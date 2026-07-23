"""一起专注与主聊天入口之间的确定性分流。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.focus import FocusActionRequest, FocusProgressRequest, FocusStartRequest

from .parser import is_focus_chat_candidate, parse_focus_chat_intent
from .service import (
    FocusServiceError,
    apply_focus_action,
    get_current_focus_session,
    get_current_focus_snapshot,
    report_focus_progress,
    start_focus_session,
)


@dataclass(frozen=True)
class FocusChatResponse:
    """专注聊天命中后交给 SSE 层的状态与 Aura 文案。"""

    action: str
    snapshot: dict[str, Any] | None
    messages: list[str]


async def try_handle_focus_chat_message(
    session: AsyncSession,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> FocusChatResponse | None:
    """识别并执行一条明确的专注命令，普通聊天返回 ``None``。"""

    if not is_focus_chat_candidate(message):
        return None
    focus = await get_current_focus_session(session, user_id)
    intent = parse_focus_chat_intent(
        message,
        current_status=focus.status if focus is not None else None,
    )
    if intent is None:
        return None
    if intent.action == "invalid_duration":
        raise FocusServiceError("专注时长必须在 1 到 240 分钟之间")
    if intent.action == "start":
        action_id = require_focus_action_id(client_message_id)
        snapshot = await start_focus_session(
            session,
            user_id,
            FocusStartRequest(
                activity=intent.activity or "手头的事",
                durationMinutes=intent.duration_minutes,
                startRequestId=action_id,
                sourceMessageId=client_message_id,
            ),
        )
        return FocusChatResponse(
            "started",
            snapshot,
            [f"好，{intent.duration_minutes} 分钟。你去专注“{intent.activity}”，时间到了我叫你。"],
        )
    if intent.action == "status":
        snapshot = await get_current_focus_snapshot(session, user_id)
        if snapshot is None:
            return FocusChatResponse("no_focus", None, ["现在没有正在进行的专注。"])
        return FocusChatResponse("status", snapshot, [focus_status_message(snapshot)])
    if focus is None:
        return FocusChatResponse("no_focus", None, ["现在没有可以操作的专注。"])

    action_id = require_focus_action_id(client_message_id)
    if intent.action in {"pause", "resume", "cancel"}:
        snapshot = await apply_focus_action(
            session,
            user_id,
            str(focus.id),
            FocusActionRequest(
                action=intent.action,
                clientActionId=action_id,
                expectedVersion=focus.version,
            ),
        )
        messages = {
            "pause": ["先暂停。我把剩下的时间留着。"],
            "resume": ["继续。剩下这段我不打扰你。"],
            "cancel": ["好，这次专注取消了。"],
        }
        return FocusChatResponse(intent.action, snapshot, messages[intent.action])
    if intent.action == "report":
        snapshot = await report_focus_progress(
            session,
            user_id,
            str(focus.id),
            FocusProgressRequest(
                resultSummary=intent.result_summary or message,
                blocker=intent.blocker,
                clientActionId=action_id,
                expectedVersion=focus.version,
            ),
        )
        if intent.blocker:
            reply = f"记下了，你现在卡在“{intent.blocker}”。下次接着做时，我们从这里开始。"
        else:
            reply = "好，这段专注算收工。"
        return FocusChatResponse("completed", snapshot, [reply])
    return None


def focus_status_message(snapshot: dict[str, Any]) -> str:
    """把公开快照转换成一条简短状态回复。"""

    focus = snapshot.get("focus") or {}
    status = focus.get("status")
    activity = focus.get("activity") or "手头的事"
    if status == "active":
        seconds = int(focus.get("remainingSeconds") or 0)
        return f"还在专注“{activity}”，大约剩 {(seconds + 59) // 60} 分钟。"
    if status == "paused":
        return f"“{activity}”暂停着，剩余时间还留着。"
    if status == "awaiting_report":
        return f"“{activity}”已经到时，我在等你说进展。"
    return f"“{activity}”的结束问询正在处理。"


def require_focus_action_id(client_message_id: str | None) -> str:
    """要求专注写操作携带稳定客户端消息 ID。"""

    action_id = str(client_message_id or "").strip()
    if not action_id:
        raise FocusServiceError("专注写操作需要 clientMessageId，避免网络重试重复计时")
    return action_id
