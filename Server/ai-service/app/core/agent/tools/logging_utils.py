from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, TypeVar, cast


TFunc = TypeVar("TFunc", bound=Callable[..., Any])


def log_tool(func: TFunc) -> TFunc:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        logging.info("调用聊天工具 tool=%s", func.__name__)
        try:
            result = func(*args, **kwargs)
        except Exception:
            logging.exception("聊天工具调用失败 tool=%s", func.__name__)
            raise

        logging.info("聊天工具调用完成 tool=%s", func.__name__)
        return result

    return cast(TFunc, wrapper)
