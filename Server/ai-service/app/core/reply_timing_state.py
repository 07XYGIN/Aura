from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.redis_client import delete_key, get_json, set_json

PENDING_BUBBLES_TTL_SECONDS = 30


def pending_bubbles_key(user_id: str) -> str:
    """构造用户待发送消息气泡状态的 Redis 键。"""
    return f"pending_bubbles:{user_id}"


def store_reply_timing_state(user_id: str | None, reply_batch: dict[str, Any]) -> bool:
    """暂存一批回复的发送时序，供客户端或后续请求恢复发送进度。

    Args:
        user_id: 当前用户 ID；为空时不写入。
        reply_batch: 包含消息列表、轮次 ID 和批次 ID 的结构化回复。

    Returns:
        Redis 写入成功返回 ``True``；输入无效或 Redis 不可用时返回 ``False``。

    Side Effects:
        将回复批次写入 Redis，TTL 覆盖总延迟时间并额外保留 30 秒。
    """
    if not user_id:
        return False

    messages = reply_batch.get("messages")
    if not isinstance(messages, list) or not messages:
        return False

    next_send_at = parse_send_timestamp(messages[0].get("sent_at"))
    payload = {
        "user_id": user_id,
        "turn_id": reply_batch.get("turn_id"),
        "batch_id": reply_batch.get("batch_id"),
        "messages": messages,
        "next_send_at": next_send_at,
        "created_at": datetime.now(UTC).isoformat(),
    }
    ttl = max(PENDING_BUBBLES_TTL_SECONDS, total_delay_seconds(messages) + PENDING_BUBBLES_TTL_SECONDS)
    return set_json(pending_bubbles_key(user_id), payload, ex=ttl)


def get_reply_timing_state(user_id: str) -> dict[str, Any] | None:
    """读取用户尚未发送完的回复时序状态。"""
    return get_json(pending_bubbles_key(user_id))


def clear_reply_timing_state(user_id: str) -> bool:
    """删除用户的待发送回复时序状态。"""
    return delete_key(pending_bubbles_key(user_id))


def parse_send_timestamp(value: Any) -> float | None:
    """将 ISO 时间字符串转换为 Unix 时间戳，格式无效时返回 ``None``。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def total_delay_seconds(messages: list[dict[str, Any]]) -> int:
    """汇总消息的非负毫秒延迟并换算为秒，最少返回 1 秒。"""
    total_ms = 0
    for message in messages:
        delay_ms = message.get("delay_ms")
        if isinstance(delay_ms, int):
            total_ms += max(delay_ms, 0)
    return max(1, int(total_ms / 1000))
