from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.redis_client import delete_key, get_json, set_json

PENDING_BUBBLES_TTL_SECONDS = 30


def pending_bubbles_key(user_id: str) -> str:
    return f"pending_bubbles:{user_id}"


def store_reply_timing_state(user_id: str | None, reply_batch: dict[str, Any]) -> bool:
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
    return get_json(pending_bubbles_key(user_id))


def clear_reply_timing_state(user_id: str) -> bool:
    return delete_key(pending_bubbles_key(user_id))


def parse_send_timestamp(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return None


def total_delay_seconds(messages: list[dict[str, Any]]) -> int:
    total_ms = 0
    for message in messages:
        delay_ms = message.get("delay_ms")
        if isinstance(delay_ms, int):
            total_ms += max(delay_ms, 0)
    return max(1, int(total_ms / 1000))
