"""SSE runtime for streaming synchronous LangGraph turns without blocking FastAPI."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections.abc import AsyncIterator, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.core.agent.models import InteractionMode, TurnPlan
from app.core.agent.protocol import SSEProtocolV1, error_event, turn_lifecycle_event
from app.core.emotion import derive_emotion_state


_SSE_DONE = object()
_QUEUE_PUT_CHECK_INTERVAL_SECONDS = 0.1


def _positive_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return max(int(value), 1)
    except ValueError:
        logging.warning("环境变量不是有效正整数 name=%s value=%r", name, value)
        return default


class ConversationCapacityError(RuntimeError):
    pass


class ConversationStreamRuntime:
    def __init__(self, max_concurrency: int | None = None, queue_size: int | None = None) -> None:
        self.max_concurrency = max_concurrency or _positive_int_env("AURA_SSE_MAX_CONCURRENCY", 16)
        self.queue_size = queue_size or _positive_int_env("AURA_SSE_QUEUE_SIZE", 32)
        self._slots = threading.BoundedSemaphore(self.max_concurrency)
        self._executor = ThreadPoolExecutor(
            max_workers=self.max_concurrency,
            thread_name_prefix="aura-sse",
        )

    def configure_for_tests(self, max_concurrency: int, queue_size: int = 32) -> None:
        if max_concurrency < 1 or queue_size < 1:
            raise ValueError("并发数和队列大小必须大于 0")
        previous = self._executor
        self.max_concurrency = max_concurrency
        self.queue_size = queue_size
        self._slots = threading.BoundedSemaphore(max_concurrency)
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrency,
            thread_name_prefix="aura-sse-test",
        )
        previous.shutdown(wait=False, cancel_futures=True)

    def try_acquire(self) -> bool:
        return self._slots.acquire(blocking=False)

    def release(self) -> None:
        try:
            self._slots.release()
        except ValueError:
            logging.error("Aura SSE 并发槽被重复释放")

    async def stream(
        self,
        plan: TurnPlan,
        *,
        aura_agent: Callable[..., Iterable[dict[str, Any]]],
        retry_aura_agent: Callable[..., Iterable[dict[str, Any]]],
    ) -> AsyncIterator[str]:
        request = plan.request
        started_at = time.perf_counter()
        protocol = SSEProtocolV1(request.client_message_id)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | object] = asyncio.Queue(maxsize=self.queue_size)
        stop_event = threading.Event()
        release_lock = threading.Lock()
        released = False

        def release_once() -> None:
            nonlocal released
            with release_lock:
                if released:
                    return
                released = True
            self.release()

        def put(item: str | object) -> bool:
            if stop_event.is_set():
                return False
            try:
                future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
            except RuntimeError:
                return False
            while True:
                try:
                    future.result(timeout=_QUEUE_PUT_CHECK_INTERVAL_SECONDS)
                    return not stop_event.is_set()
                except TimeoutError:
                    if stop_event.is_set():
                        future.cancel()
                        return False
                except Exception:
                    logging.exception("Aura SSE 队列写入失败")
                    return False

        def produce() -> None:
            try:
                if not put(protocol.encode(turn_lifecycle_event("started"))):
                    return
                if plan.interaction.mode == InteractionMode.RETRY:
                    events = retry_aura_agent(
                        request.user_id,
                        request.retry_message_id,
                        request.branch_id,
                    )
                else:
                    events = aura_agent(
                        request.message,
                        request.user_id,
                        derive_emotion_state(request.message).to_dict(),
                        request.client_message_id,
                        request.attachment_ids,
                        request.city_adcode,
                        request.branch_id,
                    )
                for event in events:
                    if stop_event.is_set() or not put(protocol.encode(event)):
                        break
            except Exception:
                logging.exception("Aura SSE 对话流失败")
                put(protocol.encode(error_event("Aura 服务暂时没有组织好回复，请稍后再试。")))
            finally:
                logging.info(
                    "Aura SSE 对话流结束 user_id=%s duration_ms=%s",
                    request.user_id,
                    round((time.perf_counter() - started_at) * 1000),
                )
                if not stop_event.is_set():
                    put(protocol.encode(turn_lifecycle_event("completed")))
                    put("data: [DONE]\n\n")
                    put(_SSE_DONE)
                release_once()

        producer = loop.run_in_executor(self._executor, produce)
        producer.add_done_callback(lambda _future: release_once())
        try:
            while True:
                item = await queue.get()
                if item is _SSE_DONE:
                    break
                yield str(item)
        finally:
            stop_event.set()


conversation_stream_runtime = ConversationStreamRuntime()
