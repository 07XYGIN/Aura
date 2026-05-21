from fastapi import APIRouter
import json
from fastapi.responses import StreamingResponse
from app.schemas.request import request_msg
from app.core.agent.agent_graph import aura_agent
router = APIRouter(
    prefix='/api',
    tags=['发送消息']
)

def event_generator(message: str, user_id: str):
    for chunk in aura_agent(message, user_id):
        yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"

@router.post('/send/sse/')
async def sse_test(msg:request_msg):
    return StreamingResponse(
        event_generator(msg.message, msg.userId),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
