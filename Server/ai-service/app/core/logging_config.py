from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Mapping
from typing import Any

from sqlalchemy import event
from sqlalchemy import inspect as sqlalchemy_inspect

logger = logging.getLogger("aura.dev")
sql_logger = logging.getLogger("aura.sql")
http_logger = logging.getLogger("aura.http")

SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "token",
    "password",
    "dataBase64",
    "data_base64",
}
MAX_VALUE_LENGTH = int(os.getenv("AURA_LOG_VALUE_MAX_LENGTH", "1000"))
MAX_RESULT_ROWS = int(os.getenv("AURA_SQL_RESULT_MAX_ROWS", "50"))


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, os.getenv("AURA_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s.%(msecs)03d %(levelname)-5s [%(name)s] %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def install_sql_logging(async_engine: Any) -> None:
    sync_engine = async_engine.sync_engine
    if getattr(sync_engine, "_aura_sql_logging_installed", False):
        return

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._aura_query_start_time = time.perf_counter()
        sql_logger.info("==> Preparing: %s", normalize_sql(statement))
        sql_logger.info("==> Parameters: %s", to_log_text(sanitize_sql_parameters(statement, parameters)))

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        started_at = getattr(context, "_aura_query_start_time", None)
        elapsed_ms = (time.perf_counter() - started_at) * 1000 if started_at else 0
        rowcount = cursor.rowcount
        sql_logger.info("<== Completed: rowcount=%s elapsed=%.2fms", rowcount, elapsed_ms)

    @event.listens_for(sync_engine, "handle_error")
    def handle_error(exception_context):
        sql_logger.exception(
            "<== SQL Error: statement=%s params=%s",
            normalize_sql(str(exception_context.statement or "")),
            to_log_text(exception_context.parameters),
        )

    setattr(sync_engine, "_aura_sql_logging_installed", True)


def log_sql_result(result: Any, elapsed_ms: float) -> Any:
    try:
        frozen = result.freeze()
    except NotImplementedError:
        sql_logger.info("<== Result: rows unavailable elapsed=%.2fms", elapsed_ms)
        return result

    rows = list(frozen.data)
    preview = rows[:MAX_RESULT_ROWS]
    sql_logger.info(
        "<== Total: %s row(s), preview=%s elapsed=%.2fms",
        len(rows),
        to_log_text(preview),
        elapsed_ms,
    )
    return frozen()


def sanitize_sql_parameters(statement: str, parameters: Any) -> Any:
    if not isinstance(parameters, (list, tuple)):
        return parameters

    sensitive_indexes = sensitive_parameter_indexes(statement)
    if not sensitive_indexes:
        return parameters

    sanitized = list(parameters)
    for index in sensitive_indexes:
        if 0 <= index < len(sanitized):
            sanitized[index] = "***"
    return sanitized


def sensitive_parameter_indexes(statement: str) -> set[int]:
    match = re.search(
        r"INSERT\s+INTO\s+\w+\s*\((?P<columns>[^)]+)\)\s+VALUES",
        statement,
        flags=re.IGNORECASE,
    )
    if not match:
        return set()

    columns = [column.strip().strip('"').split(".")[-1] for column in match.group("columns").split(",")]
    return {index for index, column in enumerate(columns) if column in SENSITIVE_KEYS}


def normalize_sql(statement: str) -> str:
    return " ".join(statement.split())


def to_log_text(value: Any) -> str:
    try:
        return json.dumps(to_log_value(value), ensure_ascii=False, default=str)
    except TypeError:
        return truncate(repr(value))


def to_log_value(value: Any, key: str | None = None) -> Any:
    if key and key in SENSITIVE_KEYS:
        return "***"
    if isinstance(value, Mapping):
        return {str(k): to_log_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_log_value(item) for item in value]
    if hasattr(value, "_mapping"):
        return to_log_value(dict(value._mapping))
    if hasattr(value, "__table__"):
        try:
            mapper = sqlalchemy_inspect(value).mapper
            return {
                attr.columns[0].name: to_log_value(
                    getattr(value, attr.key, None),
                    attr.columns[0].name,
                )
                for attr in mapper.column_attrs
            }
        except Exception:
            return {
                column.name: to_log_value(getattr(value, column.key, None), column.name)
                for column in value.__table__.columns
            }
    if isinstance(value, str):
        return truncate(value)
    return value


def truncate(value: str) -> str:
    if len(value) <= MAX_VALUE_LENGTH:
        return value
    return f"{value[:MAX_VALUE_LENGTH]}...<truncated {len(value) - MAX_VALUE_LENGTH} chars>"
