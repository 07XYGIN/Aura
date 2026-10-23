"""关系连续性线程的 PostgreSQL 事务服务。"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RelationshipThread, RelationshipThreadEvent, Users
from app.db.session import SyncSessionLocal
from app.schemas.continuity import (
    RelationshipThreadCreateRequest,
    RelationshipThreadTransitionRequest,
)

from .extractor import build_source_key, normalize_thread_candidates

ACTIVE_THREAD_STATUSES = {"pending", "followed_up"}
TERMINAL_THREAD_STATUSES = {"resolved", "abandoned"}
ACTION_EVENT_TYPES = {
    "update": "updated",
    "follow_up": "followed_up",
    "resolve": "resolved",
    "abandon": "abandoned",
}


class RelationshipThreadServiceError(RuntimeError):
    """可转换成中文 HTTP 或聊天错误的关系线程领域异常。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        """保存用户可读说明和建议 HTTP 状态码。"""

        super().__init__(message)
        self.status_code = status_code


def parse_user_id(user_id: str) -> UUID:
    """把 JWT 用户 ID 解析为 UUID，无效时抛出 400 领域错误。"""

    try:
        return UUID(str(user_id))
    except (TypeError, ValueError) as exc:
        raise RelationshipThreadServiceError("用户 ID 无效") from exc


def parse_thread_id(thread_id: str) -> UUID:
    """把关系线程 ID 解析为 UUID，无效时抛出 400 领域错误。"""

    try:
        return UUID(str(thread_id))
    except (TypeError, ValueError) as exc:
        raise RelationshipThreadServiceError("关系线程 ID 无效") from exc


