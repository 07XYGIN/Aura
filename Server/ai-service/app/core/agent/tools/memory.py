from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.memory.service import save_memory

from .logging_utils import log_tool


@tool
@log_tool
def save_memory_tool(
    title: str,
    content: str,
    memory_scope: Literal["long", "mid"],
    config: RunnableConfig,
    confidence: float = 0.8,
    reason: str | None = None,
    signals: list[str] | None = None,
) -> str:
    """保存当前用户以后确实需要继续使用的信息。

    用户明确要求记住，或内容属于稳定偏好、边界、重要事实、共同事件和近期待跟进事项时调用。
    普通闲聊、一次性情绪、模型猜测和工具结果不要保存。
    """
    configurable: dict[str, Any] = config.get("configurable", {})
    user_id = configurable.get("user_id")
    if not user_id:
        return "缺少用户 ID，无法保存记忆。"

    clean_title = clean_text(title, 80) or ("对话记忆" if memory_scope == "long" else "近期线索")
    clean_content = clean_text(content, 320)
    if not clean_content:
        return "缺少有效记忆内容，未保存。"

    try:
        saved_key = save_memory(
            user_id=str(user_id),
            content=clean_content,
            title=clean_title,
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            memory_scope=memory_scope,
            confidence=clamp_confidence(confidence),
            signals=clean_signal_list(signals),
            extra_metadata={
                "source": "save_memory_tool",
                "reason": clean_text(reason, 120),
            },
        )
    except Exception:
        logging.exception("保存记忆失败 user_id=%s title=%s", user_id, clean_title)
        return "记忆保存失败，先不要声称已经记住。"

    if not saved_key:
        return "这条内容没有形成新的有效记忆，先不要声称已经保存。"
    scope_label = "长期" if memory_scope == "long" else "近期"
    return f"已保存{scope_label}记忆：{clean_title}。"


def clean_text(value: Any, max_length: int) -> str:
    return value.strip()[:max_length] if isinstance(value, str) else ""


def clean_signal_list(value: list[str] | None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip()[:40] for item in value if isinstance(item, str) and item.strip()][:8]


def clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.8
    return max(0.0, min(1.0, number))
