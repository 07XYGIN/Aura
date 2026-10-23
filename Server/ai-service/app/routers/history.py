import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.agent.agent_graph import (
    clear_history,
    create_history_branch,
    delete_history_message,
    get_history,
)
from app.core.auth_store import get_current_user_id
from app.schemas.history import ConversationBranchRequest
from app.schemas.response import SuccessResponse

router = APIRouter(
    prefix="/api/history",
    tags=["聊天记录"],
)


@router.delete(
    "/{userId}",
    response_model=SuccessResponse,
    summary="清空指定用户的聊天记录",
)
async def delete_history(
    userId: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    branchId: str | None = None,
):
    """清空当前 JWT 用户的全部 LangGraph 聊天历史。

    路径中的 ``userId`` 仅用于兼容旧客户端。服务端始终以 JWT ``sub`` 为
    权威身份，因此伪造路径参数不能读取或删除另一条会话线程。
    """
    warn_legacy_user_mismatch(userId, current_user_id)
    try:
        deleted_count = (
            clear_history(current_user_id, branchId)
            if branchId is not None
            else clear_history(current_user_id)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SuccessResponse(data={"deletedCount": deleted_count})


@router.delete(
    "/{userId}/messages/{messageId}",
    response_model=SuccessResponse,
    summary="删除指定用户的单条聊天记录",
)
async def delete_history_item(
    userId: str,
    messageId: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    branchId: str | None = None,
):
    """删除用户的一条聊天消息。

    Raises:
        HTTPException: 指定消息不存在。
    """
    warn_legacy_user_mismatch(userId, current_user_id)
    try:
        deleted = (
            delete_history_message(current_user_id, messageId, branchId)
            if branchId is not None
            else delete_history_message(current_user_id, messageId)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    return SuccessResponse(data={"deleted": True, "messageId": messageId})


@router.get(
    "/{userId}",
    response_model=SuccessResponse,
    summary="获取指定用户的聊天记录",
)
async def history(
    userId: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    branchId: str | None = None,
):
    """返回当前 JWT 用户保存的完整聊天历史。"""
    warn_legacy_user_mismatch(userId, current_user_id)
    try:
        state = get_history(current_user_id, branchId) if branchId is not None else get_history(current_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SuccessResponse(data=state)


@router.post(
    "/{userId}/branches",
    response_model=SuccessResponse,
    summary="从一条聊天消息创建对话分支",
)
async def branch_history(
    userId: str,
    request: ConversationBranchRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """复制指定消息前的历史到新的 LangGraph 线程，不影响原对话。"""

    warn_legacy_user_mismatch(userId, current_user_id)
    try:
        branch_id = create_history_branch(
            current_user_id,
            request.message_id,
            request.branch_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if branch_id is None:
        raise HTTPException(status_code=404, detail="聊天消息不存在，无法创建分支")
    return SuccessResponse(data={"branchId": branch_id, "sourceMessageId": request.message_id})


def warn_legacy_user_mismatch(request_user_id: str, current_user_id: str) -> None:
    """记录旧客户端身份字段与 JWT 不一致的安全告警。

    该函数只记录脱敏后的控制信息，不改变请求结果，也不会把伪造身份继续传给
    数据层。保留路径参数可以让旧前端平滑升级，所有权仍由服务端强制保证。
    """

    if request_user_id != current_user_id:
        logging.warning(
            "聊天记录路径 userId 与 JWT 用户不一致，已使用 JWT 身份"
        )
