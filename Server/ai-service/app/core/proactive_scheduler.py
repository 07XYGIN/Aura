from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Iterable
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import (
    AURA_PROACTIVE_SCHEDULER_ENABLED,
    AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS,
    AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS,
)
from app.core.redis_client import get_redis_client, redis_available, safe_redis_call
from app.db.models import ChatMessage, ConversationSession, ProactiveMessage
from app.db.session import AsyncSessionLocal

PROACTIVE_QUEUE_KEY = "proactive_message_queue"
PROACTIVE_ENQUEUE_LIMIT = 200
PROACTIVE_DUE_LIMIT = 50

_scheduler_task: asyncio.Task | None = None


def proactive_score(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def enqueue_proactive_message(message_id: str | UUID, scheduled_at: datetime) -> bool:
    score = proactive_score(scheduled_at)
    return bool(
        safe_redis_call(
            "proactive_zadd",
            False,
            get_redis_client().zadd,
            PROACTIVE_QUEUE_KEY,
            {str(message_id): score},
        )
    )


def enqueue_proactive_messages(messages: Iterable[ProactiveMessage]) -> int:
    mapping = {
        str(message.id): proactive_score(message.scheduled_at)
        for message in messages
        if message.status == "pending" and message.scheduled_at
    }
    if not mapping:
        return 0
    return int(
        safe_redis_call(
            "proactive_zadd_many",
            0,
            get_redis_client().zadd,
            PROACTIVE_QUEUE_KEY,
            mapping,
        )
        or 0
    )


def pop_due_proactive_message_ids(now: datetime | None = None, limit: int = PROACTIVE_DUE_LIMIT) -> list[str]:
    now = now or datetime.now(UTC)
    score = proactive_score(now)
    redis_client = get_redis_client()
    due_ids = safe_redis_call(
        "proactive_zrangebyscore",
        [],
        redis_client.zrangebyscore,
        PROACTIVE_QUEUE_KEY,
        0,
        score,
        start=0,
        num=limit,
    )
    if not due_ids:
        return []

    due_ids = [str(item) for item in due_ids]
    safe_redis_call("proactive_zrem", 0, redis_client.zrem, PROACTIVE_QUEUE_KEY, *due_ids)
    return due_ids


async def enqueue_pending_proactive_messages(
    session: AsyncSession,
    now: datetime | None = None,
    limit: int = PROACTIVE_ENQUEUE_LIMIT,
) -> int:
    now = now or datetime.now(UTC)
    lookahead_at = now + timedelta(hours=AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS)
    result = await session.execute(
        select(ProactiveMessage)
        .where(
            ProactiveMessage.status == "pending",
            ProactiveMessage.scheduled_at <= lookahead_at,
        )
        .order_by(ProactiveMessage.scheduled_at.asc(), ProactiveMessage.created_at.asc())
        .limit(limit)
    )
    return enqueue_proactive_messages(result.scalars().all())


async def process_due_proactive_messages(
    session: AsyncSession,
    message_ids: list[str],
    now: datetime | None = None,
) -> int:
    if not message_ids:
        return 0

    now = now or datetime.now(UTC)
    parsed_ids: list[UUID] = []
    for message_id in message_ids:
        try:
            parsed_ids.append(UUID(str(message_id)))
        except ValueError:
            logging.warning("Ignore invalid proactive message id from Redis: %s", message_id)

    if not parsed_ids:
        return 0

    result = await session.execute(
        select(ProactiveMessage)
        .where(
            ProactiveMessage.id.in_(parsed_ids),
            ProactiveMessage.status == "pending",
            ProactiveMessage.scheduled_at <= now,
        )
        .order_by(ProactiveMessage.scheduled_at.asc())
    )
    messages = result.scalars().all()

    sent_count = 0
    for proactive in messages:
        session_record = ConversationSession(
            id=uuid4(),
            user_id=proactive.user_id,
            channel="proactive",
            title=proactive.title or "Aura 主动消息",
            status="active",
            started_at=now,
            metadata_json={
                "source": "proactive_scheduler",
                "proactive_message_id": str(proactive.id),
                "trigger_type": proactive.trigger_type,
            },
        )
        chat_message = ChatMessage(
            id=uuid4(),
            session_id=session_record.id,
            user_id=proactive.user_id,
            sender_type="assistant",
            sender_id="aura",
            content=proactive.content,
            content_type="text",
            sent_at=now,
            metadata_json={
                "source": "proactive_scheduler",
                "proactive_message_id": str(proactive.id),
                "trigger_type": proactive.trigger_type,
                "scheduled_at": proactive.scheduled_at.isoformat(),
            },
        )
        proactive.status = "sent"
        proactive.sent_at = now
        proactive.updated_at = now
        session.add(session_record)
        session.add(chat_message)
        sent_count += 1

    if sent_count:
        await session.commit()
        logging.info("Proactive scheduler sent %s message(s)", sent_count)
    return sent_count


async def run_proactive_scheduler_tick(now: datetime | None = None) -> int:
    if not redis_available():
        return 0

    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        await enqueue_pending_proactive_messages(session, now=now)
        due_ids = pop_due_proactive_message_ids(now=now)
        return await process_due_proactive_messages(session, due_ids, now=now)


async def proactive_scheduler_loop(stop_event: asyncio.Event) -> None:
    logging.info(
        "Proactive scheduler started interval_seconds=%s",
        AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS,
    )
    while not stop_event.is_set():
        try:
            await run_proactive_scheduler_tick()
        except Exception:
            logging.exception("Proactive scheduler tick failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS)
        except TimeoutError:
            continue
    logging.info("Proactive scheduler stopped")


def start_proactive_scheduler() -> asyncio.Event | None:
    global _scheduler_task

    if not AURA_PROACTIVE_SCHEDULER_ENABLED:
        logging.info("Proactive scheduler disabled by config")
        return None

    if _scheduler_task and not _scheduler_task.done():
        logging.info("Proactive scheduler already running")
        return None

    stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(proactive_scheduler_loop(stop_event))
    return stop_event


async def stop_proactive_scheduler(stop_event: asyncio.Event | None) -> None:
    global _scheduler_task

    if stop_event is not None:
        stop_event.set()
    if _scheduler_task is not None:
        await asyncio.gather(_scheduler_task, return_exceptions=True)
        _scheduler_task = None
