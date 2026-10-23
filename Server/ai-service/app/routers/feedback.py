"""记录用户对 Aura 单条回复的风格纠偏。"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth_store import get_current_user_id
from app.core.interaction_feedback import record_reply_feedback
from app.schemas.feedback import ReplyFeedbackRequest
from app.schemas.response import SuccessResponse


router = APIRouter(prefix="/api/feedback", tags=["对话反馈"])


@router.post("/reply", response_model=SuccessResponse, summary="纠正 Aura 的单条回复风格")
async def submit_reply_feedback(
    request: ReplyFeedbackRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """保存用户明确反馈，下一轮加载为互动规则。"""

    stored = await asyncio.to_thread(
        record_reply_feedback,
        current_user_id,
        request.message_id,
        request.category,
    )
    return SuccessResponse(data={"stored": stored, "category": request.category})
