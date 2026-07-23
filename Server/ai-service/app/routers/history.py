from fastapi import APIRouter, HTTPException

from app.core.agent.agent_graph import clear_history, delete_history_message, get_history
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
async def delete_history(userId: str):
    """清空用户的全部 LangGraph 聊天历史并返回删除数量。"""
    deleted_count = clear_history(userId)
    return SuccessResponse(data={"deletedCount": deleted_count})


@router.delete(
    "/{userId}/messages/{messageId}",
    response_model=SuccessResponse,
    summary="删除指定用户的单条聊天记录",
)
async def delete_history_item(userId: str, messageId: str):
    """删除用户的一条聊天消息。

    Raises:
        HTTPException: 指定消息不存在。
    """
    deleted = delete_history_message(userId, messageId)
    if not deleted:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    return SuccessResponse(data={"deleted": True, "messageId": messageId})


@router.get(
    "/{userId}",
    response_model=SuccessResponse,
    summary="获取指定用户的聊天记录",
)
async def history(userId: str):
    """返回用户当前保存的完整聊天历史。"""
    state = get_history(userId)
    return SuccessResponse(data=state)
