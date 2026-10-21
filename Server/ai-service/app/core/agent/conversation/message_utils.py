"""LangChain 消息内容的共享转换工具。"""

from __future__ import annotations

from typing import Any


def message_content_to_text(
    content: Any,
    *,
    separator: str = "\n",
    strip: bool = True,
) -> str:
    """把 LangChain 字符串或内容块转换为文本，并保留调用方所需格式。"""

    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
            elif isinstance(item, str):
                parts.append(item)
        text = separator.join(parts)
    else:
        text = str(content or "")
    return text.strip() if strip else text
