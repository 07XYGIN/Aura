"""构造聊天 SSE 事件及其 JSON wire format。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class SSEEnvelope(BaseModel):
    """Versioned event contract used by new clients."""

    version: Literal[1] = 1
    eventId: str
    turnId: str
    sequence: int = Field(ge=1)
    type: str
    timestamp: str
    payload: dict[str, Any]


_V1_EVENT_TYPES = {
    "turn_started": "turn.started",
    "turn_completed": "turn.completed",
    "content": "message.created",
    "assistant_message": "message.created",
    "emotion": "emotion.updated",
    "memory_reference": "memory.referenced",
    "conversation_branch": "conversation.branched",
    "activity_state": "activity.updated",
    "error": "error",
}


class SSEProtocolV1:
    """Stateful encoder that adds stable turn metadata without breaking v0 clients."""

    def __init__(self, turn_id: str | None = None) -> None:
        self.turn_id = turn_id or str(uuid4())
        self.sequence = 0

    def envelope(self, event: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        legacy_type = str(event.get("event") or event.get("type") or "unknown")
        v1_type = _V1_EVENT_TYPES.get(legacy_type, legacy_type)
        envelope = SSEEnvelope(
            eventId=str(uuid4()),
            turnId=self.turn_id,
            sequence=self.sequence,
            type=v1_type,
            timestamp=datetime.now(UTC).isoformat(),
            payload=dict(event),
        ).model_dump()
        # ``event`` and business fields remain for v0 clients; ``type`` is the
        # canonical v1 discriminator. Old code in this repository prefers
        # ``event`` and therefore continues to work during migration.
        return {**event, **envelope, "legacyType": legacy_type, "v1Type": v1_type}

    def encode(self, event: dict[str, Any]) -> str:
        return sse_data(self.envelope(event))


def turn_lifecycle_event(state: Literal["started", "completed"]) -> dict[str, Any]:
    """Create the compatibility payload for a turn lifecycle boundary."""

    event_type = f"turn_{state}"
    return {"event": event_type, "type": event_type, "state": state}


def content_event(content: str) -> dict[str, Any]:
    """构造兼容旧客户端的纯文本 content 事件。"""

    return {"event": "content", "type": "content", "content": content}


def assistant_message_event(
    *,
    content: str,
    message_id: str,
    batch_id: str,
    batch_index: int,
    batch_total: int,
    delay_ms: int,
    sent_at: str,
) -> dict[str, Any]:
    """构造带批次、延迟和发送时间的 Aura 消息事件。"""

    return {
        "event": "assistant_message",
        "type": "assistant_message",
        "content": content,
        "messageId": message_id,
        "batchId": batch_id,
        "batchIndex": batch_index,
        "batchTotal": batch_total,
        "delayMs": delay_ms,
        "sentAt": sent_at,
    }


def emotion_event(emotion_state: dict[str, Any]) -> dict[str, Any]:
    """构造当前回合情绪上下文事件。"""

    return {"event": "emotion", "type": "emotion", "emotion": emotion_state}


def conversation_branch_event(branch_id: str, source_message_id: str | None = None) -> dict[str, Any]:
    """通知客户端后续消息已写入新的 LangGraph 对话分支。"""

    return {
        "event": "conversation_branch",
        "type": "conversation_branch",
        "branchId": branch_id,
        "sourceMessageId": source_message_id,
    }


def memory_reference_event(query: str | None = None) -> dict[str, Any]:
    """构造主模型实际检索历史记忆时的引用事件。"""

    return {
        "event": "memory_reference",
        "type": "memory_reference",
        "memory_reference": {"source": "search_memory_tool", "query": query},
    }


def error_event(message: str) -> dict[str, Any]:
    """构造可安全返回客户端的错误事件。"""

    return {"event": "error", "type": "error", "message": message}


def activity_state_event(
    activity: str,
    action: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """构造与具体活动实现解耦的状态事件。"""

    return {
        "event": "activity_state",
        "type": "activity_state",
        "activity": activity,
        "action": action,
        "snapshot": snapshot,
    }


def sse_data(event: dict[str, Any]) -> str:
    """把事件字典编码为一帧 UTF-8 SSE ``data`` 文本。"""

    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"data: {data}\n\n"


def derive_memory_candidate(message: str, emotion_state: dict[str, Any]) -> dict[str, Any]:
    """延迟导入记忆 judge，并为旧调用方生成记忆候选。"""

    from .judges.memory import judge_memory_candidate

    return judge_memory_candidate(message, emotion_state)
