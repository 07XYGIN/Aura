"""聊天历史 HTTP 接口。"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.agent.conversation.history import clear_history, delete_history_message, get_history
from app.core.auth_store import get_current_user_id
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/history", tags=["聊天记录"])


@router.get("/{user_id}", response_model=SuccessResponse, summary="获取聊天记录")
async def history(
    user_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """返回当前登录用户的聊天历史。"""

    _warn_user_mismatch(user_id, current_user_id)
    return SuccessResponse(data=get_history(current_user_id))


@router.delete("/{user_id}", response_model=SuccessResponse, summary="清空聊天记录")
async def delete_history(
    user_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """清空当前登录用户的聊天历史。"""

    _warn_user_mismatch(user_id, current_user_id)
    return SuccessResponse(data={"deletedCount": clear_history(current_user_id)})


@router.delete(
    "/{user_id}/messages/{message_id}",
    response_model=SuccessResponse,
    summary="删除一条聊天记录",
)
async def delete_history_item(
    user_id: str,
    message_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """删除当前登录用户的一条聊天消息。"""

    _warn_user_mismatch(user_id, current_user_id)
    if not delete_history_message(current_user_id, message_id):
        raise HTTPException(status_code=404, detail="聊天记录不存在")
    return SuccessResponse(data={"deleted": True, "messageId": message_id})


def _warn_user_mismatch(request_user_id: str, current_user_id: str) -> None:
    """记录旧路径身份与 JWT 身份不一致的情况。"""

    if request_user_id != current_user_id:
        logging.warning("聊天记录路径 userId 与 JWT 用户不一致，已使用 JWT 身份")
