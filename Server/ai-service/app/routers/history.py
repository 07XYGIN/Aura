from typing import Any
from fastapi import APIRouter

from app.schemas.response import response_success
from app.utils.history import get_session_history

from app.core.agent.agent_graph import aura, get_history

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
    state = get_history(userId)
    response_success.data = state
    return response_success
