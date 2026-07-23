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
    """构造用户最后发言时间的 Redis 键。"""
    return f"{LAST_USER_MESSAGE_PREFIX}{user_id}"


def proactive_triggered_key(user_id: str) -> str:
    """构造用户本轮沉默问候已触发标记的 Redis 键。"""
    return f"{PROACTIVE_TRIGGERED_PREFIX}{user_id}"


def _redis_temporarily_disabled() -> bool:
    """判断沉默状态模块是否仍处于 Redis 熔断窗口。"""
    return time.monotonic() < _redis_disabled_until


def _disable_redis_temporarily() -> None:
    """Redis 写入失败后开启短暂熔断，避免每条消息重复等待连接超时。"""
    global _redis_disabled_until
    _redis_disabled_until = time.monotonic() + REDIS_RETRY_AFTER_FAILURE_SECONDS


def _redis_client_or_none() -> Redis | None:
    """在非熔断状态下获取 Redis 客户端，初始化失败时返回 ``None``。"""
    if _redis_temporarily_disabled():
        return None
    try:
        return get_redis_client()
    except Exception:
        logging.warning("沉默状态所需的 Redis 客户端初始化失败", exc_info=True)
        return None


def record_user_message_activity(user_id: str, timestamp: float | None = None) -> bool:
    """记录用户最后发言时间，并清除上一轮沉默问候标记。

    Args:
        user_id: 要更新活跃状态的用户 ID。
        timestamp: 可选 Unix 时间戳；未提供时使用当前时间。

    Returns:
        最后发言时间成功写入 Redis 时返回 ``True``，否则返回 ``False``。

    Side Effects:
        写入最后发言时间、删除主动问候标记；写入失败时暂时熔断 Redis。
    """
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
    """调度用户活跃时间记录，事件循环存在时在线程池中异步执行。

    没有运行中的事件循环时会同步写入；Redis 熔断期间直接跳过。
    """
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
    """消费后台记录任务的结果，避免未处理异常并写入告警日志。"""
    try:
        future.result()
    except Exception:
        logging.warning("后台记录用户活跃时间失败", exc_info=True)


def list_tracked_silence_user_ids() -> list[str]:
    """扫描 Redis 中有最后发言记录的用户 ID 列表。"""
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
    """读取用户最后发言的 Unix 时间戳；缺失或格式无效时返回 ``None``。"""
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
    """判断用户自上次发言后是否已经触发过沉默问候。"""
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
    """将用户标记为本轮沉默问候已触发，并返回 Redis 写入结果。"""
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
