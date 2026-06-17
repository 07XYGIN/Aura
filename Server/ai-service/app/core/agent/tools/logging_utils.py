from __future__ import annotations

import json
import logging
from functools import wraps
from typing import Any, Callable, TypeVar, cast


TFunc = TypeVar("TFunc", bound=Callable[..., Any])


def _preview(value: Any, limit: int = 800) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = repr(value)

    if len(text) > limit:
        return text[:limit] + "..."
    return text


def log_tool(func: TFunc) -> TFunc:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        logging.info(
            "命中 %s tool args=%s kwargs=%s",
            func.__name__,
            _preview(args),
            _preview(kwargs),
        )
        try:
            result = func(*args, **kwargs)
        except Exception:
            logging.exception(
                "%s tool failed args=%s kwargs=%s",
                func.__name__,
                _preview(args),
                _preview(kwargs),
            )
            raise

        logging.info("%s tool result=%s", func.__name__, _preview(result))
        return result

    return cast(TFunc, wrapper)
