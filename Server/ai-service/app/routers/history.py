from typing import Any
from fastapi import APIRouter

from app.schemas.response import response_success
from app.utils.history import get_session_history
router = APIRouter(
    prefix='/api/history',
    tags=['聊天记录']
)

@router.delete(
        '/{userId}',
        response_model=response_success,
        summary='删除指定ID的聊天记录'
)
async def del_history(userId:Any):
    get_session_history(userId).clear()
    return response_success

@router.get(
        '/{userId}',
        response_model=response_success,
        summary='获取指定ID聊天记录'
)
async def history(userId:Any):
    frontend_messages = []
    result = get_session_history(userId)
    for msg in result.messages:
        frontend_messages.append({
            "type": msg.type,
            "content": msg.content
        })
    response_success.data = frontend_messages
    return response_success

