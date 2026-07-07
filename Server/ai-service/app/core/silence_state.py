from __future__ import annotations

import asyncio
import logging
import time

from redis import Redis

from app.core.redis_client import get_redis_client, safe_redis_call

LAST_USER_MESSAGE_PREFIX = "last_user_message:"
PROACTIVE_TRIGGERED_PREFIX = "proactive_triggered:"
REDIS_RETRY_AFTER_FAILURE_SECONDS = 30

_redis_disabled_until = 0.0


def last_user_message_key(user_id: str) -> str:
    return f"{LAST_USER_MESSAGE_PREFIX}{user_id}"


def proactive_triggered_key(user_id: str) -> str:
    return f"{PROACTIVE_TRIGGERED_PREFIX}{user_id}"


def _redis_temporarily_disabled() -> bool:
    return time.monotonic() < _redis_disabled_until


def _disable_redis_temporarily() -> None:
    global _redis_disabled_until
    _redis_disabled_until = time.monotonic() + REDIS_RETRY_AFTER_FAILURE_SECONDS


def _redis_client_or_none() -> Redis | None:
    if _redis_temporarily_disabled():
        return None
    try:
        return get_redis_client()
    except Exception:
        logging.warning("Redis client initialization failed for silence state", exc_info=True)
        return None


def record_user_message_activity(user_id: str, timestamp: float | None = None) -> bool:
    normalized_user_id = str(user_id or "").strip()
    if not normalized_user_id:
        return False

    redis_client = _redis_client_or_none()
    if redis_client is None:
        return False

    last_message_at = time.time() if timestamp is None else float(timestamp)
    stored = bool(
        safe_redis_call(
            "last_user_message_set",
            False,
            redis_client.set,
            last_user_message_key(normalized_user_id),
            str(last_message_at),
        )
    )
    if not stored:
        _disable_redis_temporarily()
        return False

    safe_redis_call(
        "proactive_triggered_delete",
        0,
        redis_client.delete,
        proactive_triggered_key(normalized_user_id),
    )
    return stored


def schedule_user_message_activity_record(user_id: str, timestamp: float | None = None) -> None:
    if _redis_temporarily_disabled():
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        record_user_message_activity(user_id, timestamp)
        return

    future = loop.run_in_executor(None, record_user_message_activity, user_id, timestamp)
    future.add_done_callback(_log_background_record_error)


def _log_background_record_error(future) -> None:
    try:
        future.result()
    except Exception:
        logging.warning("Background silence activity record failed", exc_info=True)


def list_tracked_silence_user_ids() -> list[str]:
    redis_client = _redis_client_or_none()
    if redis_client is None:
        return []

    pattern = f"{LAST_USER_MESSAGE_PREFIX}*"
    keys = safe_redis_call(
        "last_user_message_scan",
        [],
        lambda: list(redis_client.scan_iter(match=pattern)),
    )
    user_ids: list[str] = []
    for key in keys or []:
        key_text = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        if key_text.startswith(LAST_USER_MESSAGE_PREFIX):
            user_ids.append(key_text.removeprefix(LAST_USER_MESSAGE_PREFIX))
    return user_ids


def get_last_user_message_timestamp(user_id: str) -> float | None:
    redis_client = _redis_client_or_none()
    if redis_client is None:
        return None

    raw_value = safe_redis_call(
        "last_user_message_get",
        None,
        redis_client.get,
        last_user_message_key(user_id),
    )
    if raw_value is None or raw_value == "":
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def silence_proactive_already_triggered(user_id: str) -> bool:
    redis_client = _redis_client_or_none()
    if redis_client is None:
        return False

    return bool(
        safe_redis_call(
            "proactive_triggered_get",
            None,
            redis_client.get,
            proactive_triggered_key(user_id),
        )
    )


def mark_silence_proactive_triggered(user_id: str) -> bool:
    redis_client = _redis_client_or_none()
    if redis_client is None:
        return False

    return bool(
        safe_redis_call(
            "proactive_triggered_set",
            False,
            redis_client.set,
            proactive_triggered_key(user_id),
            "1",
        )
    )
