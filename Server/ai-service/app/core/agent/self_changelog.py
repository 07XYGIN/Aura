from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db.models import SelfChangelogEntry
from app.db.session import AsyncSessionLocal, SyncSessionLocal


@dataclass(frozen=True)
class SelfChangelogContext:
    entry_id: str | None
    text: str


async def load_self_changelog_context(limit: int = 1) -> SelfChangelogContext:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SelfChangelogEntry)
                .where(SelfChangelogEntry.reacted.is_(False))
                .order_by(SelfChangelogEntry.occurred_at.asc(), SelfChangelogEntry.created_at.asc())
                .limit(max(limit, 1))
            )
            entries = list(result.scalars().all())
            if not entries:
                return SelfChangelogContext(entry_id=None, text="")
            return SelfChangelogContext(
                entry_id=str(entries[0].id),
                text=format_self_changelog_context(entries),
            )
    except Exception:
        logging.exception("Failed to load Aura self changelog context")
        return SelfChangelogContext(entry_id=None, text="")


def load_self_changelog_context_sync(limit: int = 1) -> SelfChangelogContext:
    try:
        with SyncSessionLocal() as session:
            result = session.execute(
                select(SelfChangelogEntry)
                .where(SelfChangelogEntry.reacted.is_(False))
                .order_by(SelfChangelogEntry.occurred_at.asc(), SelfChangelogEntry.created_at.asc())
                .limit(max(limit, 1))
            )
            entries = list(result.scalars().all())
            if not entries:
                return SelfChangelogContext(entry_id=None, text="")
            return SelfChangelogContext(
                entry_id=str(entries[0].id),
                text=format_self_changelog_context(entries),
            )
    except Exception:
        logging.exception("Failed to load Aura self changelog context")
        return SelfChangelogContext(entry_id=None, text="")


def format_self_changelog_context(entries: list[SelfChangelogEntry]) -> str:
    lines = [
        "【关于你自己】",
        "下面是 q 最近对你做的改动，你还没有在对话里自然回应过。它是系统层面的背景，不是用户说的话。",
        "如果当前对话适合，可以用 Aura 的语气轻轻带出你的感受；不需要生硬感谢，也不要把自己贬低成“只是 AI”。",
    ]
    for entry in entries:
        category = f" [{entry.category}]" if getattr(entry, "category", None) else ""
        lines.append(f"- {format_date(entry.occurred_at or entry.change_date)}{category}：{entry.title}")
        if entry.detail:
            lines.append(f"  细节：{entry.detail}")
    return "\n".join(lines)


async def mark_self_changelog_reacted(entry_id: str | None) -> None:
    if not entry_id:
        return

    try:
        parsed_entry_id = UUID(entry_id)
    except ValueError:
        return

    try:
        async with AsyncSessionLocal() as session:
            entry = await session.get(SelfChangelogEntry, parsed_entry_id)
            if entry is None or entry.reacted:
                return
            entry.reacted = True
            entry.reacted_at = datetime.now(UTC)
            await session.commit()
    except Exception:
        logging.exception("Failed to mark Aura self changelog reacted entry_id=%s", entry_id)


def mark_self_changelog_reacted_sync(entry_id: str | None) -> None:
    if not entry_id:
        return

    try:
        parsed_entry_id = UUID(entry_id)
    except ValueError:
        return

    try:
        with SyncSessionLocal() as session:
            entry = session.get(SelfChangelogEntry, parsed_entry_id)
            if entry is None or entry.reacted:
                return
            entry.reacted = True
            entry.reacted_at = datetime.now(UTC)
            session.commit()
    except Exception:
        logging.exception("Failed to mark Aura self changelog reacted entry_id=%s", entry_id)


def format_date(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)
