"""Thin HTTP adapter for Aura conversation turns."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.agent.conversation import aura_agent, retry_aura_agent
from app.core.agent.conversation.protocol import (
    SSEProtocolV1,
    error_event,
    turn_lifecycle_event,
)
from app.core.agent.schemas.models import TurnRequest
from app.core.auth_store import get_current_user_id
from app.core.emotion import derive_emotion_state
from app.schemas.request import MessageRequest


router = APIRouter(prefix="/api", tags=["发送消息"])
_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def event_generator(request: TurnRequest) -> Iterator[str]:
    """Encode one synchronous Agent turn as an SSE stream."""

    protocol = SSEProtocolV1(request.client_message_id)
    yield protocol.encode(turn_lifecycle_event("started"))

    try:
        if request.retry_message_id:
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
            yield protocol.encode(event)
    except Exception:
        logging.exception("Aura SSE 对话流失败 user_id=%s", request.user_id)
        yield protocol.encode(error_event("Aura 服务暂时没有组织好回复，请稍后再试。"))

    yield protocol.encode(turn_lifecycle_event("completed"))
    yield "data: [DONE]\n\n"


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
    return StreamingResponse(
        event_generator(request),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
