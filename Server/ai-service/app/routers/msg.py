import logging
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.agent.agent_graph import aura_agent
from app.core.agent.protocol import error_event, sse_data
from app.core.emotion import derive_emotion_state
from app.schemas.request import MessageRequest

router = APIRouter(
    prefix="/api",
    tags=["发送消息"],
)


def event_generator(message: str, user_id: str, client_message_id: str | None = None):
    started_at = time.perf_counter()
    emotion_state = derive_emotion_state(message).to_dict()
    logging.info(
        "Aura SSE stream start user_id=%s client_message_id=%s message_length=%s",
        user_id,
        client_message_id,
        len(message),
    )
    try:
        for event in aura_agent(message, user_id, emotion_state, client_message_id):
            logging.info("Aura SSE event user_id=%s event=%s", user_id, event.get("event"))
            yield sse_data(event)
    except Exception:
        logging.exception("Aura SSE stream failed")
        yield sse_data(error_event("Aura 服务暂时没有组织好回复，请稍后再试。"))
    logging.info(
        "Aura SSE stream end user_id=%s duration_ms=%s",
        user_id,
        round((time.perf_counter() - started_at) * 1000),
    )
    yield "data: [DONE]\n\n"


@router.post("/send/sse/")
async def send_message(msg: MessageRequest):
    return StreamingResponse(
        event_generator(msg.message, msg.user_id, msg.client_message_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
