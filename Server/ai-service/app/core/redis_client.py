from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import REDIS_URL


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    return Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.5,
    )


def redis_available() -> bool:
    try:
        return bool(get_redis_client().ping())
    except RedisError:
        logging.warning("Redis is unavailable; falling back to local flow", exc_info=True)
        return False


def safe_redis_call(operation: str, default: Any, func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except RedisError:
        logging.warning("Redis operation failed operation=%s", operation, exc_info=True)
        return default


def set_json(key: str, value: dict[str, Any], ex: int) -> bool:
    payload = json.dumps(value, ensure_ascii=False, default=str)
    return bool(safe_redis_call("set_json", False, get_redis_client().set, key, payload, ex=ex))


def get_json(key: str) -> dict[str, Any] | None:
    raw = safe_redis_call("get_json", None, get_redis_client().get, key)
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def delete_key(key: str) -> bool:
    return bool(safe_redis_call("delete_key", 0, get_redis_client().delete, key))
