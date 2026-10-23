"""执行最小聊天回合并输出 SSE 业务事件。"""

from __future__ import annotations

import logging
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.core.attachment_store import load_attachments

from ..graph import agent_runtime
from .history import conversation_config
from .message_utils import message_content_to_text
from .protocol import content_event


def aura_agent(
    human_prompt: str,
    user_id: str,
    client_message_id: str | None = None,
    attachment_ids: list[str] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """执行一轮普通聊天并逐段产出模型文本。"""

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")

    turn_id = client_message_id or f"turn-{uuid4()}"
    sent_at = datetime.now(UTC).isoformat()
    attachments = load_attachments(user_id, attachment_ids)
    config: RunnableConfig = conversation_config(user_id)
    config["recursion_limit"] = 8
    config["tags"] = ["aura", "chat"]
    config["metadata"] = {
        "user_id": user_id,
        "turn_id": turn_id,
        "attachment_count": len(attachments),
    }

    message = HumanMessage(
        id=f"human-{turn_id}",
        content=human_prompt.strip() or "（用户发送了附件）",
        additional_kwargs={
            "turn_id": turn_id,
            "sent_at": sent_at,
            **({"client_message_id": client_message_id} if client_message_id else {}),
            **({"attachments": attachments} if attachments else {}),
        },
    )
    inputs = {
        "messages": [message],
        "user_id": user_id,
        "attachments": attachments,
        "turn_id": turn_id,
    }

    logging.info(
        "Aura 对话开始 user_id=%s message_length=%s attachments=%s",
        user_id,
        len(human_prompt),
        len(attachments),
    )
    for chunk, metadata in agent_runtime.graph.stream(inputs, config, stream_mode="messages"):
        if not stream_node_matches(metadata, "chat"):
            continue
        content = message_content_to_text(getattr(chunk, "content", ""), strip=False)
        if content:
            yield content_event(content)

    logging.info("Aura 对话结束 user_id=%s", user_id)


def stream_node_matches(metadata: dict[str, Any], node_name: str) -> bool:
    """判断流式消息是否来自指定 LangGraph 节点。"""

    current = str(metadata.get("langgraph_node") or "")
    return current == node_name or current.endswith(f":{node_name}")
