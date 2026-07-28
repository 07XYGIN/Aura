"""模型调用的有限重试与降级支持。"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import Any, TypeVar


T = TypeVar("T")


def model_max_attempts() -> int:
    """读取主模型调用最大尝试次数，默认首调加一次重试。"""

    try:
        return max(1, min(int(os.getenv("AURA_MODEL_MAX_ATTEMPTS", "2")), 4))
    except ValueError:
        return 2


def model_retry_delay_seconds(attempt: int) -> float:
    """生成上限很低的指数退避，避免单次聊天被长时间挂起。"""

    try:
        base = max(0.05, min(float(os.getenv("AURA_MODEL_RETRY_BASE_SECONDS", "0.35")), 3.0))
    except ValueError:
        base = 0.35
    return min(base * (2 ** max(0, attempt - 1)), 3.0)


def invoke_model_with_retry(
    invoke: Callable[[list], T],
    messages: list,
    *,
    operation: str,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """仅为可恢复的网络或服务端失败重试模型调用。"""

    attempts = model_max_attempts()
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return invoke(messages)
        except Exception as exc:
            last_error = exc
            if attempt >= attempts or not is_retryable_model_error(exc):
                raise
            delay = model_retry_delay_seconds(attempt)
            logging.warning(
                "Aura 模型调用失败，准备重试 operation=%s attempt=%s/%s delay_seconds=%.2f error=%s",
                operation,
                attempt,
                attempts,
                delay,
                type(exc).__name__,
            )
            sleep(delay)

    assert last_error is not None
    raise last_error


def is_retryable_model_error(error: Exception) -> bool:
    """避免对明确的 4xx 请求错误盲目重放。"""

    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    status_code = getattr(error, "status_code", None) or getattr(error, "status", None)
    if isinstance(status_code, int):
        return status_code in {408, 409, 429} or status_code >= 500
    return True
