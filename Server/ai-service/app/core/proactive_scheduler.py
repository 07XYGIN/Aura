from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Iterable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.agent_graph import append_proactive_history_message, get_history
from app.core.proactive.service import (
    DAILY_GREETING_WINDOWS,
    EVENING_TRIGGER_TYPE,
    MORNING_TRIGGER_TYPE,
    build_daily_greeting_plan,
    draft_proactive_message_with_llm,
)
from app.core.agent.tools.weather import fetch_weather
from app.core.config import (
    AURA_CITY_ADCODE,
    AURA_PROACTIVE_SCHEDULER_ENABLED,
    AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS,
    AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS,
    AURA_TIMEZONE,
)
from app.core.redis_client import get_redis_client, redis_available, safe_redis_call
from app.core.silence_state import (
    get_last_user_message_timestamp,
    list_tracked_silence_user_ids,
    mark_silence_proactive_triggered,
    silence_proactive_already_triggered,
)
from app.db.models import ProactiveMessage, Users
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
DAILY_GREETING_USER_LIMIT = 500
DAILY_GREETING_PLACEHOLDER = "Aura 正在准备这条主动问候。"
DAILY_GREETING_TRIGGER_TYPES = {MORNING_TRIGGER_TYPE, EVENING_TRIGGER_TYPE}
DEFAULT_DAILY_GREETING_TIMEZONE = AURA_TIMEZONE
DAILY_GREETING_STALE_GRACE_SECONDS = 15 * 60

_scheduler_task: asyncio.Task | None = None


def proactive_score(value: datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_stale_daily_greeting(proactive: ProactiveMessage, now: datetime) -> bool:
    if proactive.trigger_type not in DAILY_GREETING_TRIGGER_TYPES:
        return False
    allowed_lag = timedelta(
        seconds=max(AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS, 60)
        + DAILY_GREETING_STALE_GRACE_SECONDS
    )
    return normalize_utc(proactive.scheduled_at) < normalize_utc(now) - allowed_lag


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
    logging.info('定时任务 执行 collect_due_silence_user_ids')
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
    _session: AsyncSession,
    user_id: UUID,
    limit: int = SILENCE_CONTEXT_MESSAGE_LIMIT,
) -> str:
    rows = await asyncio.to_thread(get_history, str(user_id))
    parts: list[str] = []
    for item in rows[-limit:]:
        sender_type = str(item.get("role") or "")
        content = item.get("content")
        text = " ".join(str(content or "").split())
        if not text:
            continue
        role = "用户" if sender_type in {"user", "human"} else "Aura"
        parts.append(f"{role}: {text[:80]}")
    return " / ".join(parts)[:SILENCE_CONTEXT_MAX_LENGTH]


def resolve_daily_greeting_timezone(timezone: str | None) -> tuple[ZoneInfo, str]:
    timezone_name = (timezone or DEFAULT_DAILY_GREETING_TIMEZONE).strip() or DEFAULT_DAILY_GREETING_TIMEZONE
    try:
        return ZoneInfo(timezone_name), timezone_name
    except Exception:
        logging.warning("主动问候时区无效 timezone=%s，回退到 %s", timezone, DEFAULT_DAILY_GREETING_TIMEZONE)
        return ZoneInfo(DEFAULT_DAILY_GREETING_TIMEZONE), DEFAULT_DAILY_GREETING_TIMEZONE


