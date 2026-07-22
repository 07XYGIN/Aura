from __future__ import annotations

import logging
from threading import Lock

from sqlalchemy import inspect, text

from app.db.session import engine, sync_engine

SELF_CHANGELOG_TABLE = "self_changelog_entry"

_self_changelog_schema_ready = False
_self_changelog_schema_lock = Lock()


SELF_CHANGELOG_ADMIN_DDL = (
    "ALTER TABLE self_changelog_entry ADD COLUMN IF NOT EXISTS occurred_at timestamptz",
    "UPDATE self_changelog_entry SET occurred_at = change_date::timestamptz WHERE occurred_at IS NULL",
    "ALTER TABLE self_changelog_entry ALTER COLUMN occurred_at SET DEFAULT now()",
    "ALTER TABLE self_changelog_entry ALTER COLUMN occurred_at SET NOT NULL",
    "ALTER TABLE self_changelog_entry ADD COLUMN IF NOT EXISTS category varchar(64) NOT NULL DEFAULT 'infra'",
    "CREATE INDEX IF NOT EXISTS idx_self_changelog_occurred_at ON self_changelog_entry(occurred_at DESC)",
)


def ensure_self_changelog_admin_fields() -> None:
    global _self_changelog_schema_ready
    if _self_changelog_schema_ready:
        return

    with _self_changelog_schema_lock:
        if _self_changelog_schema_ready:
            return

        with sync_engine.begin() as connection:
            if not inspect(connection).has_table(SELF_CHANGELOG_TABLE):
                logging.warning("缺少 self_changelog_entry 表，跳过管理端结构检查")
                return
            for statement in SELF_CHANGELOG_ADMIN_DDL:
                connection.execute(text(statement))

        _self_changelog_schema_ready = True


async def ensure_self_changelog_admin_fields_async() -> None:
    global _self_changelog_schema_ready
    if _self_changelog_schema_ready:
        return

    async with engine.begin() as connection:
        table_exists = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).has_table(SELF_CHANGELOG_TABLE)
        )
        if not table_exists:
            logging.warning("缺少 self_changelog_entry 表，跳过管理端结构检查")
            return
        for statement in SELF_CHANGELOG_ADMIN_DDL:
            await connection.execute(text(statement))

    _self_changelog_schema_ready = True
