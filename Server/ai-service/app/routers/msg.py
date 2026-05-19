from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.request import request_msg
from app.core.agent.agent_graph import aura_agent
router = APIRouter(
    prefix='/api',
    tags=['发送消息']
)


@router.post('/send/sse/')
async def sse_test(msg:request_msg):
    result = aura_agent(msg.message,msg.userId)

    return result
