from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.agent.tools.term_memory import save_memory

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
    """保存用户明确值得记住的信息到长期或中期记忆库；content 要简洁但保留场景、心情或具体情境。"""
    configurable: dict[str, Any] = config.get("configurable", {})
    user_id = configurable.get("user_id")
    if not user_id:
        return "缺少用户 ID，无法保存记忆。"

    clean_title = clean_text(title, max_length=80) or ("对话记忆" if memory_scope == "long" else "近期线索")
    clean_content = clean_text(content, max_length=320)
    if not clean_content:
        return "缺少有效记忆内容，未保存。"

    clean_reason = clean_text(reason, max_length=120)
    clean_signals = clean_signal_list(signals)

    try:
        memory_key = save_memory(
            user_id=str(user_id),
            content=clean_content,
            title=clean_title,
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            memory_scope=memory_scope,
            confidence=clamp_confidence(confidence),
            signals=clean_signals,
            extra_metadata={
                "source": "save_memory_tool",
                "reason": clean_reason,
            },
        )
    except Exception:
        logging.exception("save_memory_tool failed user_id=%s title=%s", user_id, clean_title)
        return "记忆保存失败，先不要声称已经记住。"

    scope_label = "长期" if memory_scope == "long" else "中期"
    return f"已保存{scope_label}记忆：{clean_title}（memory_key={memory_key}）"


def clean_text(value: Any, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def clean_signal_list(value: list[str] | None) -> list[str]:
    if not isinstance(value, list):
        return []
    signals: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        signal = item.strip()[:40]
        if signal:
            signals.append(signal)
    return signals[:8]


def clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.8
    return max(0.0, min(1.0, number))