async def create_relationship_thread(
    session: AsyncSession,
    user_id: str,
    request: RelationshipThreadCreateRequest,
    *,
    actor: str = "user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """为当前用户幂等创建一条关系线程和首个不可变事件。

    Args:
        session: 当前请求的异步数据库会话。
        user_id: JWT 中的权威用户 ID。
        request: 线程内容、事实层、可选跟进时间和客户端幂等键。
        actor: 创建者，HTTP 固定为 ``user``；后台抽取使用单独同步入口。
        now: 可注入的 UTC 创建时间，主要供测试使用。

    Returns:
        当前线程、创建事件和 ``idempotentReplay`` 标记。

    Side Effects:
        锁定唯一用户行，在同一事务插入权威状态与 ``created`` 事件并提交。
    """

    if actor not in {"user", "aura", "system"}:
        raise RelationshipThreadServiceError("关系线程创建者无效")
    parsed_user_id = parse_user_id(user_id)
    source_key = f"api:{request.client_request_id.strip()}"
    created_at = normalize_utc_datetime(now or datetime.now(UTC))
    creation_payload = create_request_payload(request)

    user_result = await session.execute(
        select(Users.id).where(Users.id == parsed_user_id).with_for_update()
    )
    if user_result.scalar_one_or_none() is None:
        raise RelationshipThreadServiceError("用户不存在", status_code=404)

    existing_result = await session.execute(
        select(RelationshipThread).where(
            RelationshipThread.user_id == parsed_user_id,
            RelationshipThread.source_key == source_key,
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        creation_event_result = await session.execute(
            select(RelationshipThreadEvent).where(
                RelationshipThreadEvent.thread_id == existing.id,
                RelationshipThreadEvent.event_type == "created",
                RelationshipThreadEvent.client_action_id == request.client_request_id.strip(),
            )
        )
        creation_event = creation_event_result.scalar_one_or_none()
        ensure_create_replay_matches(creation_event, creation_payload)
        return await build_thread_snapshot(
            session,
            existing,
            idempotent_replay=True,
        )

    thread = RelationshipThread(
        user_id=parsed_user_id,
        thread_type=request.thread_type,
        perspective=request.perspective,
        world_layer=request.world_layer,
        title=require_non_blank(request.title, "线程标题"),
        summary=require_non_blank(request.summary, "线程摘要"),
        status="pending",
        source_key=source_key,
        source_message_id=clean_optional_text(request.source_message_id),
        source_turn_id=clean_optional_text(request.source_turn_id),
        follow_up_at=normalize_optional_datetime(request.follow_up_at),
        version=1,
        metadata_json=sanitize_user_metadata(request.metadata),
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(thread)
    try:
        await session.flush()
        event = RelationshipThreadEvent(
            thread_id=thread.id,
            sequence_no=1,
            actor=actor,
            event_type="created",
            state_before={},
            state_after=thread_state_for_event(thread),
            source_message_id=thread.source_message_id,
            client_action_id=request.client_request_id.strip(),
            metadata_json={"request": creation_payload},
            occurred_at=created_at,
        )
        session.add(event)
        await session.commit()
        await session.refresh(thread)
        await session.refresh(event)
    except IntegrityError as exc:
        await session.rollback()
        raise RelationshipThreadServiceError(
            "关系线程创建发生并发冲突，请重新读取后重试",
            status_code=409,
        ) from exc
    return await build_thread_snapshot(session, thread, event=event)


async def transition_relationship_thread(
    session: AsyncSession,
    user_id: str,
    thread_id: str,
    request: RelationshipThreadTransitionRequest,
    *,
    actor: str = "user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """原子更新、跟进、解决或放弃一条关系线程。

    行锁、可选版本和线程内唯一 ``clientActionId`` 共同保证并发安全。重复请求
    返回当前状态而不再递增版本；相同 ID 携带不同参数会得到 409。
    """

    if actor not in {"user", "aura", "system"}:
        raise RelationshipThreadServiceError("关系线程执行者无效")
    thread = await require_locked_thread(session, user_id, thread_id)
    client_action_id = request.client_action_id
    replay_result = await session.execute(
        select(RelationshipThreadEvent).where(
            RelationshipThreadEvent.thread_id == thread.id,
            RelationshipThreadEvent.client_action_id == client_action_id,
        )
    )
    replay = replay_result.scalar_one_or_none()
    request_payload = transition_request_payload(request)
    if replay is not None:
        ensure_transition_replay_matches(replay, request_payload)
        return await build_thread_snapshot(
            session,
            thread,
            event=replay,
            idempotent_replay=True,
        )

    if request.expected_version is not None and thread.version != request.expected_version:
        raise RelationshipThreadServiceError(
            f"关系线程已经变化，当前版本是 {thread.version}，请刷新后重试",
            status_code=409,
        )
    if thread.status in TERMINAL_THREAD_STATUSES:
        raise RelationshipThreadServiceError("已经结束的关系线程不能再次修改", status_code=409)

    occurred_at = normalize_utc_datetime(now or datetime.now(UTC))
    state_before = thread_state_for_event(thread)
    apply_transition(thread, request, occurred_at)
    thread.version += 1
    thread.updated_at = occurred_at
    event = RelationshipThreadEvent(
        thread_id=thread.id,
        sequence_no=thread.version,
        actor=actor,
        event_type=ACTION_EVENT_TYPES[request.action],
        state_before=state_before,
        state_after=thread_state_for_event(thread),
        source_message_id=clean_optional_text(request.source_message_id),
        client_action_id=client_action_id,
        metadata_json={
            "request": request_payload,
            "user_metadata": sanitize_user_metadata(request.metadata),
        },
        occurred_at=occurred_at,
    )
    session.add(event)
    try:
        await session.commit()
        await session.refresh(thread)
        await session.refresh(event)
    except IntegrityError as exc:
        await session.rollback()
        raise RelationshipThreadServiceError(
            "关系线程状态更新发生并发冲突，请重新读取后重试",
            status_code=409,
        ) from exc
    return await build_thread_snapshot(session, thread, event=event)


async def list_relationship_threads(
    session: AsyncSession,
    user_id: str,
    *,
    thread_type: str | None = None,
    status: str | None = None,
    world_layer: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按过滤条件读取当前用户的关系线程，默认优先返回待处理事项。"""

    statement = select(RelationshipThread).where(
        RelationshipThread.user_id == parse_user_id(user_id)
    )
    if thread_type:
        statement = statement.where(RelationshipThread.thread_type == thread_type)
    if status:
        statement = statement.where(RelationshipThread.status == status)
    if world_layer:
        statement = statement.where(RelationshipThread.world_layer == world_layer)
    statement = statement.order_by(
        RelationshipThread.follow_up_at.asc().nullslast(),
        RelationshipThread.updated_at.desc(),
    ).limit(max(1, min(limit, 200)))
    result = await session.execute(statement)
    return [relationship_thread_dict(item) for item in result.scalars().all()]


async def get_relationship_thread(
    session: AsyncSession,
    user_id: str,
    thread_id: str,
) -> dict[str, Any]:
    """读取当前用户的一条线程和最近最多 100 条状态事件。"""

    result = await session.execute(
        select(RelationshipThread).where(
            RelationshipThread.id == parse_thread_id(thread_id),
            RelationshipThread.user_id == parse_user_id(user_id),
        )
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise RelationshipThreadServiceError("关系线程不存在", status_code=404)
    return await build_thread_snapshot(session, thread)


async def require_locked_thread(
    session: AsyncSession,
    user_id: str,
    thread_id: str,
) -> RelationshipThread:
    """按所有者查询并锁定线程，不存在时返回统一 404。"""

    result = await session.execute(
        select(RelationshipThread)
        .where(
            RelationshipThread.id == parse_thread_id(thread_id),
            RelationshipThread.user_id == parse_user_id(user_id),
        )
        .with_for_update()
    )
    thread = result.scalar_one_or_none()
    if thread is None:
        raise RelationshipThreadServiceError("关系线程不存在", status_code=404)
    return thread


def capture_relationship_candidates_sync(
    user_id: str,
    raw_candidates: Any,
    *,
    source_text: str,
    source_message_id: str,
    source_turn_id: str | None = None,
    now: datetime | None = None,
) -> int:
    """在主聊天线程中幂等落库模型/规则识别出的关系线程候选。

    该入口使用同步 Session，因为 ``aura_agent`` 本身在线程池执行同步 LangGraph。
    没有稳定 ``source_message_id`` 时直接跳过，避免 SSE 重连用随机 ID 制造重复。
    单个候选失败只记录日志；危机内容由上游完全不传入本函数。
    """

    normalized_source_id = clean_optional_text(source_message_id)
    if not normalized_source_id:
        return 0
    if len(normalized_source_id) > 128:
        logging.error("关系线程候选来源消息 ID 超过 128 字符，已拒绝持久化")
        return 0
    parsed_user_id = parse_user_id(user_id)
    candidates = normalize_thread_candidates(raw_candidates, source_text, now=now)
    if not candidates:
        return 0

    changed = 0
    try:
        with SyncSessionLocal.begin() as session:
            # 同一用户消息的整个抽取批次使用事务级 advisory lock 串行化。锁内再查
            # 是否已有任一抽取事件，使模型重试时即使标题或摘要漂移也整体重放首次
            # 结果，而不是依据候选文案生成第二组来源键。
            extraction_lock_key = f"aura_relationship_extract:{parsed_user_id}:{normalized_source_id}"
            session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": extraction_lock_key},
            )
            user_exists = session.execute(
                select(Users.id).where(Users.id == parsed_user_id).with_for_update()
            ).scalar_one_or_none()
            if user_exists is None:
                return 0
            already_processed = session.execute(
                select(RelationshipThreadEvent.id)
                .join(
                    RelationshipThread,
                    RelationshipThreadEvent.thread_id == RelationshipThread.id,
                )
                .where(
                    RelationshipThread.user_id == parsed_user_id,
                    RelationshipThreadEvent.actor == "system",
                    RelationshipThreadEvent.source_message_id == normalized_source_id,
                    RelationshipThreadEvent.client_action_id.like("extract:%"),
                )
                .limit(1)
            ).scalar_one_or_none()
            if already_processed is not None:
                return 0
            for candidate in candidates:
                source_key = build_source_key(
                    str(parsed_user_id),
                    normalized_source_id,
                    candidate,
                )
                if candidate["operation"] == "create":
                    changed += capture_created_candidate(
                        session,
                        parsed_user_id,
                        candidate,
                        source_key=source_key,
                        source_message_id=normalized_source_id,
                        source_turn_id=source_turn_id,
                        now=now,
                    )
                else:
                    changed += capture_transition_candidate(
                        session,
                        parsed_user_id,
                        candidate,
                        source_key=source_key,
                        source_message_id=normalized_source_id,
                        now=now,
                    )
    except IntegrityError:
        # 唯一来源键会让并发抽取至多写入一次；另一事务成功时当前事务无需重试。
        logging.info("关系线程候选已经由并发请求写入，忽略重复 source_message_id=%s", normalized_source_id)
        return 0
    except Exception:
        logging.exception("关系线程候选保存失败 user_id=%s", parsed_user_id)
        return 0
    return changed


def apply_reply_thread_actions_sync(
    user_id: str,
    raw_actions: Any,
    context_items: list[dict[str, Any]],
    *,
    turn_id: str,
    now: datetime | None = None,
) -> int:
    """在 Aura 确实发出回访问句后，把对应到期线程标为已跟进。

    主模型只能返回本轮上下文中的短引用 ``T1`` 至 ``T12``，不能提交数据库
    UUID。服务端再把引用映射回本轮加载的线程，并且只接受 ``is_due=true``、
    当前仍为 ``pending`` 的记录。稳定动作 ID 让同一回复重放不会重复追加事件。
    """

    try:
        parsed_user_id = parse_user_id(user_id)
    except RelationshipThreadServiceError:
        return 0
    normalized_turn_id = clean_optional_text(turn_id)
    if not normalized_turn_id or len(normalized_turn_id) > 128 or not isinstance(raw_actions, list):
        return 0

    ref_map = {
        str(item.get("ref")): item
        for item in context_items
        if item.get("ref") and item.get("id") and item.get("is_due") is True
    }
    requested_refs = {
        str(action.get("thread_ref") or action.get("threadRef"))
        for action in raw_actions
        if isinstance(action, dict) and action.get("action") == "follow_up"
    }
    targets = [ref_map[ref] for ref in requested_refs if ref in ref_map]
    if not targets:
        return 0

    occurred_at = normalize_utc_datetime(now or datetime.now(UTC))
    changed = 0
    try:
        with SyncSessionLocal.begin() as session:
            for item in targets:
                try:
                    target_id = UUID(str(item["id"]))
                except (TypeError, ValueError):
                    continue
                thread = session.execute(
                    select(RelationshipThread)
                    .where(
                        RelationshipThread.id == target_id,
                        RelationshipThread.user_id == parsed_user_id,
                    )
                    .with_for_update()
                ).scalar_one_or_none()
                if thread is None or thread.status != "pending":
                    continue

                digest = hashlib.sha256(
                    f"{parsed_user_id}:{normalized_turn_id}:{thread.id}:follow_up".encode("utf-8")
                ).hexdigest()
                client_action_id = f"reply-followup:{digest}"[:128]
                replay = session.execute(
                    select(RelationshipThreadEvent.id).where(
                        RelationshipThreadEvent.thread_id == thread.id,
                        RelationshipThreadEvent.client_action_id == client_action_id,
                    )
                ).scalar_one_or_none()
                if replay is not None:
                    continue

                state_before = thread_state_for_event(thread)
                thread.status = "followed_up"
                thread.last_followed_up_at = occurred_at
                thread.follow_up_at = None
                thread.version += 1
                thread.updated_at = occurred_at
                session.add(
                    RelationshipThreadEvent(
                        thread_id=thread.id,
                        sequence_no=thread.version,
                        actor="aura",
                        event_type="followed_up",
                        state_before=state_before,
                        state_after=thread_state_for_event(thread),
                        source_message_id=None,
                        client_action_id=client_action_id,
                        metadata_json={
                            "source": "structured_reply",
                            "turn_id": normalized_turn_id,
                            "thread_ref": item["ref"],
                        },
                        occurred_at=occurred_at,
                    )
                )
                changed += 1
    except Exception:
        logging.exception("Aura 跟进线程状态保存失败 user_id=%s turn_id=%s", user_id, normalized_turn_id)
        return 0
    return changed


def capture_created_candidate(
    session,
    user_id: UUID,
    candidate: dict[str, Any],
    *,
    source_key: str,
    source_message_id: str,
    source_turn_id: str | None,
    now: datetime | None,
) -> int:
    """在同步事务中写入一条新的自动抽取线程；来源键已存在时返回 0。"""

    existing = session.execute(
        select(RelationshipThread.id).where(
            RelationshipThread.user_id == user_id,
            RelationshipThread.source_key == source_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return 0

    occurred_at = normalize_utc_datetime(now or datetime.now(UTC))
    follow_up_at = parse_optional_iso_datetime(candidate.get("follow_up_at"))
    thread = RelationshipThread(
        user_id=user_id,
        thread_type=candidate["thread_type"],
        perspective=candidate["perspective"],
        world_layer=candidate["world_layer"],
        title=candidate["title"],
        summary=candidate["summary"],
        status="pending",
        source_key=source_key,
        source_message_id=source_message_id,
        source_turn_id=clean_optional_text(source_turn_id),
        follow_up_at=follow_up_at,
        version=1,
        metadata_json={
            "capture_source": "turn_judge",
            "extractor_version": "relationship-thread-v1",
            "proactive_allowed": bool(candidate.get("proactive_allowed")),
        },
        created_at=occurred_at,
        updated_at=occurred_at,
    )
    session.add(thread)
    session.flush()
    session.add(
        RelationshipThreadEvent(
            thread_id=thread.id,
            sequence_no=1,
            actor="system",
            event_type="created",
            state_before={},
            state_after=thread_state_for_event(thread),
            source_message_id=source_message_id,
            client_action_id=f"extract:{source_key[-64:]}",
            metadata_json={"candidate": candidate},
            occurred_at=occurred_at,
        )
    )
    return 1


def capture_transition_candidate(
    session,
    user_id: UUID,
    candidate: dict[str, Any],
    *,
    source_key: str,
    source_message_id: str,
    now: datetime | None,
) -> int:
    """按候选携带的明确目标 ID 推进已有线程；模糊目标不会猜测匹配。"""

    target_id = candidate.get("target_id")
    if not target_id:
        return 0
    thread = session.execute(
        select(RelationshipThread)
        .where(
            RelationshipThread.id == UUID(target_id),
            RelationshipThread.user_id == user_id,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if thread is None or thread.status in TERMINAL_THREAD_STATUSES:
        return 0

    client_action_id = f"extract:{source_key[-64:]}"
    replay = session.execute(
        select(RelationshipThreadEvent.id).where(
            RelationshipThreadEvent.thread_id == thread.id,
            RelationshipThreadEvent.client_action_id == client_action_id,
        )
    ).scalar_one_or_none()
    if replay is not None:
        return 0

    occurred_at = normalize_utc_datetime(now or datetime.now(UTC))
    before = thread_state_for_event(thread)
    apply_candidate_transition(thread, candidate, occurred_at)
    thread.version += 1
    thread.updated_at = occurred_at
    session.add(
        RelationshipThreadEvent(
            thread_id=thread.id,
            sequence_no=thread.version,
            actor="system",
            event_type=ACTION_EVENT_TYPES[candidate["operation"]],
            state_before=before,
            state_after=thread_state_for_event(thread),
            source_message_id=source_message_id,
            client_action_id=client_action_id,
            metadata_json={"candidate": candidate},
            occurred_at=occurred_at,
        )
    )
    return 1


def apply_transition(
    thread: RelationshipThread,
    request: RelationshipThreadTransitionRequest,
    occurred_at: datetime,
) -> None:
    """根据经过 Pydantic 校验的 API 请求原地修改线程快照。"""

    fields_set = request.model_fields_set
    if request.action == "update":
        if not fields_set.intersection({"title", "summary", "follow_up_at", "metadata"}):
            raise RelationshipThreadServiceError("更新线程时至少提供一个需要修改的字段")
        if "title" in fields_set and request.title is not None:
            thread.title = require_non_blank(request.title, "线程标题")
        if "summary" in fields_set and request.summary is not None:
            thread.summary = require_non_blank(request.summary, "线程摘要")
        if "follow_up_at" in fields_set:
            thread.follow_up_at = normalize_optional_datetime(request.follow_up_at)
        if request.metadata:
            thread.metadata_json = {
                **dict(thread.metadata_json or {}),
                **sanitize_user_metadata(request.metadata),
            }
        return
    if request.action == "follow_up":
        thread.status = "followed_up"
        thread.last_followed_up_at = occurred_at
        thread.follow_up_at = (
            normalize_optional_datetime(request.follow_up_at)
            if "follow_up_at" in fields_set
            else None
        )
        if request.summary:
            thread.summary = require_non_blank(request.summary, "线程摘要")
        return
    thread.status = "resolved" if request.action == "resolve" else "abandoned"
    thread.resolved_at = occurred_at
    thread.follow_up_at = None
    if request.summary:
        thread.summary = require_non_blank(request.summary, "线程摘要")


def apply_candidate_transition(
    thread: RelationshipThread,
    candidate: dict[str, Any],
    occurred_at: datetime,
) -> None:
    """把模型候选限制为和 API 相同的状态机变更。"""

    operation = candidate["operation"]
    if operation == "update":
        if candidate.get("title"):
            thread.title = candidate["title"]
        if candidate.get("summary"):
            thread.summary = candidate["summary"]
        if candidate.get("follow_up_at"):
            thread.follow_up_at = parse_optional_iso_datetime(candidate["follow_up_at"])
        return
    thread.status = "resolved" if operation == "resolve" else "abandoned"
    thread.resolved_at = occurred_at
    thread.follow_up_at = None


async def build_thread_snapshot(
    session: AsyncSession,
    thread: RelationshipThread,
    *,
    event: RelationshipThreadEvent | None = None,
    idempotent_replay: bool = False,
) -> dict[str, Any]:
    """组合线程当前状态、本轮事件和最近事件，供 API 稳定返回。"""

    result = await session.execute(
        select(RelationshipThreadEvent)
        .where(RelationshipThreadEvent.thread_id == thread.id)
        .order_by(RelationshipThreadEvent.sequence_no.desc())
        .limit(100)
    )
    return {
        "thread": relationship_thread_dict(thread),
        "event": relationship_thread_event_dict(event) if event else None,
        "events": [relationship_thread_event_dict(item) for item in result.scalars().all()],
        "idempotentReplay": idempotent_replay,
    }


def relationship_thread_dict(thread: RelationshipThread) -> dict[str, Any]:
    """把 ORM 线程转换为不暴露内部来源哈希的公共字典。"""

    return {
        "id": str(thread.id),
        "threadType": thread.thread_type,
        "perspective": thread.perspective,
        "worldLayer": thread.world_layer,
        "title": thread.title,
        "summary": thread.summary,
        "status": thread.status,
        "sourceMessageId": thread.source_message_id,
        "sourceTurnId": thread.source_turn_id,
        "followUpAt": iso_datetime(thread.follow_up_at),
        "lastFollowedUpAt": iso_datetime(thread.last_followed_up_at),
        "resolvedAt": iso_datetime(thread.resolved_at),
        "version": thread.version,
        "metadata": dict(thread.metadata_json or {}),
        "createdAt": iso_datetime(thread.created_at),
        "updatedAt": iso_datetime(thread.updated_at),
    }


def relationship_thread_event_dict(event: RelationshipThreadEvent) -> dict[str, Any]:
    """把不可变事件转换为 API 字典。"""

    return {
        "id": str(event.id),
        "sequenceNo": event.sequence_no,
        "actor": event.actor,
        "eventType": event.event_type,
        "stateBefore": dict(event.state_before or {}),
        "stateAfter": dict(event.state_after or {}),
        "sourceMessageId": event.source_message_id,
        "clientActionId": event.client_action_id,
        "metadata": dict(event.metadata_json or {}),
        "occurredAt": iso_datetime(event.occurred_at),
    }


def thread_state_for_event(thread: RelationshipThread) -> dict[str, Any]:
    """生成事件中可重放的业务快照，不复制用户 ID 和内部 ORM 状态。"""

    return {
        "thread_type": thread.thread_type,
        "perspective": thread.perspective,
        "world_layer": thread.world_layer,
        "title": thread.title,
        "summary": thread.summary,
        "status": thread.status,
        "follow_up_at": iso_datetime(thread.follow_up_at),
        "last_followed_up_at": iso_datetime(thread.last_followed_up_at),
        "resolved_at": iso_datetime(thread.resolved_at),
        "version": thread.version,
        "metadata": dict(thread.metadata_json or {}),
    }


def ensure_create_replay_matches(
    event: RelationshipThreadEvent | None,
    expected: dict[str, Any],
) -> None:
    """用原始创建事件校验幂等重放，避免后续更新影响比较结果。"""

    actual = dict(event.metadata_json or {}).get("request") if event is not None else None
    if actual != expected:
        raise RelationshipThreadServiceError(
            "这个 clientRequestId 已用于参数不同的关系线程，请生成新的 ID",
            status_code=409,
        )


def ensure_transition_replay_matches(
    event: RelationshipThreadEvent,
    expected: dict[str, Any],
) -> None:
    """拒绝把同一个状态动作幂等 ID 复用于不同操作或参数。"""

    actual = dict(event.metadata_json or {}).get("request")
    if actual != expected:
        raise RelationshipThreadServiceError(
            "这个 clientActionId 已用于参数不同的线程操作，请生成新的 ID",
            status_code=409,
        )


def create_request_payload(request: RelationshipThreadCreateRequest) -> dict[str, Any]:
    """提取用于创建幂等参数漂移检查的规范业务字段。"""

    return {
        "thread_type": request.thread_type,
        "perspective": request.perspective,
        "world_layer": request.world_layer,
        "title": require_non_blank(request.title, "线程标题"),
        "summary": require_non_blank(request.summary, "线程摘要"),
        "follow_up_at": iso_datetime(normalize_optional_datetime(request.follow_up_at)),
        "source_message_id": clean_optional_text(request.source_message_id),
        "source_turn_id": clean_optional_text(request.source_turn_id),
        "metadata": sanitize_user_metadata(request.metadata),
    }


def transition_request_payload(request: RelationshipThreadTransitionRequest) -> dict[str, Any]:
    """提取用于状态动作幂等比较的规范业务字段。"""

    return {
        "action": request.action,
        "expected_version": request.expected_version,
        "title": require_non_blank(request.title, "线程标题") if request.title is not None else None,
        "summary": require_non_blank(request.summary, "线程摘要") if request.summary is not None else None,
        "follow_up_at": iso_datetime(normalize_optional_datetime(request.follow_up_at)),
        "source_message_id": clean_optional_text(request.source_message_id),
        "metadata": sanitize_user_metadata(request.metadata),
    }


def normalize_optional_datetime(value: datetime | None) -> datetime | None:
    """把可选日期时间统一成 UTC；无时区值按上海时间解释由 Pydantic 保留。"""

    if value is None:
        return None
    if value.tzinfo is None:
        from zoneinfo import ZoneInfo

        value = value.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return value.astimezone(UTC)


def normalize_utc_datetime(value: datetime) -> datetime:
    """把必填日期时间统一成 UTC，无时区值按 UTC 解释。"""

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_optional_iso_datetime(value: Any) -> datetime | None:
    """解析候选中的 UTC ISO 时间；无效值返回 ``None``。"""

    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return normalize_utc_datetime(parsed)


def clean_optional_text(value: Any) -> str | None:
    """清理可选来源 ID，空白统一为 ``None``。"""

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def require_non_blank(value: str, field_label: str) -> str:
    """清理必填业务文本，并拒绝只包含空白的 Pydantic 合法字符串。"""

    normalized = str(value or "").strip()
    if not normalized:
        raise RelationshipThreadServiceError(f"{field_label}不能为空")
    return normalized


def sanitize_user_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    """移除只允许后台维护的元数据键，防止 API 伪造主动授权和抽取来源。"""

    reserved_keys = {"proactive_allowed", "capture_source", "extractor_version"}
    return {
        str(key): item
        for key, item in dict(value or {}).items()
        if str(key) not in reserved_keys
    }


def iso_datetime(value: datetime | None) -> str | None:
    """把可选日期时间序列化为 ISO 字符串。"""

    return value.isoformat() if isinstance(value, datetime) else None
