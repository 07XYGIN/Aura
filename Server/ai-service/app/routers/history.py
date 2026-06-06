from fastapi import APIRouter

from app.core.agent.agent_graph import get_history
from app.schemas.response import SuccessResponse
from app.utils.history import clear_session_history

router = APIRouter(
    prefix='/api/history',
    tags=['聊天记录']
)


@router.delete(
    '/{userId}',
    response_model=SuccessResponse,
    summary='删除指定 ID 的聊天记录'
)
async def delete_history(userId: str):
    clear_session_history(userId)
    return SuccessResponse()


@router.get(
    '/{userId}',
    response_model=SuccessResponse,
    summary='获取指定 ID 聊天记录'
)
async def history(userId: str):
    state = get_history(userId)
    return SuccessResponse(data=state)
