"""聊天图的模型调用节点实现。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from app.core.config import llm

from ..conversation.attachments import add_current_turn_images
from ..conversation.context import trim_short_term_messages
from .runtime_prompt import build_runtime_system_prompt


def generate_chat_response(state: dict[str, Any]) -> dict[str, Any]:
    """调用一次聊天模型并把原始回复写回图状态。"""

    messages = [SystemMessage(content=build_runtime_system_prompt(state))]
    messages.extend(trim_short_term_messages(state["messages"]))
    messages = add_current_turn_images(
        messages,
        user_id=str(state.get("user_id") or ""),
        attachments=state.get("attachments", []),
        turn_id=state.get("turn_id"),
    )
    try:
        response = llm.invoke(messages)
    except Exception:
        logging.exception("Aura 主模型调用失败")
        response = AIMessage(content="模型暂时无法回复，请稍后再试。")

    return {"messages": [response]}
