"""Thin HTTP adapter for Aura conversation turns."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.agent.agent_graph import append_external_history_turn, aura_agent, retry_aura_agent
from app.core.agent.models import (
    ActivityResult,
    InteractionMode,
    InteractionState,
    TurnPlan,
    TurnRequest,
)
from app.core.agent.orchestrator import TurnOrchestrator
from app.core.auth_store import get_current_user_id
from app.core.config import AURA_OPTIONAL_ACTIVITIES_ENABLED
from app.core.focus.chat import FocusChatResponse, try_handle_focus_chat_message
from app.core.games.bash.chat import BashChatResponse, try_handle_bash_chat_message
from app.core.pet.chat import PetChatResponse, try_handle_pet_chat_message
from app.core.silence_state import schedule_user_message_activity_record
from app.interfaces.conversation_stream import conversation_stream_runtime
from app.schemas.request import MessageRequest


router = APIRouter(prefix="/api", tags=["发送消息"])
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

# One-release compatibility surface for callers/tests that imported these names.
_sse_max_concurrency = conversation_stream_runtime.max_concurrency
_sse_queue_size = conversation_stream_runtime.queue_size


def _configure_sse_runtime_for_tests(max_concurrency: int, queue_size: int = 32) -> None:
    global _sse_max_concurrency, _sse_queue_size
    conversation_stream_runtime.configure_for_tests(max_concurrency, queue_size)
    _sse_max_concurrency = max_concurrency
    _sse_queue_size = queue_size


def _try_acquire_sse_slot() -> bool:
    return conversation_stream_runtime.try_acquire()


def _release_sse_slot() -> None:
    conversation_stream_runtime.release()


async def event_generator(
    message: str,
    user_id: str,
    client_message_id: str | None = None,
    attachment_ids: list[str] | None = None,
    city_adcode: str | None = None,
    branch_id: str | None = None,
    retry_message_id: str | None = None,
) -> AsyncIterator[str]:
    """Backward-compatible facade over the conversation stream runtime."""

    request = TurnRequest(
        user_id=user_id,
        message=message,
        client_message_id=client_message_id,
        attachment_ids=attachment_ids or [],
        city_adcode=city_adcode,
        branch_id=branch_id,
        retry_message_id=retry_message_id,
    )
    plan = TurnPlan(
        request=request,
        interaction=InteractionState(
            mode=InteractionMode.RETRY if retry_message_id else InteractionMode.NORMAL,
            branch_id=branch_id,
            retry_message_id=retry_message_id,
        ),
    )
    async for frame in conversation_stream_runtime.stream(
        plan,
        aura_agent=aura_agent,
        retry_aura_agent=retry_aura_agent,
    ):
        yield frame


def _legacy_activity_result(
    activity: str,
    response: FocusChatResponse | BashChatResponse | PetChatResponse,
) -> ActivityResult:
    snapshot = response.snapshot or {}
    entity_name = {"focus": "focus", "bash_game": "game", "pet": "pet"}[activity]
    entity = snapshot.get(entity_name) or {}
    metadata: dict[str, Any] = {f"{activity}_action": response.action}
    if isinstance(entity, dict):
        metadata[f"{activity}_id"] = entity.get("id")
        metadata[f"{activity}_version"] = entity.get("version")
    return ActivityResult(
        activity=activity,
        action=response.action,
        snapshot=response.snapshot,
        messages=response.messages,
        source_metadata=metadata,
    )


async def _legacy_activity_stream(
    activity: str,
    response: FocusChatResponse | BashChatResponse | PetChatResponse,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> AsyncIterator[str]:
    request = TurnRequest(
        user_id=user_id,
        message=message,
        client_message_id=client_message_id,
    )
    plan = TurnPlan(
        request=request,
        interaction=InteractionState(mode=InteractionMode.ACTIVITY, activity=activity),
        activity_result=_legacy_activity_result(activity, response),
    )
    async for frame in TurnOrchestrator().stream_activity(plan):
        yield frame


async def bash_game_event_generator(
    response: BashChatResponse,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> AsyncIterator[str]:
    async for frame in _legacy_activity_stream(
        "bash_game", response, message=message, user_id=user_id,
        client_message_id=client_message_id,
    ):
        yield frame


async def pet_event_generator(
    response: PetChatResponse,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> AsyncIterator[str]:
    async for frame in _legacy_activity_stream(
        "pet", response, message=message, user_id=user_id,
        client_message_id=client_message_id,
    ):
        yield frame


async def focus_event_generator(
    response: FocusChatResponse,
    *,
    message: str,
    user_id: str,
    client_message_id: str | None,
) -> AsyncIterator[str]:
    async for frame in _legacy_activity_stream(
        "focus", response, message=message, user_id=user_id,
        client_message_id=client_message_id,
    ):
        yield frame


@router.post("/send/sse/")
async def send_message(
    msg: MessageRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """Authenticate, prepare one turn, and expose it as an SSE response."""

    if msg.user_id != current_user_id:
        logging.warning(
            "聊天请求体 userId 与 JWT 用户不一致，使用 JWT 身份 body_user_id=%s auth_user_id=%s",
            msg.user_id,
            current_user_id,
        )
    request = TurnRequest(
        user_id=current_user_id,
        message=msg.message,
        client_message_id=msg.client_message_id,
        attachment_ids=msg.attachment_ids,
        city_adcode=msg.city_adcode,
        branch_id=msg.branch_id,
        retry_message_id=msg.retry_message_id,
    )
    orchestrator = TurnOrchestrator(activities_enabled=AURA_OPTIONAL_ACTIVITIES_ENABLED)
    plan = await orchestrator.prepare(request)
    schedule_user_message_activity_record(current_user_id)

    if plan.interaction.mode == InteractionMode.ACTIVITY:
        stream = orchestrator.stream_activity(plan)
    else:
        if not _try_acquire_sse_slot():
            raise HTTPException(
                status_code=429,
                detail=(
                    "Aura 正在处理太多实时对话，请稍后再试。"
                    f"（当前上限 {_sse_max_concurrency}）"
                ),
            )
        stream = event_generator(
            request.message,
            request.user_id,
            request.client_message_id,
            request.attachment_ids,
            request.city_adcode,
            request.branch_id,
            request.retry_message_id,
        )

    return StreamingResponse(stream, media_type="text/event-stream", headers=_SSE_HEADERS)
