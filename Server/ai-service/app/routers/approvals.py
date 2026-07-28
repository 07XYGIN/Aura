"""Aura 长期记忆与关系变更的人工审批接口。"""

from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.agent.agent_graph import list_pending_approvals, resolve_pending_approval
from app.core.auth_store import get_current_user_id
from app.schemas.approval import ApprovalResolutionRequest
from app.schemas.response import SuccessResponse


router = APIRouter(prefix="/api/approvals", tags=["人工审批"])


@router.get("", response_model=SuccessResponse, summary="读取 Aura 等待确认的长期变更")
async def read_pending_approvals(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """返回当前用户在 LangGraph checkpointer 中仍未解决的审批摘要。"""

    approvals = await asyncio.to_thread(list_pending_approvals, current_user_id)
    return SuccessResponse(data={"items": approvals})


@router.post("/{approval_id}/resolve", response_model=SuccessResponse, summary="批准或拒绝 Aura 长期变更")
async def resolve_approval(
    approval_id: str,
    request: ApprovalResolutionRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """用 LangGraph ``Command(resume=...)`` 恢复对应的人工审批子图。"""

    result = await asyncio.to_thread(
        resolve_pending_approval,
        current_user_id,
        approval_id,
        request.approved,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="审批不存在、已处理或无法恢复")
    return SuccessResponse(data=result)
