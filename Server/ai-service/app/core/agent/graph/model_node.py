"""聊天图的模型调用节点实现。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from app.core.config import llm

from ..conversation.attachments import add_current_turn_images
from ..conversation.context import trim_short_term_messages
from ..conversation.reply import (
    build_reply_messages,
    build_reply_messages_from_texts,
    build_structured_reply_response,
    message_content_to_text,
)
from ..reliability import invoke_model_with_retry
from ..schemas.structured_reply import try_parse_structured_reply_payload
from .runtime_prompt import build_runtime_system_prompt


def generate_chat_response(state: dict[str, Any]) -> dict[str, Any]:
    """调用模型并整理本轮回复。"""

    system_prompt = build_runtime_system_prompt(state)
    messages = [SystemMessage(content=system_prompt)] + trim_short_term_messages(state["messages"])
    messages = add_current_turn_images(
        messages,
        user_id=str(state.get("user_id") or ""),
        attachments=state.get("attachments", []),
        turn_id=state.get("turn_id"),
    )
    try:
        response = invoke_model_with_retry(llm.invoke, messages, operation="主对话")
    except Exception:
        logging.exception("Aura 主模型在重试后仍不可用，返回安全降级回复")
        response = AIMessage(
            content='{"messages":["我这边刚刚没有接上，等一下再试一次。"]}'
        )

    draft_content = message_content_to_text(getattr(response, "content", ""))
    parsed_payload = try_parse_structured_reply_payload(draft_content)
    if parsed_payload is not None:
        reply_messages, reply_batch = build_reply_messages_from_texts(parsed_payload.messages, response, state)
    else:
        logging.warning("Aura 首次回复不是有效的结构化 JSON，尝试重新整理格式")
        structured_response = build_structured_reply_response(response, messages, state)
        reply_messages, reply_batch = build_reply_messages(structured_response, state)
        parsed_payload = try_parse_structured_reply_payload(
            message_content_to_text(getattr(structured_response, "content", ""))
        )

    return {
        "messages": reply_messages,
        "last_reply_batch": reply_batch,
    }
