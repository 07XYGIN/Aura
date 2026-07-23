"""构造聊天 SSE 事件及其 JSON wire format。"""

from __future__ import annotations

import json
from typing import Any, Literal


MemoryScope = Literal["short", "mid", "long"]


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


def memory_candidate_event(candidate: dict[str, Any]) -> dict[str, Any]:
    """构造记忆候选事件，供客户端观察本轮记忆判断。"""

    return {
        "event": "memory_candidate",
        "type": "memory_candidate",
        "memory_candidate": candidate,
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


def sse_data(event: dict[str, Any]) -> str:
    """把事件字典编码为一帧 UTF-8 SSE ``data`` 文本。"""

    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"data: {data}\n\n"


def derive_memory_candidate(message: str, emotion_state: dict[str, Any]) -> dict[str, Any]:
    """延迟导入记忆 judge，并为旧调用方生成记忆候选。"""

    from .judges.memory import judge_memory_candidate

    return judge_memory_candidate(message, emotion_state)
