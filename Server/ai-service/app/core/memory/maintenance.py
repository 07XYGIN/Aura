from __future__ import annotations

from typing import Any, Literal

from .service import (
    apply_memory_merge,
    list_memory_merge_candidates,
    list_topic_memory_merge_candidates,
)


def merge_memories(
    user_id: str,
    *,
    mode: Literal["deduplicate", "topic"] = "deduplicate",
    topic: str | None = None,
    threshold: float | None = None,
    limit: int = 1,
    scan_limit: int | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """后台或管理端执行记忆整理；不允许普通聊天模型自行扫描和修改记忆库。"""
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        raise ValueError("缺少用户 ID，无法整理记忆")

    clean_mode = mode if mode in {"deduplicate", "topic"} else "deduplicate"
    clean_topic = clean_text(topic, 120)
    if clean_mode == "topic" and not clean_topic:
        raise ValueError("按主题整理记忆时必须提供明确主题")

    safe_threshold = (
        clamp_float(threshold, 0.52, 0.35, 0.9)
        if clean_mode == "topic"
        else clamp_float(threshold, 0.85, 0.8, 0.98)
    )
    safe_limit = clamp_int(limit, 1, 1, 3)
    safe_scan_limit = (
        clamp_int(scan_limit, 20, 2, 80)
        if clean_mode == "topic"
        else clamp_int(scan_limit, 120, 20, 500)
    )

    if clean_mode == "topic":
        candidates = list_topic_memory_merge_candidates(
            user_id=normalized_user_id,
            topic_query=clean_topic,
            threshold=safe_threshold,
            limit=safe_limit,
            scan_limit=safe_scan_limit,
        )
    else:
        candidates = list_memory_merge_candidates(
            user_id=normalized_user_id,
            threshold=safe_threshold,
            limit=safe_limit,
            scan_limit=safe_scan_limit,
        )

    items = candidates.get("items") if isinstance(candidates, dict) else []
    merged: list[dict[str, Any]] = []
    skipped = 0
    for item in items[:safe_limit] if isinstance(items, list) else []:
        if not isinstance(item, dict):
            skipped += 1
            continue
        keys = [key.strip() for key in item.get("memory_keys", []) if isinstance(key, str) and key.strip()]
        title = clean_text(item.get("suggested_title"), 80) or "合并记忆"
        content = clean_text(item.get("suggested_content"), 520)
        if len(keys) < 2 or not content:
            skipped += 1
            continue
        merged.append(
            apply_memory_merge(
                user_id=normalized_user_id,
                memory_keys=keys,
                merged_title=title,
                merged_content=content,
                reason=clean_text(reason, 120) or "后台整理记忆",
                source="memory_maintenance",
            )
        )

    return {
        "mode": clean_mode,
        "topic": clean_topic or None,
        "merged": merged,
        "mergedCount": len(merged),
        "skippedCount": skipped,
    }


def clean_text(value: Any, max_length: int) -> str:
    return value.strip()[:max_length] if isinstance(value, str) else ""


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
