from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Iterable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
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
PROACTIVE_CLAIM_LEASE_SECONDS = 5 * 60
PROACTIVE_MAX_DELIVERY_ATTEMPTS = 3
PROACTIVE_RETRY_BASE_SECONDS = 60
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
    """将日期时间标准化为 Redis 有序集合使用的 Unix 分数。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def normalize_utc(value: datetime) -> datetime:
    """将日期时间转换为 UTC；无时区值按 UTC 解释。"""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_stale_daily_greeting(proactive: ProactiveMessage, now: datetime) -> bool:
    """判断早晚问候是否已超过调度间隔和允许的延迟宽限。"""
    if proactive.trigger_type not in DAILY_GREETING_TRIGGER_TYPES:
        return False
    allowed_lag = timedelta(
        seconds=max(AURA_PROACTIVE_SCHEDULER_INTERVAL_SECONDS, 60)
        + DAILY_GREETING_STALE_GRACE_SECONDS
    )
    return normalize_utc(proactive.scheduled_at) < normalize_utc(now) - allowed_lag


def is_deep_night(now: datetime, timezone: ZoneInfo = SILENCE_TIMEZONE) -> bool:
    """判断给定时刻在目标时区是否处于禁止沉默触达的深夜时段。"""
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
    """筛选已沉默超过阈值且本轮尚未问候的用户。

    Args:
        now: 计算沉默时长的当前时间，默认使用当前 UTC 时间。
        threshold_seconds: 触发主动问候所需的最短沉默秒数。

    Returns:
        应触发沉默问候的用户 ID；深夜或 Redis 无状态时为空列表。
    """
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
    """把一条主动消息按计划时间写入 Redis 有序队列。"""
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
    """批量将有计划时间的待发送消息写入 Redis 有序队列。

    Returns:
        Redis 报告的新增或更新成员数量；无有效消息或 Redis 失败时返回 0。
    """
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
    """从 Redis 取出并移除一批到期主动消息 ID。

    Redis 这里只负责清理到期加速索引，不再决定消息所有权。真正的多实例抢占由
    PostgreSQL ``FOR UPDATE SKIP LOCKED`` 完成，因此两步删除失败不会丢失消息。
    """
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
    """查询未来观察窗口内的待发送记录并同步到 Redis 队列。

    Args:
        session: 用于查询主动消息的数据库会话。
        now: 观察窗口起点，默认当前 UTC 时间。
        limit: 单次最多加入队列的数据库记录数。

    Returns:
        Redis 报告的入队数量。
    """
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


async def claim_due_proactive_messages(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = PROACTIVE_DUE_LIMIT,
    message_ids: list[UUID] | None = None,
) -> list[ProactiveMessage]:
    """从 PostgreSQL 原子抢占一批到期主动消息。

    ``processing`` 记录只有在租约过期后才可被另一 worker 重新抢占。抢占状态先
    提交再执行 checkpoint 写入，进程中途退出时可在五分钟后恢复；同一时刻的
    其他实例通过 ``SKIP LOCKED`` 不会拿到同一行。

    Returns:
        已改为 ``processing`` 且增加过尝试次数的 ORM 记录。
    """

    reference_now = now or datetime.now(UTC)
    claimable = or_(
        ProactiveMessage.status == "pending",
        and_(
            ProactiveMessage.status == "processing",
            ProactiveMessage.claimed_until.is_not(None),
            ProactiveMessage.claimed_until <= reference_now,
        ),
    )
    statement = (
        select(ProactiveMessage)
        .where(
            claimable,
            ProactiveMessage.scheduled_at <= reference_now,
        )
        .order_by(ProactiveMessage.scheduled_at.asc(), ProactiveMessage.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(max(1, min(limit, PROACTIVE_DUE_LIMIT)))
    )
    if message_ids is not None:
        if not message_ids:
            return []
        statement = statement.where(ProactiveMessage.id.in_(message_ids))

    result = await session.execute(statement)
    messages = list(result.scalars().all())
    if not messages:
        return []

    claimed_until = reference_now + timedelta(seconds=PROACTIVE_CLAIM_LEASE_SECONDS)
    for proactive in messages:
        proactive.status = "processing"
        proactive.claimed_until = claimed_until
        proactive.attempt_count = int(getattr(proactive, "attempt_count", 0) or 0) + 1
        proactive.updated_at = reference_now
    await session.commit()
    return messages


async def build_recent_conversation_context(
    _session: AsyncSession,
    user_id: UUID,
    limit: int = SILENCE_CONTEXT_MESSAGE_LIMIT,
) -> str:
    """读取最近聊天历史并压缩为沉默问候的短上下文。

    ``session`` 目前为接口兼容参数；历史实际来自 Agent 的检查点存储。
    """
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
    """解析 IANA 时区名称，无效时回退到服务默认时区。

    Returns:
        ``(ZoneInfo, 最终采用的时区名称)``。
    """
    timezone_name = (timezone or DEFAULT_DAILY_GREETING_TIMEZONE).strip() or DEFAULT_DAILY_GREETING_TIMEZONE
    try:
        return ZoneInfo(timezone_name), timezone_name
    except Exception:
        logging.warning("主动问候时区无效 timezone=%s，回退到 %s", timezone, DEFAULT_DAILY_GREETING_TIMEZONE)
        return ZoneInfo(DEFAULT_DAILY_GREETING_TIMEZONE), DEFAULT_DAILY_GREETING_TIMEZONE


def local_day_bounds_utc(target_date: date, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    """返回目标本地日期对应的 UTC 半开区间 ``[开始, 次日开始)``。"""
    start_local = datetime.combine(target_date, time.min, tzinfo=timezone)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def upcoming_daily_greeting_plans_for_user(
    user_id: str,
    timezone: str | None,
    now: datetime,
    lookahead_hours: int = AURA_PROACTIVE_SCHEDULER_LOOKAHEAD_HOURS,
) -> list[dict]:
    """生成观察窗口内尚未到时的早晚问候计划。

    Args:
        user_id: 用于生成稳定计划时间的用户 ID。
        timezone: 用户时区名称，无效时使用默认时区。
        now: 计划计算基准时间。
        lookahead_hours: 从 ``now`` 向后扫描的小时数。

    Returns:
        按 UTC 计划时间升序排列的问候计划字典。
    """
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
    """加载需要规划每日问候的用户及其默认时区、城市配置。

    当前项目为单用户使用，但保留批量返回结构以兼容调度流程。
    """
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
    """检查用户在指定本地日期是否已有同类型问候记录。"""
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
    """为观察窗口内缺失的早晚问候创建数据库记录并加入 Redis。

    Returns:
        Redis 报告的入队数量；没有新计划时返回 0。

    Side Effects:
        新增 ``proactive_messages`` 记录、刷新主键并提交事务。
    """
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
                dedupe_key=(
                    f"daily_greeting:{plan['trigger_type']}:"
                    f"{plan['greeting_date']}:{plan['timezone']}"
                ),
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

    try:
        await session.flush()
        queued_count = enqueue_proactive_messages(messages)
        await session.commit()
    except IntegrityError:
        # 多个调度实例可能同时发现缺口；数据库 dedupe 唯一约束决定唯一赢家。
        await session.rollback()
        logging.info("每日问候计划已由另一调度实例创建，忽略本轮重复")
        return 0
    logging.info("主动问候计划完成 message_count=%s", len(messages))
    return queued_count


async def ensure_relationship_follow_up_messages(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = PROACTIVE_ENQUEUE_LIMIT,
) -> int:
    """为明确授权且已经到期的关系线程创建可靠主动消息。

    普通自动识别事项即使有 ``follow_up_at`` 也不会进入此流程；只有抽取器在
    用户原文中确认“记得问我/提醒我”并写入 ``proactive_allowed=true`` 的线程
    才可创建。数据库唯一 ``dedupe_key`` 处理多实例并发和调度重试。
    """

    from app.db.models import RelationshipThread

    reference_now = now or datetime.now(UTC)
    result = await session.execute(
        select(RelationshipThread)
        .where(
            RelationshipThread.status == "pending",
            RelationshipThread.follow_up_at.is_not(None),
            RelationshipThread.follow_up_at <= reference_now,
            RelationshipThread.metadata_json["proactive_allowed"].astext == "true",
        )
        .order_by(RelationshipThread.follow_up_at.asc())
        .limit(max(1, min(limit, PROACTIVE_ENQUEUE_LIMIT)))
    )
    messages: list[ProactiveMessage] = []
    for thread in result.scalars().all():
        content = build_relationship_follow_up_content(thread.title, thread.summary)
        proactive = ProactiveMessage(
            id=uuid4(),
            user_id=thread.user_id,
            trigger_type="relationship_follow_up",
            title="接着问一句",
            content=content,
            scheduled_at=reference_now,
            status="pending",
            dedupe_key=f"relationship_follow_up:{thread.id}:{thread.version}",
            metadata_json={
                "source": "relationship_thread",
                "relationship_thread_id": str(thread.id),
                "relationship_thread_version": thread.version,
            },
        )
        session.add(proactive)
        messages.append(proactive)

    if not messages:
        return 0
    try:
        await session.flush()
        queued_count = enqueue_proactive_messages(messages)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logging.info("关系线程主动跟进已由另一调度实例创建，忽略本轮重复")
        return 0
    return queued_count


def build_relationship_follow_up_content(title: str, summary: str) -> str:
    """根据已确认的线程事实生成简短、具体、不催回复的跟进文本。"""

    normalized_title = " ".join(str(title or "").split()).strip()
    normalized_summary = " ".join(str(summary or "").split()).strip()
    subject = normalized_title or normalized_summary or "你之前提到的那件事"
    return f"你之前说的“{subject[:60]}”，后来怎么样了？"


async def trigger_silence_proactive_messages(
    session: AsyncSession,
    user_ids: list[str],
    now: datetime | None = None,
) -> int:
    """为到期沉默用户生成问候，并立即写入聊天历史。

    Args:
        session: 用于创建和更新主动消息记录的数据库会话。
        user_ids: 已通过沉默阈值筛选的用户 ID。
        now: 消息发送时间，默认当前 UTC 时间。

    Returns:
        实际发送的主动消息数量。

    Side Effects:
        调用模型生成文案、写数据库和聊天历史，并更新 Redis 触发标记。
    """
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
    """返回每日问候所需的时区和天气城市配置。

    当前为单用户全局配置，保留会话和用户参数以便以后改为用户级资料。
    """
    return {
        "timezone": AURA_TIMEZONE,
        "city_adcode": AURA_CITY_ADCODE,
    }


async def prepare_proactive_message_content(
    session: AsyncSession,
    proactive: ProactiveMessage,
) -> str:
    """准备主动消息最终文案，并更新每日问候的生成元数据。

    普通主动消息沿用已有内容；早晚问候会按需查询天气并调用模型生成。

    Returns:
        可发送的非空文案；模型决定不发送或生成空内容时返回空字符串。
    """
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
    """处理主动消息记录，将有效内容追加到聊天历史并更新发送状态。

    过期问候和空文案标记为 ``skipped``。checkpoint 写入成功后才标记
    ``sent``；失败时按尝试次数回到 ``pending`` 或进入 ``failed``，不会静默丢失。

    Returns:
        成功写入聊天历史的消息数量。
    """
    now = now or datetime.now(UTC)
    sent_count = 0
    changed_count = 0
    successful_messages: list[ProactiveMessage] = []
    for proactive in messages:
        if proactive.status not in {"pending", "processing"}:
            continue
        if proactive.status == "pending":
            proactive.status = "processing"
            proactive.attempt_count = int(getattr(proactive, "attempt_count", 0) or 0) + 1
            proactive.claimed_until = now + timedelta(seconds=PROACTIVE_CLAIM_LEASE_SECONDS)

        if is_stale_daily_greeting(proactive, now):
            metadata = dict(getattr(proactive, "metadata_json", None) or {})
            metadata["skipped_reason"] = "stale_daily_greeting"
            proactive.metadata_json = metadata
            proactive.status = "skipped"
            proactive.claimed_until = None
            proactive.updated_at = now
            changed_count += 1
            continue

        content = await prepare_proactive_message_content(session, proactive)
        if not content:
            proactive.status = "skipped"
            proactive.claimed_until = None
            proactive.updated_at = now
            changed_count += 1
            continue

        delivery_message_id = str(
            getattr(proactive, "delivery_message_id", None) or proactive.id
        )
        appended = append_proactive_history_message(
            user_id=str(proactive.user_id),
            content=content,
            message_id=delivery_message_id,
            sent_at=now,
            trigger_type=proactive.trigger_type,
        )
        if not appended:
            mark_proactive_delivery_failure(proactive, now, "聊天历史写入失败")
            changed_count += 1
            continue

        proactive.status = "sent"
        proactive.sent_at = now
        proactive.claimed_until = None
        proactive.last_error = None
        proactive.updated_at = now
        sent_count += 1
        changed_count += 1
        successful_messages.append(proactive)

    if changed_count:
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            logging.exception("主动消息投递状态提交失败")
            return 0
    for proactive in successful_messages:
        try:
            await mark_relationship_thread_followed_up_from_proactive(session, proactive, now)
        except Exception:
            await session.rollback()
            logging.exception("主动跟进发送成功，但关系线程状态更新失败 message_id=%s", proactive.id)
    if sent_count:
        logging.info("主动消息发送完成 sent_count=%s", sent_count)
    return sent_count


async def mark_relationship_thread_followed_up_from_proactive(
    session: AsyncSession,
    proactive: ProactiveMessage,
    now: datetime,
) -> None:
    """在跟进消息确认写入历史后，把来源线程推进到 ``followed_up``。

    ``relationship_thread_id`` 仅从服务端生成的 metadata 读取，并同时校验线程
    所有者。重复执行时终态检查会直接返回，不会追加重复事件。
    """

    if proactive.trigger_type != "relationship_follow_up":
        return
    metadata = dict(getattr(proactive, "metadata_json", None) or {})
    raw_thread_id = metadata.get("relationship_thread_id")
    try:
        thread_id = UUID(str(raw_thread_id))
    except (TypeError, ValueError):
        return

    from app.db.models import RelationshipThread, RelationshipThreadEvent

    result = await session.execute(
        select(RelationshipThread)
        .where(
            RelationshipThread.id == thread_id,
            RelationshipThread.user_id == proactive.user_id,
        )
        .with_for_update()
    )
    thread = result.scalar_one_or_none()
    if thread is None or thread.status != "pending":
        return

    state_before = relationship_thread_scheduler_state(thread)
    thread.status = "followed_up"
    thread.last_followed_up_at = now
    thread.follow_up_at = None
    thread.version += 1
    thread.updated_at = now
    session.add(
        RelationshipThreadEvent(
            thread_id=thread.id,
            sequence_no=thread.version,
            actor="aura",
            event_type="followed_up",
            state_before=state_before,
            state_after=relationship_thread_scheduler_state(thread),
            client_action_id=f"proactive-followup:{proactive.id}",
            metadata_json={"proactive_message_id": str(proactive.id)},
            occurred_at=now,
        )
    )
    await session.commit()


def relationship_thread_scheduler_state(thread) -> dict[str, object]:
    """构造调度器写入线程事件所需的紧凑状态快照。"""

    return {
        "thread_type": thread.thread_type,
        "perspective": thread.perspective,
        "world_layer": thread.world_layer,
        "title": thread.title,
        "summary": thread.summary,
        "status": thread.status,
        "follow_up_at": thread.follow_up_at.isoformat() if thread.follow_up_at else None,
        "last_followed_up_at": (
            thread.last_followed_up_at.isoformat() if thread.last_followed_up_at else None
        ),
        "resolved_at": thread.resolved_at.isoformat() if thread.resolved_at else None,
        "version": thread.version,
        "metadata": dict(thread.metadata_json or {}),
    }


def mark_proactive_delivery_failure(
    proactive: ProactiveMessage,
    now: datetime,
    error_message: str,
) -> None:
    """记录一次投递失败，并决定延迟重试还是进入人工可见的失败终态。"""

    attempts = int(getattr(proactive, "attempt_count", 0) or 0)
    proactive.last_error = error_message[:1000]
    proactive.claimed_until = None
    proactive.updated_at = now
    if attempts >= PROACTIVE_MAX_DELIVERY_ATTEMPTS:
        proactive.status = "failed"
        return
    proactive.status = "pending"
    retry_seconds = PROACTIVE_RETRY_BASE_SECONDS * (2 ** max(attempts - 1, 0))
    proactive.scheduled_at = now + timedelta(seconds=retry_seconds)


async def process_due_proactive_messages(
    session: AsyncSession,
    message_ids: list[str],
    now: datetime | None = None,
) -> int:
    """校验到期消息 ID、查询仍待发送的记录并执行发送。

    无效 UUID、已经处理或计划时间未到的记录会被忽略。
    """
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

    messages = await claim_due_proactive_messages(
        session,
        now=now,
        message_ids=parsed_ids,
    )
    return await send_proactive_message_records(session, messages, now=now)


async def run_proactive_scheduler_tick(now: datetime | None = None) -> int:
    """执行一个完整主动消息调度周期。

    顺序处理沉默问候、每日问候补计划、Redis 加速索引和 PostgreSQL 到期抢占。
    Redis 不可用时只跳过依赖在线活跃状态的沉默问候；持久化消息仍会发送。

    Returns:
        本周期实际发送的主动消息总数。
    """
    now = now or datetime.now(UTC)
    has_redis = redis_available()
    async with AsyncSessionLocal() as session:
        silence_user_ids = collect_due_silence_user_ids(now=now) if has_redis else []
        silence_sent_count = await trigger_silence_proactive_messages(session, silence_user_ids, now=now)
        await ensure_daily_greeting_messages(session, now=now)
        await ensure_relationship_follow_up_messages(session, now=now)
        if has_redis:
            await enqueue_pending_proactive_messages(session, now=now)
            pop_due_proactive_message_ids(now=now)
        claimed_messages = await claim_due_proactive_messages(session, now=now)
        scheduled_sent_count = await send_proactive_message_records(
            session,
            claimed_messages,
            now=now,
        )
        return silence_sent_count + scheduled_sent_count


async def proactive_scheduler_loop(stop_event: asyncio.Event) -> None:
    """按配置间隔持续运行主动消息调度，直到收到停止事件。

    单次周期异常只记录日志，不会终止后续调度。
    """
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
    """在当前事件循环启动唯一的主动消息后台任务。

    Returns:
        用于请求停止的事件；功能关闭或任务已运行时返回 ``None``。
    """
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
    """通知主动消息后台任务停止，并等待任务退出后清理全局引用。"""
    global _scheduler_task

    if stop_event is not None:
        stop_event.set()
    if _scheduler_task is not None:
        await asyncio.gather(_scheduler_task, return_exceptions=True)
        _scheduler_task = None
