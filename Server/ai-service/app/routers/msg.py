import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.agent.agent_graph import aura_agent
from app.schemas.request import MessageRequest

router = APIRouter(
    prefix='/api',
    tags=['发送消息']
)


def event_generator(message: str, user_id: str):
    for chunk in aura_agent(message, user_id):
        yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.post('/send/sse/')
async def send_message(msg: MessageRequest):
    return StreamingResponse(
        event_generator(msg.message, msg.user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )
