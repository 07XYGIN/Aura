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
    """创建并缓存全局 Redis 客户端。

    Returns:
        使用字符串响应和较短超时配置的同步 Redis 客户端。
    """
    return Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        protocol=2,
        socket_connect_timeout=0.2,
        socket_timeout=0.5,
    )


def redis_available() -> bool:
    """通过 PING 检查 Redis 是否可用；连接失败时返回 ``False``。"""
    try:
        return bool(get_redis_client().ping())
    except RedisError:
        logging.warning("Redis 当前不可用，回退到本地流程", exc_info=True)
        return False


def safe_redis_call(operation: str, default: Any, func, *args, **kwargs):
    """执行一次 Redis 操作，并在 Redis 异常时记录日志、返回降级值。

    Args:
        operation: 用于日志定位的操作名称。
        default: Redis 操作失败时返回的值。
        func: 要调用的 Redis 方法或封装函数。
        *args: 传给 ``func`` 的位置参数。
        **kwargs: 传给 ``func`` 的关键字参数。

    Returns:
        Redis 操作结果；发生 ``RedisError`` 时返回 ``default``。
    """
    try:
        return func(*args, **kwargs)
    except RedisError:
        logging.warning("Redis 操作失败 operation=%s", operation, exc_info=True)
        return default


def set_json(key: str, value: dict[str, Any], ex: int) -> bool:
    """将字典序列化为 JSON 后写入 Redis，并设置秒级过期时间。"""
    payload = json.dumps(value, ensure_ascii=False, default=str)
    return bool(safe_redis_call("set_json", False, get_redis_client().set, key, payload, ex=ex))


def get_json(key: str) -> dict[str, Any] | None:
    """读取 Redis 中的 JSON 对象；键不存在、内容无效或不是对象时返回 ``None``。"""
    raw = safe_redis_call("get_json", None, get_redis_client().get, key)
    if not isinstance(raw, str) or not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def delete_key(key: str) -> bool:
    """删除一个 Redis 键，并返回是否实际删除了数据。"""
    return bool(safe_redis_call("delete_key", 0, get_redis_client().delete, key))
