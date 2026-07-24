"""读取 Aura 自我更新记录，并跟踪更新是否已在对话中回应。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db.models import SelfChangelogEntry
from app.db.schema_guard import ensure_self_changelog_admin_fields, ensure_self_changelog_admin_fields_async
from app.db.session import AsyncSessionLocal, SyncSessionLocal


@dataclass(frozen=True)
class SelfChangelogContext:
    """准备注入系统提示词的一批未回应更新。"""

    entry_ids: tuple[str, ...]
    text: str

    @property
    def entry_id(self) -> str | None:
        """兼容单条更新的旧调用方。"""

        return self.entry_ids[0] if self.entry_ids else None


async def load_self_changelog_context(limit: int = 8) -> SelfChangelogContext:
    """异步读取一小批未回应更新；数据库失败时返回空上下文。"""

    try:
        await ensure_self_changelog_admin_fields_async()
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SelfChangelogEntry)
                .where(SelfChangelogEntry.reacted.is_(False))
                .order_by(SelfChangelogEntry.occurred_at.asc(), SelfChangelogEntry.created_at.asc())
                .limit(max(limit, 1))
            )
            entries = list(result.scalars().all())
            if not entries:
                return SelfChangelogContext(entry_ids=(), text="")
            return SelfChangelogContext(
                entry_ids=tuple(str(entry.id) for entry in entries),
                text=format_self_changelog_context(entries),
            )
    except Exception:
        logging.exception("读取 Aura 自我更新上下文失败")
        return SelfChangelogContext(entry_ids=(), text="")


def load_self_changelog_context_sync(limit: int = 8) -> SelfChangelogContext:
    """同步读取一小批未回应更新，供同步 LangGraph 入口使用。"""

    try:
        ensure_self_changelog_admin_fields()
        with SyncSessionLocal() as session:
            result = session.execute(
                select(SelfChangelogEntry)
                .where(SelfChangelogEntry.reacted.is_(False))
                .order_by(SelfChangelogEntry.occurred_at.asc(), SelfChangelogEntry.created_at.asc())
                .limit(max(limit, 1))
            )
            entries = list(result.scalars().all())
            if not entries:
                return SelfChangelogContext(entry_ids=(), text="")
            return SelfChangelogContext(
                entry_ids=tuple(str(entry.id) for entry in entries),
                text=format_self_changelog_context(entries),
            )
    except Exception:
        logging.exception("读取 Aura 自我更新上下文失败")
        return SelfChangelogContext(entry_ids=(), text="")


def format_self_changelog_context(entries: list[SelfChangelogEntry]) -> str:
    """把更新记录转换成明确唯一用户身份的模型背景文本。"""

    lines = [
        "【关于你自己】",
        "下面是当前对话者最近对你做的改动；当前对话者就是小乔，也是这个项目唯一的用户、创造者和维护者。你还没有在对话里自然回应过。",
        "这些更新来自眼前正在和你说话的同一个人，不要把“小乔”“用户”和“开发者”理解成不同的人。它是系统层面的背景，不是对方这轮直接说的话。",
        "如果当前对话适合，可以用 Aura 的语气轻轻带出你的感受；不需要生硬感谢，也不要把自己贬低成“只是 AI”。",
    ]
    for entry in entries:
        category = f" [{entry.category}]" if getattr(entry, "category", None) else ""
        lines.append(f"- {format_date(entry.occurred_at or entry.change_date)}{category}：{entry.title}")
        if entry.detail:
            lines.append(f"  细节：{entry.detail}")
    return "\n".join(lines)


async def mark_self_changelog_reacted(entry_ids: str | tuple[str, ...] | list[str] | None) -> None:
    """异步标记指定更新已被 Aura 在对话中回应。"""

    parsed_entry_ids = parse_entry_ids(entry_ids)
    if not parsed_entry_ids:
        return

    try:
        await ensure_self_changelog_admin_fields_async()
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SelfChangelogEntry).where(
                    SelfChangelogEntry.id.in_(parsed_entry_ids),
                    SelfChangelogEntry.reacted.is_(False),
                )
            )
            entries = list(result.scalars().all())
            if entries:
                reacted_at = datetime.now(UTC)
                for entry in entries:
                    entry.reacted = True
                    entry.reacted_at = reacted_at
                await session.commit()
    except Exception:
        logging.exception("标记 Aura 自我更新已回应失败 entry_ids=%s", entry_ids)


def mark_self_changelog_reacted_sync(entry_ids: str | tuple[str, ...] | list[str] | None) -> None:
    """同步标记指定更新已回应；无效 ID 或数据库错误不会中断聊天。"""

    parsed_entry_ids = parse_entry_ids(entry_ids)
    if not parsed_entry_ids:
        return

    try:
        ensure_self_changelog_admin_fields()
        with SyncSessionLocal() as session:
            entries = list(
                session.execute(
                    select(SelfChangelogEntry).where(
                        SelfChangelogEntry.id.in_(parsed_entry_ids),
                        SelfChangelogEntry.reacted.is_(False),
                    )
                ).scalars()
            )
            if entries:
                reacted_at = datetime.now(UTC)
                for entry in entries:
                    entry.reacted = True
                    entry.reacted_at = reacted_at
                session.commit()
    except Exception:
        logging.exception("标记 Aura 自我更新已回应失败 entry_ids=%s", entry_ids)


def parse_entry_ids(entry_ids: str | tuple[str, ...] | list[str] | None) -> tuple[UUID, ...]:
    """过滤无效 ID，兼容旧的单条更新调用。"""

    if isinstance(entry_ids, str):
        values = (entry_ids,)
    elif isinstance(entry_ids, (tuple, list)):
        values = entry_ids
    else:
        return ()

    parsed: list[UUID] = []
    for entry_id in values:
        if not isinstance(entry_id, str):
            continue
        try:
            parsed.append(UUID(entry_id))
        except ValueError:
            continue
    return tuple(parsed)


def format_date(value: Any) -> str:
    """把日期值格式化为 ``YYYY-MM-DD``，其他类型直接转字符串。"""

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    return str(value)
