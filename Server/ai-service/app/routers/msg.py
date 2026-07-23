import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.agent.agent_graph import aura_agent
from app.core.agent.protocol import error_event, sse_data
from app.core.emotion import derive_emotion_state
from app.core.silence_state import schedule_user_message_activity_record
from app.schemas.request import MessageRequest

router = APIRouter(
    prefix="/api",
    tags=["发送消息"],
)

_SSE_DONE = object()
_QUEUE_PUT_CHECK_INTERVAL_SECONDS = 0.1


def _positive_int_env(name: str, default: int) -> int:
    """读取正整数环境变量，无效时记录告警并使用默认值。"""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        logging.warning("环境变量不是有效正整数 name=%s value=%r，回退到 default=%s", name, value, default)
        return default
    return max(parsed, 1)


_sse_max_concurrency = _positive_int_env("AURA_SSE_MAX_CONCURRENCY", 16)
_sse_queue_size = _positive_int_env("AURA_SSE_QUEUE_SIZE", 32)
_sse_slots = threading.BoundedSemaphore(_sse_max_concurrency)
_sse_executor = ThreadPoolExecutor(
    max_workers=_sse_max_concurrency,
    thread_name_prefix="aura-sse",
)


def _configure_sse_runtime_for_tests(max_concurrency: int, queue_size: int = 32) -> None:
    """重建 SSE 并发槽、线程池和队列配置，供隔离测试使用。

    Raises:
        ValueError: 并发数或队列大小小于 1。

    Side Effects:
        关闭旧线程池并替换模块级 SSE 运行时对象。
    """
    global _sse_executor, _sse_max_concurrency, _sse_queue_size, _sse_slots

    if max_concurrency < 1:
        raise ValueError("最大并发数必须大于 0")
    if queue_size < 1:
        raise ValueError("队列大小必须大于 0")

    previous_executor = _sse_executor
    _sse_max_concurrency = max_concurrency
    _sse_queue_size = queue_size
    _sse_slots = threading.BoundedSemaphore(max_concurrency)
    _sse_executor = ThreadPoolExecutor(
        max_workers=max_concurrency,
        thread_name_prefix="aura-sse-test",
    )
    previous_executor.shutdown(wait=False, cancel_futures=True)


def _try_acquire_sse_slot() -> bool:
    """非阻塞申请一个 SSE 对话并发槽。"""
    return _sse_slots.acquire(blocking=False)


def _release_sse_slot() -> None:
    """释放 SSE 并发槽；重复释放只记录错误，不向外抛出。"""
    try:
        _sse_slots.release()
    except ValueError:
        logging.error("Aura SSE 并发槽被重复释放")


async def event_generator(
    message: str,
    user_id: str,
    client_message_id: str | None = None,
    attachment_ids: list[str] | None = None,
    city_adcode: str | None = None,
) -> AsyncIterator[str]:
    """在线程池运行同步 Agent，并桥接为异步 SSE 文本流。

    Args:
        message: 用户本轮文本。
        user_id: 当前用户 ID，同时作为 LangGraph 线程标识。
        client_message_id: 客户端消息 ID，用于幂等和历史关联。
        attachment_ids: 本轮引用的已上传附件 ID。
        city_adcode: 天气工具可使用的城市编码。

    Yields:
        已编码的 SSE ``data`` 帧，结束前发送 ``[DONE]``。

    Side Effects:
        在线程池调用 Agent、写入聊天相关状态，并在结束或断连后释放并发槽。
    """
    started_at = time.perf_counter()
    emotion_state = derive_emotion_state(message).to_dict()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[str | object] = asyncio.Queue(maxsize=_sse_queue_size)
    stop_event = threading.Event()
    release_lock = threading.Lock()
    released = False

    logging.info(
        "Aura SSE 对话流开始 user_id=%s client_message_id=%s message_length=%s",
        user_id,
        client_message_id,
        len(message),
    )

    def release_slot_once() -> None:
        """在锁保护下确保本轮 SSE 并发槽最多释放一次。"""
        nonlocal released
        with release_lock:
            if released:
                return
            released = True
        _release_sse_slot()

    def put_from_thread(item: str | object) -> bool:
        """从生产线程向异步队列背压写入事件，断流时停止等待。"""
        if stop_event.is_set():
            return False

        try:
            put_future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
        except RuntimeError:
            return False

        while True:
            try:
                put_future.result(timeout=_QUEUE_PUT_CHECK_INTERVAL_SECONDS)
                return not stop_event.is_set()
            except TimeoutError:
                if stop_event.is_set():
                    put_future.cancel()
                    return False
            except Exception:
                logging.exception("Aura SSE 队列写入失败")
                return False

    def produce_events() -> None:
        """同步消费 Agent 事件并推入异步队列，异常时发送统一错误事件。"""
        try:
            for event in aura_agent(
                message,
                user_id,
                emotion_state,
                client_message_id,
                attachment_ids,
                city_adcode,
            ):
                if stop_event.is_set():
                    break
                # logging.info("Aura SSE event user_id=%s event=%s", user_id, event.get("event"))
                if not put_from_thread(sse_data(event)):
                    break
        except Exception:
            logging.exception("Aura SSE 对话流失败")
            put_from_thread(sse_data(error_event("Aura 服务暂时没有组织好回复，请稍后再试。")))
        finally:
            logging.info(
                "Aura SSE 对话流结束 user_id=%s duration_ms=%s",
                user_id,
                round((time.perf_counter() - started_at) * 1000),
            )
            if not stop_event.is_set():
                put_from_thread("data: [DONE]\n\n")
                put_from_thread(_SSE_DONE)
            release_slot_once()

    producer = loop.run_in_executor(_sse_executor, produce_events)
    producer.add_done_callback(lambda _future: release_slot_once())

    try:
        while True:
            item = await queue.get()
            if item is _SSE_DONE:
                break
            yield str(item)
    finally:
        stop_event.set()


@router.post("/send/sse/")
async def send_message(msg: MessageRequest):
    """申请并发槽并为一轮用户消息创建 SSE 响应。

    Raises:
        HTTPException: 当前实时对话数量已达到配置上限。

    Returns:
        ``text/event-stream`` 流式响应；并同时异步记录用户活跃时间。
    """
    if not _try_acquire_sse_slot():
        raise HTTPException(
            status_code=429,
            detail=f"Aura 正在处理太多实时对话，请稍后再试。（当前上限 {_sse_max_concurrency}）",
        )

    schedule_user_message_activity_record(msg.user_id)
    return StreamingResponse(
        event_generator(
            msg.message,
            msg.user_id,
            msg.client_message_id,
            msg.attachment_ids,
            msg.city_adcode,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
