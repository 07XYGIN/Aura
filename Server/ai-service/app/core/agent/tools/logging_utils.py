"""聊天 Tool 的统一中文日志装饰器。"""

from __future__ import annotations

import logging
import hashlib
import json
from time import monotonic
from urllib.parse import urlsplit
from functools import wraps
from typing import Any, Callable, TypeVar, cast


TFunc = TypeVar("TFunc", bound=Callable[..., Any])


def log_world_call(tool_name: str, value: str, started: float, result: dict) -> None:
    """Log bounded metadata, not page bodies, URL tokens or private queries."""
    fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    try:
        host = urlsplit(value).hostname if tool_name == "fetch_url" else None
    except ValueError:
        host = None
    logging.info("world_tool %s", json.dumps({
        "tool_name": tool_name, "query_or_url_hash": fingerprint,
        "url_host": (host or "")[:200], "input_length": len(value),
        "duration_ms": round((monotonic() - started) * 1000),
        "success": result.get("ok", False),
        "result_count": len(result.get("results", [])) if tool_name == "search_web" else int(result.get("ok") is True),
        "error_type": result.get("error", {}).get("code"),
    }, ensure_ascii=False))


def log_tool(func: TFunc) -> TFunc:
    """记录工具开始、成功和失败，但不输出可能含隐私的参数或结果。"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        """执行被装饰工具并保留原始返回值和异常。"""

        logging.info("调用聊天工具 tool=%s", func.__name__)
        try:
            result = func(*args, **kwargs)
        except Exception:
            logging.exception("聊天工具调用失败 tool=%s", func.__name__)
            raise

        logging.info("聊天工具调用完成 tool=%s", func.__name__)
        return result

    return cast(TFunc, wrapper)
