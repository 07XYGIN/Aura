"""读取和维护 LangGraph 中的最小聊天历史。"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from ..graph import agent_runtime
from .message_utils import message_content_to_text


def conversation_config(user_id: str) -> RunnableConfig:
    """为当前用户生成唯一的 LangGraph checkpoint 配置。"""

    return {
        "configurable": {
            "thread_id": user_id,
            "user_id": user_id,
        }
    }


def get_history(user_id: str) -> list[dict[str, Any]]:
    """导出当前用户的文本聊天历史。"""

    messages = _get_messages(user_id)
    history: list[dict[str, Any]] = []
    for message in messages:
        message_type = getattr(message, "type", None)
        if message_type not in {"human", "ai"}:
            continue
        content = message_content_to_text(getattr(message, "content", ""))
        if not content:
            continue
        metadata = getattr(message, "additional_kwargs", {}) or {}
        history.append(
            {
                "id": getattr(message, "id", None) or f"{message_type}-{len(history)}",
                "role": "user" if message_type == "human" else "aura",
                "content": content,
                "attachments": public_history_attachments(metadata.get("attachments")),
                "createdAt": metadata.get("sent_at"),
                "turnId": metadata.get("turn_id"),
            }
        )
    return history


def delete_history_message(user_id: str, message_id: str) -> bool:
    """删除当前用户的一条 checkpoint 消息。"""

    normalized_message_id = message_id.strip()
    if not normalized_message_id:
        return False
    messages = _get_messages(user_id)
    if not any(getattr(message, "id", None) == normalized_message_id for message in messages):
        return False

    _require_graph().update_state(
        conversation_config(user_id),
        {"messages": [RemoveMessage(id=normalized_message_id, content="")]},
    )
    return True


def clear_history(user_id: str) -> int:
    """清空当前用户的 checkpoint 消息并返回原消息数量。"""

    messages = _get_messages(user_id)
    if not messages:
        return 0
    _require_graph().update_state(
        conversation_config(user_id),
        {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES, content="")]},
    )
    return len(messages)


def public_history_attachments(value: Any) -> list[dict[str, Any]]:
    """只返回前端展示附件所需的安全字段。"""

    if not isinstance(value, list):
        return []
    return [
        {
            "id": item.get("id"),
            "fileName": item["fileName"],
            "contentType": item.get("contentType"),
            "size": item.get("size"),
        }
        for item in value
        if isinstance(item, dict) and isinstance(item.get("fileName"), str)
    ]


def _get_messages(user_id: str) -> list:
    """读取用户 checkpoint 中的消息列表。"""

    state = _require_graph().get_state(conversation_config(user_id))
    if not state or not state.values:
        return []
    return list(state.values.get("messages", []))


def _require_graph():
    """返回已初始化的共享图。"""

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")
    return agent_runtime.graph
