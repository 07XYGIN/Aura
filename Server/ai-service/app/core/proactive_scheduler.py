from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Iterable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.tools.proactive import build_proactive_message_draft
from app.core.config import (
    AURA_PROACTIVE_SCHEDULER_ENABLED,
    AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS,
    AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS,
)
from app.core.redis_client import get_redis_client, redis_available, safe_redis_call
from app.core.silence_state import (
    get_last_user_message_timestamp,
    list_tracked_silence_user_ids,
    mark_silence_proactive_triggered,
    silence_proactive_already_triggered,
)
from app.db.models import ChatMessage, ConversationSession, ProactiveMessage
from app.db.session import AsyncSessionLocal

PROACTIVE_QUEUE_KEY = "proactive_message_queue"
PROACTIVE_ENQUEUE_LIMIT = 200
PROACTIVE_DUE_LIMIT = 50
SILENCE_TRIGGER_TYPE = "silence"
SILENCE_THRESHOLD_SECONDS = 8 * 3600
SILENCE_TIMEZONE = ZoneInfo("Asia/Shanghai")
SILENCE_DEEP_NIGHT_START_HOUR = 1
SILENCE_DEEP_NIGHT_END_HOUR = 7
SILENCE_CONTEXT_MESSAGE_LIMIT = 6
SILENCE_CONTEXT_MAX_LENGTH = 160

_scheduler_task: asyncio.Task | None = None


def proactive_score(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def is_deep_night(now: datetime, timezone: ZoneInfo = SILENCE_TIMEZONE) -> bool:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    local_now = now.astimezone(timezone)
    hour = local_now.hour
    if SILENCE_DEEP_NIGHT_START_HOUR < SILENCE_DEEP_NIGHT_END_HOUR:
        return SILENCE_DEEP_NIGHT_START_HOUR <= hour < SILENCE_DEEP_NIGHT_END_HOUR
    return hour >= SILENCE_DEEP_NIGHT_START_HOUR or hour < SILENCE_DEEP_NIGHT_END_HOUR


def collect_due_silence_user_ids(
    now: datetime | None = None,
    threshold_seconds: int = SILENCE_THRESHOLD_SECONDS,
) -> list[str]:
    now = now or datetime.now(UTC)
    if is_deep_night(now):
        return []

    now_timestamp = proactive_score(now)
    due_user_ids: list[str] = []
    for user_id in list_tracked_silence_user_ids():
        last_timestamp = get_last_user_message_timestamp(user_id)
        if last_timestamp is None:
            continue
        if now_timestamp - last_timestamp <= threshold_seconds:
            continue
        if silence_proactive_already_triggered(user_id):
            continue
        due_user_ids.append(user_id)
    return due_user_ids


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


async def build_recent_conversation_context(
    session: AsyncSession,
    user_id: UUID,
    limit: int = SILENCE_CONTEXT_MESSAGE_LIMIT,
) -> str:
    result = await session.execute(
        select(ChatMessage.sender_type, ChatMessage.content)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    rows = list(result.all())
    parts: list[str] = []
    for sender_type, content in reversed(rows):
        text = " ".join(str(content or "").split())
        if not text:
            continue
        role = "用户" if sender_type == "user" else "Aura"
        parts.append(f"{role}: {text[:80]}")
    return " / ".join(parts)[:SILENCE_CONTEXT_MAX_LENGTH]


async def trigger_silence_proactive_messages(
    session: AsyncSession,
    user_ids: list[str],
    now: datetime | None = None,
) -> int:
    if not user_ids:
        return 0

    now = now or datetime.now(UTC)
    messages: list[ProactiveMessage] = []
    user_ids_to_mark: list[str] = []
    for user_id_value in user_ids:
        try:
            user_id = UUID(str(user_id_value))
        except ValueError:
            logging.warning("Ignore invalid silence proactive user id from Redis: %s", user_id_value)
            continue

        user_context = await build_recent_conversation_context(session, user_id)
        draft = build_proactive_message_draft(SILENCE_TRIGGER_TYPE, user_context)
        if not draft.get("should_send", True):
            continue

        content = str(draft.get("content") or "").strip()
        if not content:
            continue

        proactive = ProactiveMessage(
            id=uuid4(),
            user_id=user_id,
            trigger_type=SILENCE_TRIGGER_TYPE,
            title="Aura 主动问候",
            content=content,
            scheduled_at=now,
            status="pending",
            metadata_json={
                "source": "silence_scheduler",
                "trigger_type": SILENCE_TRIGGER_TYPE,
                "context": user_context,
                "tone": draft.get("tone"),
            },
        )
        session.add(proactive)
        messages.append(proactive)
        user_ids_to_mark.append(str(user_id_value))

    if not messages:
        return 0

    await session.flush()
    sent_count = await send_proactive_message_records(session, messages, now=now)
    if sent_count:
        for user_id in user_ids_to_mark:
            mark_silence_proactive_triggered(user_id)
    return sent_count


async def send_proactive_message_records(
    session: AsyncSession,
    messages: Iterable[ProactiveMessage],
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
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
            is_proactive=True,
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

    return await send_proactive_message_records(session, messages, now=now)


async def run_proactive_scheduler_tick(now: datetime | None = None) -> int:
    if not redis_available():
        return 0

    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        silence_user_ids = collect_due_silence_user_ids(now=now)
        silence_sent_count = await trigger_silence_proactive_messages(session, silence_user_ids, now=now)
        await enqueue_pending_proactive_messages(session, now=now)
        due_ids = pop_due_proactive_message_ids(now=now)
        scheduled_sent_count = await process_due_proactive_messages(session, due_ids, now=now)
        return silence_sent_count + scheduled_sent_count


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
