import asyncio
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.agent.agent_graph import append_external_history_turn, aura_agent, retry_aura_agent
from app.core.agent.protocol import (
    assistant_message_event,
    bash_game_state_event,
    content_event,
    error_event,
    focus_state_event,
    pet_state_event,
    sse_data,
)
from app.core.emotion import derive_emotion_state
from app.core.auth_store import get_current_user_id
from app.core.continuity.capsules import trigger_keyword_messages
from app.core.games.bash.chat import BashChatResponse, try_handle_bash_chat_message
from app.core.games.bash.service import BashGameServiceError
from app.core.focus.chat import FocusChatResponse, try_handle_focus_chat_message
from app.core.focus.service import FocusServiceError
from app.core.pet.chat import PetChatResponse, try_handle_pet_chat_message
from app.core.pet.service import PetServiceError
from app.core.silence_state import schedule_user_message_activity_record
from app.db.session import AsyncSessionLocal
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
    branch_id: str | None = None,
    retry_message_id: str | None = None,
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
            if retry_message_id:
                events = retry_aura_agent(user_id, retry_message_id, branch_id)
            else:
                events = aura_agent(
                    message,
                    user_id,
                    emotion_state,
                    client_message_id,
                    attachment_ids,
                    city_adcode,
                    branch_id,
                )
            for event in events:
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


