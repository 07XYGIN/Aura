"""一起专注的 PostgreSQL 状态机与主动消息衔接。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    FocusSession,
    FocusSessionEvent,
    ProactiveMessage,
    RelationshipThread,
    RelationshipThreadEvent,
)
from app.db.session import SyncSessionLocal
from app.schemas.focus import FocusActionRequest, FocusProgressRequest, FocusStartRequest

FOCUS_TRIGGER_TYPE = "focus_check_in"
RUNNING_FOCUS_STATUSES = ("active", "paused", "check_in_queued")
CURRENT_FOCUS_STATUSES = (*RUNNING_FOCUS_STATUSES, "awaiting_report")
MAX_FOCUS_SCAN = 100


class FocusServiceError(RuntimeError):
    """可安全返回给客户端的中文专注领域错误。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def start_focus_session(
    session: AsyncSession,
    user_id: str,
    request: FocusStartRequest,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """幂等开始一次专注，并保证每个用户最多一个正在计时的会话。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    reference_now = normalize_utc(now or datetime.now(UTC))
    replay_result = await session.execute(
        select(FocusSession).where(
            FocusSession.user_id == parsed_user_id,
            FocusSession.start_request_id == request.start_request_id,
        )
    )
    replay = replay_result.scalar_one_or_none()
    if replay is not None:
        ensure_start_replay_matches(replay, request)
        return focus_snapshot(replay, action="start_replayed", now=reference_now)

    running_result = await session.execute(
        select(FocusSession).where(
            FocusSession.user_id == parsed_user_id,
            FocusSession.status.in_(RUNNING_FOCUS_STATUSES),
        ).limit(1)
    )
    if running_result.scalar_one_or_none() is not None:
        raise FocusServiceError("已经有一次专注正在进行，先完成或取消它", 409)

    focus = FocusSession(
        id=uuid4(),
        user_id=parsed_user_id,
        activity=request.activity,
        duration_minutes=request.duration_minutes,
        status="active",
        started_at=reference_now,
        ends_at=reference_now + timedelta(minutes=request.duration_minutes),
        start_request_id=request.start_request_id,
        source_message_id=request.source_message_id,
        version=1,
        metadata_json=safe_metadata(request.metadata),
    )
    session.add(focus)
    session.add(
        FocusSessionEvent(
            id=uuid4(),
            session_id=focus.id,
            sequence_no=1,
            actor="user",
            event_type="started",
            client_action_id=request.start_request_id,
            note=request.activity,
            metadata_json={"duration_minutes": request.duration_minutes},
            occurred_at=reference_now,
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise FocusServiceError("专注会话创建发生并发冲突，请读取当前状态", 409) from exc
    return focus_snapshot(focus, action="started", now=reference_now)


async def get_current_focus_session(
    session: AsyncSession,
    user_id: str,
    *,
    now: datetime | None = None,
) -> FocusSession | None:
    """优先返回正在计时的会话，否则返回最近一条等待汇报的会话。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    result = await session.execute(
        select(FocusSession)
        .where(
            FocusSession.user_id == parsed_user_id,
            FocusSession.status.in_(CURRENT_FOCUS_STATUSES),
        )
        .order_by(
            FocusSession.status.in_(RUNNING_FOCUS_STATUSES).desc(),
            FocusSession.created_at.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_current_focus_snapshot(
    session: AsyncSession,
    user_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """返回当前专注公开快照，没有活动或待汇报会话时返回 ``None``。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    focus = await get_current_focus_session(session, user_id, now=reference_now)
    return focus_snapshot(focus, action="status", now=reference_now) if focus else None


async def apply_focus_action(
    session: AsyncSession,
    user_id: str,
    focus_id: str,
    request: FocusActionRequest,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """原子执行暂停、恢复或取消，并用事件表处理网络重放。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    parsed_focus_id = parse_uuid(focus_id, "专注会话 ID")
    reference_now = normalize_utc(now or datetime.now(UTC))
    result = await session.execute(
        select(FocusSession)
        .where(
            FocusSession.id == parsed_focus_id,
            FocusSession.user_id == parsed_user_id,
        )
        .with_for_update()
    )
    focus = result.scalar_one_or_none()
    if focus is None:
        raise FocusServiceError("没有找到这次专注", 404)
    replay_result = await session.execute(
        select(FocusSessionEvent).where(
            FocusSessionEvent.session_id == focus.id,
            FocusSessionEvent.client_action_id == request.client_action_id,
        )
    )
    if replay_result.scalar_one_or_none() is not None:
        return focus_snapshot(focus, action=f"{request.action}_replayed", now=reference_now)
    if request.expected_version is not None and focus.version != request.expected_version:
        raise FocusServiceError("专注状态已经变化，请刷新后重试", 409)

    if request.action == "pause":
        if focus.status != "active":
            raise FocusServiceError("只有正在计时的专注可以暂停", 409)
        focus.status = "paused"
        focus.paused_at = reference_now
        focus.remaining_seconds = max(0, min(14400, int((normalize_utc(focus.ends_at) - reference_now).total_seconds())))
        event_type = "paused"
    elif request.action == "resume":
        if focus.status != "paused":
            raise FocusServiceError("只有已暂停的专注可以继续", 409)
        remaining = max(1, int(focus.remaining_seconds or 0))
        focus.status = "active"
        focus.ends_at = reference_now + timedelta(seconds=remaining)
        focus.paused_at = None
        focus.remaining_seconds = None
        event_type = "resumed"
    else:
        if focus.status in {"completed", "cancelled", "expired"}:
            raise FocusServiceError("这次专注已经结束", 409)
        await ensure_focus_outbox_can_cancel(session, focus)
        focus.status = "cancelled"
        focus.cancelled_at = reference_now
        event_type = "cancelled"

    focus.version += 1
    session.add(
        FocusSessionEvent(
            id=uuid4(),
            session_id=focus.id,
            sequence_no=focus.version,
            actor="user",
            event_type=event_type,
            client_action_id=request.client_action_id,
            metadata_json={},
            occurred_at=reference_now,
        )
    )
    await session.commit()
    return focus_snapshot(focus, action=event_type, now=reference_now)


async def report_focus_progress(
    session: AsyncSession,
    user_id: str,
    focus_id: str,
    request: FocusProgressRequest,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """保存结束后的进度和卡点，并把真实卡点转成待续项目线程。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    parsed_focus_id = parse_uuid(focus_id, "专注会话 ID")
    reference_now = normalize_utc(now or datetime.now(UTC))
    result = await session.execute(
        select(FocusSession)
        .where(
            FocusSession.id == parsed_focus_id,
            FocusSession.user_id == parsed_user_id,
        )
        .with_for_update()
    )
    focus = result.scalar_one_or_none()
    if focus is None:
        raise FocusServiceError("没有找到这次专注", 404)
    replay_result = await session.execute(
        select(FocusSessionEvent).where(
            FocusSessionEvent.session_id == focus.id,
            FocusSessionEvent.client_action_id == request.client_action_id,
        )
    )
    if replay_result.scalar_one_or_none() is not None:
        return focus_snapshot(focus, action="progress_replayed", now=reference_now)
    if focus.status != "awaiting_report":
        raise FocusServiceError("这次专注还没有进入进度汇报阶段", 409)
    if request.expected_version is not None and focus.version != request.expected_version:
        raise FocusServiceError("专注状态已经变化，请刷新后重试", 409)

    focus.status = "completed"
    focus.result_summary = request.result_summary
    focus.blocker = request.blocker
    focus.completed_at = reference_now
    focus.version += 1
    session.add(
        FocusSessionEvent(
            id=uuid4(),
            session_id=focus.id,
            sequence_no=focus.version,
            actor="user",
            event_type="completed",
            client_action_id=request.client_action_id,
            note=request.result_summary,
            metadata_json={"has_blocker": bool(request.blocker)},
            occurred_at=reference_now,
        )
    )
    if request.blocker:
        add_focus_blocker_thread(session, focus, request.blocker, reference_now)
    await session.commit()
    return focus_snapshot(focus, action="completed", now=reference_now)


async def ensure_due_focus_check_ins(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = MAX_FOCUS_SCAN,
) -> list[ProactiveMessage]:
    """为到时的 active 会话创建唯一结束问询 outbox。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    result = await session.execute(
        select(FocusSession)
        .where(
            FocusSession.status == "active",
            FocusSession.ends_at <= reference_now,
        )
        .order_by(FocusSession.ends_at.asc())
        .with_for_update(skip_locked=True)
        .limit(max(1, min(limit, MAX_FOCUS_SCAN)))
    )
    messages: list[ProactiveMessage] = []
    for focus in result.scalars().all():
        outbox = ProactiveMessage(
            id=uuid4(),
            user_id=focus.user_id,
            trigger_type=FOCUS_TRIGGER_TYPE,
            title="专注结束",
            content=f"时间到了。刚才那段“{focus.activity}”进展怎么样？有哪里还卡着吗？",
            scheduled_at=reference_now,
            status="pending",
            dedupe_key=f"focus_check_in:{focus.id}:{focus.version}",
            metadata_json={
                "source": "focus_session",
                "focus_session_id": str(focus.id),
                "focus_session_version": focus.version,
            },
        )
        session.add(outbox)
        focus.status = "check_in_queued"
        focus.check_in_queued_at = reference_now
        focus.outbox_message_id = outbox.id
        focus.version += 1
        session.add(
            FocusSessionEvent(
                id=uuid4(),
                session_id=focus.id,
                sequence_no=focus.version,
                actor="system",
                event_type="check_in_queued",
                client_action_id=f"scheduler:{focus.id}",
                metadata_json={"outbox_message_id": str(outbox.id)},
                occurred_at=reference_now,
            )
        )
        messages.append(outbox)
    if messages:
        await session.commit()
    return messages


async def defer_proactive_during_focus(
    session: AsyncSession,
    proactive: ProactiveMessage,
    now: datetime,
) -> bool:
    """活动专注期间延后非专注主动消息，避免计时中途打扰。"""

    if proactive.trigger_type == FOCUS_TRIGGER_TYPE:
        return False
    result = await session.execute(
        select(FocusSession).where(
            FocusSession.user_id == proactive.user_id,
            FocusSession.status.in_(RUNNING_FOCUS_STATUSES),
        ).limit(1)
    )
    focus = result.scalar_one_or_none()
    if focus is None:
        return False
    if focus.status == "active" and normalize_utc(focus.ends_at) <= normalize_utc(now):
        return False
    delay_until = (
        normalize_utc(focus.ends_at) + timedelta(minutes=2)
        if focus.status == "active"
        else normalize_utc(now) + timedelta(minutes=15)
    )
    proactive.status = "pending"
    proactive.scheduled_at = max(normalize_utc(proactive.scheduled_at), delay_until)
    proactive.claimed_until = None
    proactive.updated_at = normalize_utc(now)
    return True


async def stage_focus_outbox_state(
    session: AsyncSession,
    proactive: ProactiveMessage,
    now: datetime,
) -> bool:
    """在 outbox 提交事务内同步专注问询的业务状态。"""

    if proactive.trigger_type != FOCUS_TRIGGER_TYPE or proactive.status not in {"sent", "failed"}:
        return False
    raw_id = dict(proactive.metadata_json or {}).get("focus_session_id")
    try:
        focus_id = UUID(str(raw_id))
    except (TypeError, ValueError):
        return False
    result = await session.execute(
        select(FocusSession)
        .where(
            FocusSession.id == focus_id,
            FocusSession.user_id == proactive.user_id,
        )
        .with_for_update()
    )
    focus = result.scalar_one_or_none()
    if focus is None or focus.outbox_message_id != proactive.id:
        return False
    target_status = "awaiting_report" if proactive.status == "sent" else "expired"
    if focus.status == target_status:
        return False
    if focus.status != "check_in_queued":
        return False
    focus.status = target_status
    if target_status == "awaiting_report":
        focus.check_in_sent_at = normalize_utc(now)
        event_type = "check_in_sent"
        actor = "aura"
    else:
        event_type = "expired"
        actor = "system"
    focus.version += 1
    session.add(
        FocusSessionEvent(
            id=uuid4(),
            session_id=focus.id,
            sequence_no=focus.version,
            actor=actor,
            event_type=event_type,
            client_action_id=f"outbox:{proactive.id}:{event_type}",
            metadata_json={"outbox_status": proactive.status},
            occurred_at=normalize_utc(now),
        )
    )
    return True


async def reconcile_focus_outbox(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """只补已终态 outbox 对应的专注状态，不重复发送问询。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    result = await session.execute(
        select(ProactiveMessage)
        .join(FocusSession, FocusSession.outbox_message_id == ProactiveMessage.id)
        .where(
            FocusSession.status == "check_in_queued",
            ProactiveMessage.trigger_type == FOCUS_TRIGGER_TYPE,
            ProactiveMessage.status.in_(("sent", "failed")),
        )
        .limit(MAX_FOCUS_SCAN)
    )
    changed = 0
    for proactive in result.scalars().all():
        if await stage_focus_outbox_state(session, proactive, reference_now):
            changed += 1
    if changed:
        await session.commit()
    return changed


def load_focus_prompt_context_sync(user_id: str, *, now: datetime | None = None) -> str:
    """读取当前专注状态供主模型保持一致，不暴露内部 ID 或版本。"""

    try:
        parsed_user_id = UUID(str(user_id))
    except (TypeError, ValueError):
        return ""
    reference_now = normalize_utc(now or datetime.now(UTC))
    try:
        with SyncSessionLocal() as session:
            focus = session.execute(
                select(FocusSession)
                .where(
                    FocusSession.user_id == parsed_user_id,
                    FocusSession.status.in_(CURRENT_FOCUS_STATUSES),
                )
                .order_by(FocusSession.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
    except Exception:
        logging.exception("专注上下文读取失败 user_id=%s", parsed_user_id)
        return ""
    if focus is None:
        return ""
    if focus.status == "active":
        remaining = max(0, int((normalize_utc(focus.ends_at) - reference_now).total_seconds()))
        state = f"正在专注“{focus.activity}”，约剩 {max(1, (remaining + 59) // 60)} 分钟"
    elif focus.status == "paused":
        state = f"“{focus.activity}”已暂停"
    elif focus.status == "check_in_queued":
        state = f"“{focus.activity}”已经到时，结束问询正在投递"
    else:
        state = f"“{focus.activity}”已经到时，正在等小乔汇报进度"
    return (
        "【一起专注】\n"
        f"{state}。这是服务端真实状态。专注进行中不要主动开启新话题或催促；"
        "小乔主动说话时正常回应。"
    )


async def ensure_focus_outbox_can_cancel(session: AsyncSession, focus: FocusSession) -> None:
    """取消 queued 会话时同步取消待发 outbox，processing/sent 阶段拒绝竞态撤回。"""

    if focus.outbox_message_id is None:
        return
    result = await session.execute(
        select(ProactiveMessage)
        .where(ProactiveMessage.id == focus.outbox_message_id)
        .with_for_update()
    )
    outbox = result.scalar_one_or_none()
    if outbox is None or outbox.status == "failed":
        return
    if outbox.status == "pending":
        outbox.status = "cancelled"
        outbox.cancelled_at = datetime.now(UTC)
        outbox.claimed_until = None
        return
    if outbox.status == "processing":
        raise FocusServiceError("结束问询正在投递，暂时不能取消", 409)
    if outbox.status == "sent":
        raise FocusServiceError("结束问询已经发出，不能再取消这次专注", 409)


def add_focus_blocker_thread(session, focus: FocusSession, blocker: str, now: datetime) -> None:
    """把用户明确汇报的卡点写成待续项目线程，不授予主动消息权限。"""

    source_key = f"focus-blocker:{focus.id}:{focus.version}"
    thread = RelationshipThread(
        id=uuid4(),
        user_id=focus.user_id,
        thread_type="project_task",
        perspective="user",
        world_layer="reality",
        title=f"专注卡点：{focus.activity}"[:160],
        summary=blocker[:1200],
        status="pending",
        source_key=source_key,
        source_message_id=focus.source_message_id,
        source_turn_id=None,
        version=1,
        metadata_json={
            "capture_source": "focus_progress",
            "focus_session_id": str(focus.id),
            "proactive_allowed": False,
        },
    )
    session.add(thread)
    session.add(
        RelationshipThreadEvent(
            id=uuid4(),
            thread_id=thread.id,
            sequence_no=1,
            actor="user",
            event_type="created",
            state_before={},
            state_after={
                "thread_type": "project_task",
                "perspective": "user",
                "world_layer": "reality",
                "title": thread.title,
                "summary": thread.summary,
                "status": "pending",
                "version": 1,
            },
            client_action_id=source_key,
            metadata_json={"focus_session_id": str(focus.id)},
            occurred_at=now,
        )
    )


def focus_snapshot(focus: FocusSession, *, action: str, now: datetime) -> dict[str, Any]:
    """生成 API 和 SSE 共用的公开专注快照。"""

    remaining_seconds = None
    if focus.status == "active":
        remaining_seconds = max(0, int((normalize_utc(focus.ends_at) - normalize_utc(now)).total_seconds()))
    elif focus.status == "paused":
        remaining_seconds = int(focus.remaining_seconds or 0)
    return {
        "action": action,
        "idempotentReplay": action.endswith("_replayed"),
        "focus": {
            "id": str(focus.id),
            "activity": focus.activity,
            "durationMinutes": focus.duration_minutes,
            "status": focus.status,
            "remainingSeconds": remaining_seconds,
            "startedAt": iso_datetime(focus.started_at),
            "endsAt": iso_datetime(focus.ends_at),
            "pausedAt": iso_datetime(focus.paused_at),
            "checkInSentAt": iso_datetime(focus.check_in_sent_at),
            "completedAt": iso_datetime(focus.completed_at),
            "cancelledAt": iso_datetime(focus.cancelled_at),
            "resultSummary": focus.result_summary,
            "blocker": focus.blocker,
            "version": focus.version,
        },
    }


def ensure_start_replay_matches(focus: FocusSession, request: FocusStartRequest) -> None:
    """拒绝用同一开始幂等键替换活动或时长。"""

    if focus.activity != request.activity or focus.duration_minutes != request.duration_minutes:
        raise FocusServiceError("startRequestId 已被另一份专注参数使用", 409)


def parse_uuid(value: str, label: str) -> UUID:
    """解析外部 UUID，并返回稳定中文错误。"""

    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise FocusServiceError(f"{label}格式无效") from exc


def normalize_utc(value: datetime) -> datetime:
    """把日期时间统一为 UTC。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_datetime(value: datetime | None) -> str | None:
    """把可选时间转换为 UTC ISO 字符串。"""

    return normalize_utc(value).isoformat() if value is not None else None


def safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    """只保留简单公开标签，剥离身份和主动消息授权字段。"""

    if not isinstance(value, dict):
        return {}
    reserved = {"user_id", "userid", "proactive_allowed", "authorization", "content"}
    return {
        str(key)[:80]: item
        for key, item in value.items()
        if str(key).strip().casefold() not in reserved
    }