def local_day_bounds_utc(target_date: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    start_local = datetime.combine(target_date, time.min, tzinfo=timezone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def upcoming_daily_greeting_plans_for_user(
    user_id: str,
    timezone: str | None,
    now: datetime,
    lookahead_hours: int = AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS,
) -> list[dict]:
    zone, timezone_name = resolve_daily_greeting_timezone(timezone)
    normalized_now = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    lookahead_at = normalized_now + timedelta(hours=lookahead_hours)
    local_now = normalized_now.astimezone(zone)
    days_to_scan = max(2, int(lookahead_hours / 24) + 2)
    plans: list[dict] = []

    for offset in range(days_to_scan):
        greeting_date = local_now.date() + timedelta(days=offset)
        daily_plan = build_daily_greeting_plan(
            user_id=user_id,
            timezone=timezone_name,
            now=local_now,
            target_date=greeting_date,
        )
        for trigger_type, slot_name in (
            (MORNING_TRIGGER_TYPE, "morning"),
            (EVENING_TRIGGER_TYPE, "evening"),
        ):
            slot = daily_plan[slot_name]
            scheduled_local = datetime.fromisoformat(slot["scheduled_at"])
            scheduled_utc = scheduled_local.astimezone(UTC)
            if scheduled_utc <= normalized_now:
                continue

            if not (normalized_now < scheduled_utc <= lookahead_at):
                continue
            plans.append(
                {
                    "trigger_type": trigger_type,
                    "slot": slot_name,
                    "scheduled_at": scheduled_utc,
                    "scheduled_local_at": scheduled_local,
                    "greeting_date": daily_plan["date"],
                    "timezone": timezone_name,
                    "window": slot["window"],
                    "reply_spec": slot["reply_spec"],
                }
            )

    plans.sort(key=lambda item: item["scheduled_at"])
    return plans


async def load_daily_greeting_targets(
    session: AsyncSession,
    limit: int = DAILY_GREETING_USER_LIMIT,
) -> list[dict]:
    result = await session.execute(
        select(Users.id)
        .order_by(Users.created_at.asc())
        .limit(limit)
    )
    targets: list[dict] = []
    for user_id in result.scalars().all():
        targets.append(
            {
                "user_id": user_id,
                "timezone": AURA_TIMEZONE,
                "city_adcode": AURA_CITY_ADCODE,
            }
        )
    return targets


async def daily_greeting_already_planned(
    session: AsyncSession,
    user_id: UUID,
    trigger_type: str,
    greeting_date: date,
    timezone: str | None,
) -> bool:
    zone, _timezone_name = resolve_daily_greeting_timezone(timezone)
    day_start, day_end = local_day_bounds_utc(greeting_date, zone)
    result = await session.execute(
        select(ProactiveMessage.id)
        .where(
            ProactiveMessage.user_id == user_id,
            ProactiveMessage.trigger_type == trigger_type,
            ProactiveMessage.scheduled_at >= day_start,
            ProactiveMessage.scheduled_at < day_end,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def ensure_daily_greeting_messages(
    session: AsyncSession,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
    targets = await load_daily_greeting_targets(session)
    messages: list[ProactiveMessage] = []

    for target in targets:
        user_id = target["user_id"]
        for plan in upcoming_daily_greeting_plans_for_user(
            user_id=str(user_id),
            timezone=target.get("timezone"),
            now=now,
        ):
            if await daily_greeting_already_planned(
                session,
                user_id,
                plan["trigger_type"],
                date.fromisoformat(plan["greeting_date"]),
                plan["timezone"],
            ):
                continue

            title = "Aura 早安问候" if plan["trigger_type"] == MORNING_TRIGGER_TYPE else "Aura 晚安问候"
            proactive = ProactiveMessage(
                id=uuid4(),
                user_id=user_id,
                trigger_type=plan["trigger_type"],
                title=title,
                content=DAILY_GREETING_PLACEHOLDER,
                scheduled_at=plan["scheduled_at"],
                status="pending",
                metadata_json={
                    "source": "daily_greeting_scheduler",
                    "trigger_type": plan["trigger_type"],
                    "slot": plan["slot"],
                    "greeting_date": plan["greeting_date"],
                    "timezone": plan["timezone"],
                    "window": plan["window"],
                    "reply_spec": plan["reply_spec"],
                    "scheduled_local_at": plan["scheduled_local_at"].isoformat(),
                    "city_adcode": target.get("city_adcode"),
                },
            )
            session.add(proactive)
            messages.append(proactive)

    if not messages:
        return 0

    await session.flush()
    queued_count = enqueue_proactive_messages(messages)
    await session.commit()
    logging.info("主动问候计划完成 message_count=%s", len(messages))
    return queued_count


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
            logging.warning("Redis 中的沉默触达用户 ID 无效，已忽略 value=%s", user_id_value)
            continue

        user_context = await build_recent_conversation_context(session, user_id)
        draft = await asyncio.to_thread(
            draft_proactive_message_with_llm,
            SILENCE_TRIGGER_TYPE,
            user_context,
        )
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


async def load_daily_greeting_context(_session: AsyncSession, _user_id: UUID) -> dict:
    return {
        "timezone": AURA_TIMEZONE,
        "city_adcode": AURA_CITY_ADCODE,
    }


async def prepare_proactive_message_content(
    session: AsyncSession,
    proactive: ProactiveMessage,
) -> str:
    if proactive.trigger_type not in DAILY_GREETING_TRIGGER_TYPES:
        return str(proactive.content or "").strip()

    metadata = dict(getattr(proactive, "metadata_json", None) or {})
    profile_context = await load_daily_greeting_context(session, proactive.user_id)
    city_adcode = metadata.get("city_adcode") or profile_context.get("city_adcode")
    weather_context: dict | None = None
    if proactive.trigger_type == MORNING_TRIGGER_TYPE and city_adcode:
        weather_context = await asyncio.to_thread(fetch_weather, str(city_adcode))

    draft = await asyncio.to_thread(
        draft_proactive_message_with_llm,
        proactive.trigger_type,
        "",
        weather_context,
    )
    if not draft.get("should_send", True):
        return ""

    content = str(draft.get("content") or "").strip()
    if not content:
        return ""

    metadata.update(
        {
            "draft_source": draft.get("source"),
            "tone": draft.get("tone"),
            "weather": weather_context or {},
        }
    )
    proactive.content = content
    proactive.metadata_json = metadata
    return content


async def send_proactive_message_records(
    session: AsyncSession,
    messages: Iterable[ProactiveMessage],
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
    sent_count = 0
    changed_count = 0
    for proactive in messages:
        if is_stale_daily_greeting(proactive, now):
            metadata = dict(getattr(proactive, "metadata_json", None) or {})
            metadata["skipped_reason"] = "stale_daily_greeting"
            proactive.metadata_json = metadata
            proactive.status = "skipped"
            proactive.updated_at = now
            changed_count += 1
            continue

        content = await prepare_proactive_message_content(session, proactive)
        if not content:
            proactive.status = "skipped"
            proactive.updated_at = now
            changed_count += 1
            continue

        message_id = str(uuid4())
        append_proactive_history_message(
            user_id=str(proactive.user_id),
            content=content,
            message_id=message_id,
            sent_at=now,
            trigger_type=proactive.trigger_type,
        )
        proactive.status = "sent"
        proactive.sent_at = now
        proactive.updated_at = now
        sent_count += 1
        changed_count += 1

    if changed_count:
        await session.commit()
    if sent_count:
        logging.info("主动消息发送完成 sent_count=%s", sent_count)
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
            logging.warning("Redis 中的主动消息 ID 无效，已忽略 value=%s", message_id)

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
        await ensure_daily_greeting_messages(session, now=now)
        await enqueue_pending_proactive_messages(session, now=now)
        due_ids = pop_due_proactive_message_ids(now=now)
        scheduled_sent_count = await process_due_proactive_messages(session, due_ids, now=now)
        return silence_sent_count + scheduled_sent_count


async def proactive_scheduler_loop(stop_event: asyncio.Event) -> None:
    logging.info(
        "主动消息调度器启动 interval_seconds=%s",
        AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS,
    )
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS)
            break
        except TimeoutError:
            pass

        try:
            await run_proactive_scheduler_tick()
        except Exception:
            logging.exception("主动消息调度周期执行失败")
    logging.info("主动消息调度器已停止")


def start_proactive_scheduler() -> asyncio.Event | None:
    global _scheduler_task

    if not AURA_PROACTIVE_SCHEDULER_ENABLED:
        logging.info("主动消息调度器已由配置关闭")
        return None

    if _scheduler_task and not _scheduler_task.done():
        logging.info("主动消息调度器已经在运行")
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