async def bash_game_event_generator(
    response: BashChatResponse,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> AsyncIterator[str]:
    """把已完成的巴什博弈事务转换为 SSE，并写入统一聊天历史。

    Args:
        response: 游戏聊天服务返回的已提交结果。
        message: 用户原始游戏指令。
        user_id: 当前用户和 LangGraph 线程 ID。
        client_message_id: 客户端回合 ID，用于历史去重。

    Yields:
        可选 ``bash_game_state``、一到多条 Aura 消息以及最终 ``[DONE]``。

    Side Effects:
        在线程中向 LangGraph checkpoint 写入本轮用户与 Aura 消息。写入失败时
        降级为兼容 content 事件，不会改变已经提交的游戏状态。
    """

    snapshot = response.snapshot
    if snapshot is not None:
        yield sse_data(bash_game_state_event(snapshot))

    source_metadata: dict[str, object] = {"game_action": response.action}
    if snapshot and snapshot.get("game"):
        game = snapshot["game"]
        source_metadata.update(
            {
                "game_session_id": game.get("id"),
                "game_version": game.get("version"),
            }
        )
    idempotent_replay = bool(snapshot and snapshot.get("idempotentReplay"))
    reply_batch = None
    if not idempotent_replay:
        try:
            reply_batch = await asyncio.to_thread(
                append_external_history_turn,
                user_id,
                message,
                response.messages,
                source="bash_game",
                turn_id=client_message_id,
                client_message_id=client_message_id,
                source_metadata=source_metadata,
            )
        except Exception:
            logging.exception("巴什博弈消息写入统一聊天历史失败，降级为 content 事件")
    if reply_batch:
        await trigger_keyword_after_external_history(
            user_id,
            message,
            client_message_id,
            source="bash_game",
        )
        for item in reply_batch.get("messages", []):
            yield sse_data(
                assistant_message_event(
                    content=item["content"],
                    message_id=item["message_id"],
                    batch_id=item["batch_id"],
                    batch_index=item["batch_index"],
                    batch_total=item["batch_total"],
                    delay_ms=item["delay_ms"],
                    sent_at=item["sent_at"],
                )
            )
    else:
        for content in response.messages:
            yield sse_data(content_event(content))
    yield "data: [DONE]\n\n"


async def pet_event_generator(
    response: PetChatResponse,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> AsyncIterator[str]:
    """把已完成的宠物事务转换为 SSE，并按幂等规则写入聊天历史。

    Args:
        response: 宠物聊天服务返回的已提交状态和文案。
        message: 用户原始宠物命令。
        user_id: 当前用户和 LangGraph 线程 ID。
        client_message_id: 客户端回合 ID，用于事件和历史幂等关联。

    Yields:
        可选 ``pet_state``、Aura 文本事件以及最终 ``[DONE]``。

    Side Effects:
        非幂等重放时把本轮追加到 LangGraph 历史。历史写入失败只降级为
        content 事件，不回滚已经提交的宠物状态。
    """

    snapshot = response.snapshot
    if snapshot is not None:
        yield sse_data(pet_state_event(snapshot))

    source_metadata: dict[str, object] = {"pet_action": response.action}
    if snapshot and snapshot.get("pet"):
        pet = snapshot["pet"]
        source_metadata.update(
            {
                "pet_id": pet.get("id"),
                "pet_version": pet.get("version"),
            }
        )
    idempotent_replay = bool(snapshot and snapshot.get("idempotentReplay"))
    reply_batch = None
    if not idempotent_replay:
        try:
            reply_batch = await asyncio.to_thread(
                append_external_history_turn,
                user_id,
                message,
                response.messages,
                source="pet",
                turn_id=client_message_id,
                client_message_id=client_message_id,
                source_metadata=source_metadata,
            )
        except Exception:
            logging.exception("宠物消息写入统一聊天历史失败，降级为 content 事件")
    if reply_batch:
        await trigger_keyword_after_external_history(
            user_id,
            message,
            client_message_id,
            source="pet",
        )
        for item in reply_batch.get("messages", []):
            yield sse_data(
                assistant_message_event(
                    content=item["content"],
                    message_id=item["message_id"],
                    batch_id=item["batch_id"],
                    batch_index=item["batch_index"],
                    batch_total=item["batch_total"],
                    delay_ms=item["delay_ms"],
                    sent_at=item["sent_at"],
                )
            )
    else:
        for content in response.messages:
            yield sse_data(content_event(content))
    yield "data: [DONE]\n\n"


async def trigger_keyword_after_external_history(
    user_id: str,
    message: str,
    client_message_id: str | None,
    *,
    source: str,
) -> None:
    """在游戏或宠物回合确认写入统一历史后评估关键词保险箱。

    缺少稳定客户端消息 ID 时跳过；条件消息的创建和事件消费都依赖该 ID 保证
    网络重放不会触发第二次。数据库异常只影响条件评估，不回滚已经提交的游戏
    或宠物状态，也不会中断本轮 SSE。
    """

    if not client_message_id:
        return
    try:
        async with AsyncSessionLocal() as session:
            await trigger_keyword_messages(
                session,
                user_id,
                message,
                event_id=f"chat:{client_message_id}",
            )
    except Exception:
        logging.exception(
            "外部聊天回合的关键词条件评估失败 source=%s user_id=%s",
            source,
            user_id,
        )


async def focus_event_generator(
    response: FocusChatResponse,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> AsyncIterator[str]:
    """把专注事务转换成 SSE，并写入与普通聊天共用的历史。"""

    snapshot = response.snapshot
    if snapshot is not None:
        yield sse_data(focus_state_event(snapshot))
    idempotent_replay = bool(snapshot and snapshot.get("idempotentReplay"))
    reply_batch = None
    if not idempotent_replay:
        try:
            reply_batch = await asyncio.to_thread(
                append_external_history_turn,
                user_id,
                message,
                response.messages,
                source="focus",
                turn_id=client_message_id,
                client_message_id=client_message_id,
                source_metadata={
                    "focus_action": response.action,
                    "focus_session_id": (
                        (snapshot.get("focus") or {}).get("id") if snapshot else None
                    ),
                },
            )
        except Exception:
            logging.exception("专注消息写入统一聊天历史失败，降级为 content 事件")
    if reply_batch:
        await trigger_keyword_after_external_history(
            user_id,
            message,
            client_message_id,
            source="focus",
        )
        for item in reply_batch.get("messages", []):
            yield sse_data(
                assistant_message_event(
                    content=item["content"],
                    message_id=item["message_id"],
                    batch_id=item["batch_id"],
                    batch_index=item["batch_index"],
                    batch_total=item["batch_total"],
                    delay_ms=item["delay_ms"],
                    sent_at=item["sent_at"],
                )
            )
    else:
        for content in response.messages:
            yield sse_data(content_event(content))
    yield "data: [DONE]\n\n"


@router.post("/send/sse/")
async def send_message(
    msg: MessageRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """申请并发槽并为一轮用户消息创建 SSE 响应。

    Raises:
        HTTPException: 当前实时对话数量已达到配置上限。

    Returns:
        ``text/event-stream`` 流式响应；并同时异步记录用户活跃时间。

    Security:
        请求体 ``userId`` 仅为旧客户端兼容字段，所有 Agent、游戏和宠物读写均
        使用 JWT ``sub`` 作为权威用户 ID，不能通过修改请求体操作其他用户。
    """
    user_id = current_user_id
    if msg.user_id != current_user_id:
        logging.warning(
            "聊天请求体 userId 与 JWT 用户不一致，使用 JWT 身份 body_user_id=%s auth_user_id=%s",
            msg.user_id,
            current_user_id,
        )
    if msg.retry_message_id:
        if not _try_acquire_sse_slot():
            raise HTTPException(
                status_code=429,
                detail=f"Aura 正在处理太多实时对话，请稍后再试。（当前上限 {_sse_max_concurrency}）",
            )
        return StreamingResponse(
            event_generator(
                "",
                user_id,
                branch_id=msg.branch_id,
                retry_message_id=msg.retry_message_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    focus_response: FocusChatResponse | None = None
    if msg.branch_id is None:
        try:
            async with AsyncSessionLocal() as session:
                focus_response = await try_handle_focus_chat_message(
                    session,
                    message=msg.message,
                    user_id=user_id,
                    client_message_id=msg.client_message_id,
                )
        except FocusServiceError as exc:
            focus_response = FocusChatResponse(
                action="rejected",
                snapshot=None,
                messages=[str(exc)],
            )
        except Exception:
            logging.exception("一起专注聊天分流失败，回退到普通 Aura 对话")

    if focus_response is not None:
        schedule_user_message_activity_record(user_id)
        return StreamingResponse(
            focus_event_generator(
                focus_response,
                message=msg.message,
                user_id=user_id,
                client_message_id=msg.client_message_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    game_response: BashChatResponse | None = None
    if msg.branch_id is None:
        try:
            async with AsyncSessionLocal() as session:
                game_response = await try_handle_bash_chat_message(
                    session,
                    message=msg.message,
                    user_id=user_id,
                    client_message_id=msg.client_message_id,
                )
        except BashGameServiceError as exc:
            game_response = BashChatResponse(
                action="rejected",
                snapshot=None,
                messages=[str(exc)],
            )
        except Exception:
            logging.exception("巴什博弈聊天分流失败，回退到普通 Aura 对话")

    if game_response is not None:
        schedule_user_message_activity_record(user_id)
        return StreamingResponse(
            bash_game_event_generator(
                game_response,
                message=msg.message,
                user_id=user_id,
                client_message_id=msg.client_message_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    pet_response: PetChatResponse | None = None
    if msg.branch_id is None:
        try:
            async with AsyncSessionLocal() as session:
                pet_response = await try_handle_pet_chat_message(
                    session,
                    message=msg.message,
                    user_id=user_id,
                    client_message_id=msg.client_message_id,
                )
        except PetServiceError as exc:
            pet_response = PetChatResponse(
                action="rejected",
                snapshot=None,
                messages=[str(exc)],
            )
        except Exception:
            logging.exception("共同宠物聊天分流失败，回退到普通 Aura 对话")

    if pet_response is not None:
        schedule_user_message_activity_record(user_id)
        return StreamingResponse(
            pet_event_generator(
                pet_response,
                message=msg.message,
                user_id=user_id,
                client_message_id=msg.client_message_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    if not _try_acquire_sse_slot():
        raise HTTPException(
            status_code=429,
            detail=f"Aura 正在处理太多实时对话，请稍后再试。（当前上限 {_sse_max_concurrency}）",
        )

    schedule_user_message_activity_record(user_id)
    return StreamingResponse(
        event_generator(
            msg.message,
            user_id,
            msg.client_message_id,
            msg.attachment_ids,
            msg.city_adcode,
            msg.branch_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
