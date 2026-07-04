from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.agent.tools.term_memory import apply_memory_merge, list_memory_merge_candidates, save_memory

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


@tool
@log_tool
def merge_similar_memories_tool(
    config: RunnableConfig,
    threshold: float = 0.88,
    limit: int = 1,
    scan_limit: int = 120,
    reason: str | None = None,
) -> str:
    """主动整理当前用户的长期记忆：自动扫描高相似记忆，合并为一条，并让合并前的旧记忆退出可检索范围。"""
    configurable: dict[str, Any] = config.get("configurable", {})
    user_id = configurable.get("user_id")
    if not user_id:
        return "缺少用户 ID，无法整理长期记忆。"

    safe_threshold = clamp_float(threshold, default=0.88, minimum=0.8, maximum=0.98)
    safe_limit = clamp_int(limit, default=1, minimum=1, maximum=3)
    safe_scan_limit = clamp_int(scan_limit, default=120, minimum=20, maximum=500)
    clean_reason = clean_text(reason, max_length=120) or "aura_memory_merge_tool"

    try:
        candidates = list_memory_merge_candidates(
            user_id=str(user_id),
            threshold=safe_threshold,
            limit=safe_limit,
            scan_limit=safe_scan_limit,
        )
    except Exception:
        logging.exception("merge_similar_memories_tool scan failed user_id=%s", user_id)
        return "长期记忆整理失败，先不要声称已经整理完成。"

    raw_items = candidates.get("items") if isinstance(candidates, dict) else None
    items = raw_items if isinstance(raw_items, list) else []
    if not items:
        return "没有发现需要合并的高度相似长期记忆。"

    merged_titles: list[str] = []
    skipped_count = 0
    for item in items[:safe_limit]:
        if not isinstance(item, dict):
            skipped_count += 1
            continue

        raw_keys = item.get("memory_keys")
        memory_keys = (
            [key.strip() for key in raw_keys if isinstance(key, str) and key.strip()]
            if isinstance(raw_keys, list)
            else []
        )
        merged_title = clean_text(item.get("suggested_title"), max_length=80) or "合并记忆"
        merged_content = clean_text(item.get("suggested_content"), max_length=520)
        if len(memory_keys) < 2 or not merged_content:
            skipped_count += 1
            continue

        try:
            result = apply_memory_merge(
                user_id=str(user_id),
                memory_keys=memory_keys,
                merged_title=merged_title,
                merged_content=merged_content,
                reason=clean_reason,
                source="memory_merge_tool",
            )
        except Exception:
            logging.exception(
                "merge_similar_memories_tool apply failed user_id=%s memory_keys=%s",
                user_id,
                memory_keys,
            )
            skipped_count += 1
            continue

        merged_from = result.get("merged_from") if isinstance(result, dict) else None
        merged_count = len(merged_from) if isinstance(merged_from, list) else len(memory_keys)
        result_title = result.get("title") if isinstance(result, dict) else merged_title
        title = clean_text(result_title, max_length=80) or merged_title
        merged_titles.append(f"{title}（{merged_count} 条）")

    if not merged_titles:
        return "发现了相似记忆候选，但合并失败，先不要声称已经整理完成。"

    skipped_text = f"；另有 {skipped_count} 组候选未合并" if skipped_count else ""
    return (
        f"已合并 {len(merged_titles)} 组相似长期记忆：{'；'.join(merged_titles)}。"
        f"合并前的旧记忆已标记为已替代，不会再作为可引用长期记忆检索{skipped_text}。"
    )


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


def clamp_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))
