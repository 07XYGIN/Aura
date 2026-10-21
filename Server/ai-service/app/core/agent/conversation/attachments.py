"""为当前模型请求准备经过校验的聊天图片内容。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from app.core.attachment_store import load_attachment_data_urls

from .message_utils import message_content_to_text


def add_current_turn_images(
    messages: list,
    *,
    user_id: str,
    attachments: list[dict[str, Any]],
    turn_id: str | None,
) -> list:
    """只把图片数据附加到当前请求，不写入持久化的图状态。"""

    attachment_ids = [
        str(item.get("id") or "")
        for item in attachments[:4]
        if isinstance(item, dict) and item.get("id")
    ]
    if not user_id or not attachment_ids:
        return messages

    try:
        image_data_urls = load_attachment_data_urls(user_id, attachment_ids)
    except Exception:
        logging.exception("Aura 图片附件读取失败，将继续使用文字上下文")
        return messages
    if not image_data_urls:
        return messages

    target_index = None
    fallback_index = None
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if not isinstance(message, HumanMessage):
            continue
        fallback_index = index
        metadata = getattr(message, "additional_kwargs", {}) or {}
        if turn_id and metadata.get("turn_id") == turn_id:
            target_index = index
            break

    if turn_id and target_index is None:
        return messages
    target_index = target_index if target_index is not None else fallback_index
    if target_index is None:
        return messages

    target = messages[target_index]
    text = message_content_to_text(target.content, separator="", strip=False).strip() or "（用户发送了图片）"
    content = [{"type": "text", "text": text}]
    content.extend(
        {"type": "image_url", "image_url": {"url": url}}
        for url in image_data_urls
    )

    # 不把 Base64 图片写入持久化的图状态。
    updated = list(messages)
    updated[target_index] = target.model_copy(update={"content": content})
    return updated
