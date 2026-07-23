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
    """构造记忆候选事件，供客户端观察本轮记忆判断。

    条件消息候选可能包含尚未打开的正文和口令，只能向客户端返回类型、标题和
    授权摘要。真正创建结果由条件消息 API 查询；SSE 不能成为绕过密封边界的
    第二条数据通道。
    """

    public_candidate = dict(candidate)
    raw_conditional_messages = candidate.get("conditional_messages")
    public_candidate["conditional_messages"] = [
        {
            "authorized": bool(item.get("authorized", True)),
            "message_type": item.get("messageType") or item.get("message_type"),
            "condition_type": item.get("conditionType") or item.get("condition_type"),
            "title": item.get("title"),
        }
        for item in raw_conditional_messages or []
        if isinstance(item, dict)
    ]

    return {
        "event": "memory_candidate",
        "type": "memory_candidate",
        "memory_candidate": public_candidate,
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


def bash_game_state_event(snapshot: dict[str, Any]) -> dict[str, Any]:
    """构造巴什博弈状态事件。

    Args:
        snapshot: 游戏事务服务返回的公开快照，包含动作、棋局和行动列表。

    Returns:
        同时携带 ``event``/``type`` 的 SSE 业务事件；旧客户端可以忽略未知
        类型，新客户端可直接用 ``bashGame`` 渲染棋局。
    """

    return {
        "event": "bash_game_state",
        "type": "bash_game_state",
        "action": snapshot.get("action"),
        "bashGame": snapshot,
    }


def pet_state_event(snapshot: dict[str, Any]) -> dict[str, Any]:
    """构造共同宠物状态 SSE 事件。

    ``snapshot`` 只来自已提交事务或只读状态快照；旧客户端可忽略未知事件，
    新客户端可以使用 ``petState`` 渲染宠物和最近事件。
    """

    return {
        "event": "pet_state",
        "type": "pet_state",
        "action": snapshot.get("action"),
        "petState": snapshot,
    }


def sse_data(event: dict[str, Any]) -> str:
    """把事件字典编码为一帧 UTF-8 SSE ``data`` 文本。"""

    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"data: {data}\n\n"


def derive_memory_candidate(message: str, emotion_state: dict[str, Any]) -> dict[str, Any]:
    """延迟导入记忆 judge，并为旧调用方生成记忆候选。"""

    from .judges.memory import judge_memory_candidate

    return judge_memory_candidate(message, emotion_state)
