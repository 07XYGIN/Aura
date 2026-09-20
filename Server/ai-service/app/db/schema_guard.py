from __future__ import annotations

from threading import Lock

from sqlalchemy import inspect

from app.db.session import engine, sync_engine
from app.db.models import SelfChangelogEntry

SELF_CHANGELOG_TABLE = "self_changelog_entry"

_self_changelog_schema_ready = False
_self_changelog_schema_lock = Lock()


def validate_self_changelog_fields(connection) -> None:
    """Legacy callers validate only; all schema mutations belong to migrations."""
    inspector = inspect(connection)
    if not inspector.has_table(SELF_CHANGELOG_TABLE):
        raise RuntimeError("缺少 self_changelog_entry 表；请先初始化数据库并执行迁移")
    actual = {column["name"] for column in inspector.get_columns(SELF_CHANGELOG_TABLE)}
    missing = set(SelfChangelogEntry.__table__.columns.keys()) - actual
    if missing:
        raise RuntimeError(f"self_changelog_entry 缺少字段 {sorted(missing)}；请执行数据库迁移")


def ensure_self_changelog_admin_fields() -> None:
    """Validate legacy callers without changing schema during a request."""
    global _self_changelog_schema_ready
    if _self_changelog_schema_ready:
        return

    with _self_changelog_schema_lock:
        if _self_changelog_schema_ready:
            return

        with sync_engine.connect() as connection:
            validate_self_changelog_fields(connection)

        _self_changelog_schema_ready = True


async def ensure_self_changelog_admin_fields_async() -> None:
    """Async validation; schema changes must be applied through Alembic."""
    global _self_changelog_schema_ready
    if _self_changelog_schema_ready:
        return

    async with engine.connect() as connection:
        await connection.run_sync(validate_self_changelog_fields)

    _self_changelog_schema_ready = True
