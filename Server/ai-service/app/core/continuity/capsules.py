"""时间胶囊与秘密保险箱的条件评估、状态机和 outbox 衔接。

这个模块刻意不注册成主聊天 Tool。创建权限来自认证 HTTP 请求，或来自记忆 judge
已经确认的用户明确指令；时间、关键词、项目和 GitHub 条件都由服务端代码评估。
条件成立后仅生成 ``proactive_message``，最终状态要等主动消息成功写入聊天历史后
才推进到 ``delivered``。
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from datetime import UTC, datetime
from typing import Any, Iterable
from uuid import UUID, uuid4

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ConditionalMessage,
    ConditionalMessageEvent,
    ProactiveMessage,
    Users,
)
from app.db.session import SyncSessionLocal
from app.schemas.capsule import ConditionalMessageCreateRequest

CAPSULE_TRIGGER_TYPE = "conditional_message"
MAX_CONDITION_SCAN = 200
_password_hash = PasswordHash.recommended()


class ConditionalMessageServiceError(ValueError):
    """可安全返回给客户端的中文条件消息领域错误。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


async def create_conditional_message(
    session: AsyncSession,
    user_id: str,
    request: ConditionalMessageCreateRequest,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """为当前用户幂等创建一条密封消息。

    Args:
        session: 当前 HTTP 请求持有的异步数据库会话。
        user_id: 从 JWT ``sub`` 得到的权威用户 ID。
        request: 正文、条件、幂等键和可选来源信息。
        now: 测试可注入的当前时间；生产默认 UTC 当前时间。

    Returns:
        不泄露密封正文的公开快照。同一 ``clientRequestId`` 的相同请求会返回
        原记录；复用该 ID 却改变业务内容会返回 409。
    """

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    reference_now = normalize_utc(now or datetime.now(UTC))
    values = build_create_values(parsed_user_id, request, reference_now)
    existing = await find_by_dedupe(session, parsed_user_id, values["dedupe_key"])
    if existing is not None:
        ensure_same_create(existing, values)
        return conditional_message_dict(existing)

    record = ConditionalMessage(id=uuid4(), **values)
    session.add(record)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await find_by_dedupe(session, parsed_user_id, values["dedupe_key"])
        if existing is None:
            raise
        ensure_same_create(existing, values)
        return conditional_message_dict(existing)
    await session.refresh(record)
    return conditional_message_dict(record)


async def list_conditional_messages(
    session: AsyncSession,
    user_id: str,
    *,
    status: str | None = None,
    message_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按创建时间倒序读取当前用户的条件消息，不提前暴露密封正文。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    statement = select(ConditionalMessage).where(ConditionalMessage.user_id == parsed_user_id)
    if status:
        statement = statement.where(ConditionalMessage.status == status)
    if message_type:
        statement = statement.where(ConditionalMessage.message_type == message_type)
    result = await session.execute(
        statement.order_by(ConditionalMessage.created_at.desc()).limit(max(1, min(limit, 200)))
    )
    return [conditional_message_dict(item) for item in result.scalars().all()]


async def get_conditional_message(
    session: AsyncSession,
    user_id: str,
    message_id: str,
) -> dict[str, Any]:
    """读取一条属于当前用户的条件消息；其他用户的记录按不存在处理。"""

    record = await require_record(session, user_id, message_id)
    return conditional_message_dict(record)


async def cancel_conditional_message(
    session: AsyncSession,
    user_id: str,
    message_id: str,
    *,
    expected_version: int | None = None,
    client_action_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """取消尚未真正投递的消息，并同步取消可能已生成的 outbox。

    ``client_action_id`` 会写入 metadata，重复相同动作直接返回当前状态。已投递、
    已过期或使用另一个动作取消的记录不会被悄悄改写。
    """

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    parsed_message_id = parse_uuid(message_id, "条件消息 ID")
    result = await session.execute(
        select(ConditionalMessage)
        .where(
            ConditionalMessage.id == parsed_message_id,
            ConditionalMessage.user_id == parsed_user_id,
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise ConditionalMessageServiceError("条件消息不存在", 404)
    metadata = dict(record.metadata_json or {})
    if metadata.get("cancel_action_id") == client_action_id:
        return conditional_message_dict(record)
    if expected_version is not None and record.version != expected_version:
        raise ConditionalMessageServiceError("条件消息版本已变化，请刷新后重试", 409)
    if record.status == "delivered":
        raise ConditionalMessageServiceError("消息已经投递，不能再取消", 409)
    if record.status in {"cancelled", "expired"}:
        raise ConditionalMessageServiceError("条件消息已经结束，不能重复取消", 409)

    reference_now = normalize_utc(now or datetime.now(UTC))
    outbox = None
    if record.outbox_message_id is not None:
        outbox_result = await session.execute(
            select(ProactiveMessage)
            .where(
                ProactiveMessage.id == record.outbox_message_id,
                ProactiveMessage.user_id == parsed_user_id,
            )
            .with_for_update()
        )
        outbox = outbox_result.scalar_one_or_none()
        if outbox is not None and outbox.status == "sent":
            raise ConditionalMessageServiceError("消息已经写入聊天历史，不能再取消", 409)
        if outbox is not None and outbox.status == "processing":
            raise ConditionalMessageServiceError("消息正在投递，暂时不能取消", 409)

    record.status = "cancelled"
    record.cancelled_at = reference_now
    record.version += 1
    metadata["cancel_action_id"] = client_action_id
    record.metadata_json = metadata
    if outbox is not None and outbox.status == "pending":
        outbox.status = "cancelled"
        outbox.cancelled_at = reference_now
        outbox.claimed_until = None
    await session.commit()
    return conditional_message_dict(record)


async def trigger_keyword_messages(
    session: AsyncSession,
    user_id: str,
    message: str,
    *,
    event_id: str,
    now: datetime | None = None,
) -> int:
    """用本轮真实用户文本评估关键词条件，并返回新进入队列的数量。"""

    payload = {"messageHash": text_digest(message)}
    return await trigger_event_messages(
        session,
        user_id,
        event_type="keyword",
        event_id=event_id,
        payload=payload,
        condition_type="keyword",
        matcher=lambda condition: keyword_matches(condition, message),
        now=now,
    )


def trigger_keyword_messages_sync(
    user_id: str,
    message: str,
    *,
    event_id: str,
    now: datetime | None = None,
) -> int:
    """在同步 LangGraph 聊天线程完成历史写入后评估关键词条件。

    普通对话使用同步 SQLAlchemy 会话，因此这里提供与异步事件入口相同的 inbox
    幂等边界。事件查询使用普通行锁而不是 ``SKIP LOCKED``，防止一次性聊天事件
    因并发锁竞争被永久漏掉。
    """

    try:
        parsed_user_id = UUID(str(user_id))
    except (TypeError, ValueError):
        return 0
    reference_now = normalize_utc(now or datetime.now(UTC))
    payload = {"messageHash": text_digest(message)}
    try:
        with SyncSessionLocal.begin() as session:
            statement = (
                pg_insert(ConditionalMessageEvent)
                .values(
                    id=uuid4(),
                    user_id=parsed_user_id,
                    event_type="keyword",
                    event_id=str(event_id)[:128],
                    payload=payload,
                    matched_count=0,
                    occurred_at=reference_now,
                )
                .on_conflict_do_nothing(
                    constraint="uq_conditional_message_event_user_event"
                )
                .returning(ConditionalMessageEvent.id)
            )
            inserted_id = session.execute(statement).scalar_one_or_none()
            if inserted_id is None:
                existing = session.execute(
                    select(ConditionalMessageEvent).where(
                        ConditionalMessageEvent.user_id == parsed_user_id,
                        ConditionalMessageEvent.event_type == "keyword",
                        ConditionalMessageEvent.event_id == str(event_id)[:128],
                    )
                ).scalar_one()
                if canonical_json(existing.payload_json) != canonical_json(payload):
                    logging.warning("关键词事件 ID 被不同消息复用 event_id=%s", event_id)
                    return 0
                return existing.matched_count

            event = session.get(ConditionalMessageEvent, inserted_id)
            records = session.execute(
                select(ConditionalMessage)
                .where(
                    ConditionalMessage.user_id == parsed_user_id,
                    ConditionalMessage.status == "sealed",
                    ConditionalMessage.condition_type == "keyword",
                )
                .order_by(ConditionalMessage.created_at.asc())
                .with_for_update()
                .limit(MAX_CONDITION_SCAN)
            ).scalars().all()
            matched = 0
            for record in records:
                if expire_if_needed(record, reference_now):
                    continue
                if is_same_creation_message(record, "keyword", event_id):
                    continue
                if not keyword_matches(dict(record.condition_json or {}), message):
                    continue
                if queue_record(
                    session,
                    record,
                    reference_now,
                    "keyword",
                    {"eventId": event_id},
                ):
                    matched += 1
            event.matched_count = matched
            return matched
    except Exception:
        logging.exception("关键词条件消息评估失败 user_id=%s event_id=%s", parsed_user_id, event_id)
        return 0


async def trigger_project_status_messages(
    session: AsyncSession,
    user_id: str,
    *,
    project_key: str,
    status: str,
    event_id: str,
    metadata: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> int:
    """评估一次共同项目状态变化，只消费完全匹配的密封消息。"""

    payload = {
        "projectKey": normalize_token(project_key),
        "status": normalize_token(status),
        "metadata": safe_metadata(metadata),
    }
    return await trigger_event_messages(
        session,
        user_id,
        event_type="project_status",
        event_id=event_id,
        payload=payload,
        condition_type="project_status",
        matcher=lambda condition: project_status_matches(condition, payload),
        now=now,
    )


async def trigger_github_event_messages(
    session: AsyncSession,
    user_id: str,
    *,
    repository: str,
    event: str,
    delivery_id: str,
    action: str | None = None,
    conclusion: str | None = None,
    ref: str | None = None,
    metadata: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> int:
    """评估一条规范化 GitHub 事件；``delivery_id`` 是事件幂等边界。"""

    payload = {
        "repository": normalize_token(repository),
        "event": normalize_token(event),
        "action": normalize_optional_token(action),
        "conclusion": normalize_optional_token(conclusion),
        "ref": normalize_optional_token(ref),
        "metadata": safe_metadata(metadata),
    }
    return await trigger_event_messages(
        session,
        user_id,
        event_type="github_event",
        event_id=delivery_id,
        payload=payload,
        condition_type="github_event",
        matcher=lambda condition: github_event_matches(condition, payload),
        now=now,
    )


async def unlock_passphrase_message(
    session: AsyncSession,
    user_id: str,
    message_id: str,
    *,
    passphrase: str,
    event_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """校验口令并把指定保险箱放入 outbox；口令明文从不写入数据库。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    parsed_message_id = parse_uuid(message_id, "条件消息 ID")
    reference_now = normalize_utc(now or datetime.now(UTC))
    event, created = await ensure_event(
        session,
        parsed_user_id,
        "passphrase",
        event_id,
        {"conditionalMessageId": str(parsed_message_id)},
        reference_now,
    )
    if not created:
        record = await require_record(session, user_id, message_id)
        return conditional_message_dict(record)

    result = await session.execute(
        select(ConditionalMessage)
        .where(
            ConditionalMessage.id == parsed_message_id,
            ConditionalMessage.user_id == parsed_user_id,
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if record is None:
        await session.rollback()
        raise ConditionalMessageServiceError("条件消息不存在", 404)
    if record.condition_type != "passphrase":
        await session.rollback()
        raise ConditionalMessageServiceError("这条消息不是口令保险箱", 409)
    if record.status != "sealed":
        event.matched_count = 0
        await session.commit()
        return conditional_message_dict(record)
    if not verify_secret(passphrase, record.unlock_secret_hash):
        await session.rollback()
        raise ConditionalMessageServiceError("保险箱口令不正确", 403)

    queued = queue_record(session, record, reference_now, "passphrase", {"eventId": event_id})
    event.matched_count = 1 if queued is not None else 0
    await session.commit()
    return conditional_message_dict(record)


async def trigger_event_messages(
    session: AsyncSession,
    user_id: str,
    *,
    event_type: str,
    event_id: str,
    payload: dict[str, Any],
    condition_type: str,
    matcher,
    now: datetime | None = None,
) -> int:
    """为关键词、项目或 GitHub 事件执行统一的幂等匹配事务。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    reference_now = normalize_utc(now or datetime.now(UTC))
    event, created = await ensure_event(
        session,
        parsed_user_id,
        event_type,
        event_id,
        payload,
        reference_now,
    )
    if not created:
        return event.matched_count

    result = await session.execute(
        select(ConditionalMessage)
        .where(
            ConditionalMessage.user_id == parsed_user_id,
            ConditionalMessage.status == "sealed",
            ConditionalMessage.condition_type == condition_type,
        )
        .order_by(ConditionalMessage.created_at.asc())
        .with_for_update()
        .limit(MAX_CONDITION_SCAN)
    )
    matched = 0
    for record in result.scalars().all():
        if expire_if_needed(record, reference_now):
            continue
        if is_same_creation_message(record, event_type, event_id):
            continue
        if not matcher(dict(record.condition_json or {})):
            continue
        if queue_record(session, record, reference_now, event_type, {"eventId": event_id, **payload}):
            matched += 1
    event.matched_count = matched
    await session.commit()
    return matched


async def ensure_due_conditional_messages(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = MAX_CONDITION_SCAN,
) -> list[ProactiveMessage]:
    """扫描到期时间胶囊并创建 outbox，供主动消息调度周期调用。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    expired_count = await expire_due_records(session, reference_now)
    result = await session.execute(
        select(ConditionalMessage)
        .where(
            ConditionalMessage.status == "sealed",
            ConditionalMessage.condition_type == "time",
            ConditionalMessage.deliver_at.is_not(None),
            ConditionalMessage.deliver_at <= reference_now,
        )
        .order_by(ConditionalMessage.deliver_at.asc())
        .with_for_update(skip_locked=True)
        .limit(max(1, min(limit, MAX_CONDITION_SCAN)))
    )
    messages: list[ProactiveMessage] = []
    for record in result.scalars().all():
        if expire_if_needed(record, reference_now):
            continue
        outbox = queue_record(session, record, reference_now, "time", {"deliverAt": record.deliver_at.isoformat()})
        if outbox is not None:
            messages.append(outbox)
    if messages:
        await session.commit()
    elif expired_count:
        await session.commit()
    return messages


async def mark_conditional_message_delivered(
    session: AsyncSession,
    proactive: ProactiveMessage,
    now: datetime,
) -> None:
    """在 outbox 成功写入聊天历史后推进来源消息，重复执行不会重复变更。"""

    changed = await stage_conditional_message_delivery_state(session, proactive, now)
    if changed:
        await session.commit()


async def stage_conditional_message_delivery_state(
    session: AsyncSession,
    proactive: ProactiveMessage,
    now: datetime,
) -> bool:
    """在调用方事务内同步一条 outbox 的来源状态，不自行提交。

    返回值表示业务记录是否发生变化。主动发送主流程用它把 ``sent`` 与
    ``delivered`` 放进同一次 PostgreSQL 提交；对账流程也复用它修复旧崩溃窗口。
    """

    if proactive.trigger_type != CAPSULE_TRIGGER_TYPE or proactive.status not in {"sent", "failed"}:
        return False
    raw_message_id = dict(proactive.metadata_json or {}).get("conditional_message_id")
    try:
        message_id = UUID(str(raw_message_id))
    except (TypeError, ValueError):
        return False
    result = await session.execute(
        select(ConditionalMessage)
        .where(
            ConditionalMessage.id == message_id,
            ConditionalMessage.user_id == proactive.user_id,
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if record is None or record.outbox_message_id != proactive.id:
        return False
    target_status = "delivered" if proactive.status == "sent" else "failed"
    if record.status == target_status:
        return False
    if record.status != "queued":
        logging.warning(
            "条件消息 outbox 已发送但业务状态异常 message_id=%s status=%s",
            record.id,
            record.status,
        )
        return False
    record.status = target_status
    if target_status == "delivered":
        record.delivered_at = normalize_utc(now)
    record.version += 1
    return True


async def reconcile_conditional_message_outbox(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = MAX_CONDITION_SCAN,
) -> int:
    """修复 outbox 已进入终态、来源仍 queued 的极小崩溃窗口。

    此函数只读取已经 ``sent``/``failed`` 的 outbox 并补业务状态，绝不会再次调用
    checkpoint 写入，所以对账不会向聊天历史重复发送消息。
    """

    reference_now = normalize_utc(now or datetime.now(UTC))
    result = await session.execute(
        select(ProactiveMessage)
        .join(
            ConditionalMessage,
            ConditionalMessage.outbox_message_id == ProactiveMessage.id,
        )
        .where(
            ConditionalMessage.status == "queued",
            ProactiveMessage.trigger_type == CAPSULE_TRIGGER_TYPE,
            ProactiveMessage.status.in_(("sent", "failed")),
        )
        .order_by(ProactiveMessage.updated_at.asc())
        .limit(max(1, min(limit, MAX_CONDITION_SCAN)))
    )
    changed = 0
    for proactive in result.scalars().all():
        if await stage_conditional_message_delivery_state(session, proactive, reference_now):
            changed += 1
    if changed:
        await session.commit()
    return changed


def capture_conditional_candidates_sync(
    user_id: str,
    candidates: Iterable[dict[str, Any]],
    *,
    source_message_id: str,
    source_turn_id: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """持久化 judge 已确认的显式条件消息候选，并返回给主模型的确认摘要。

    每个候选都用 ``source_message_id + 顺序`` 形成稳定幂等键。数据库故障会记录
    中文日志并返回空列表，让普通聊天继续；没有稳定客户端消息 ID 时调用方不应
    进入此函数。
    """

    try:
        parsed_user_id = UUID(str(user_id))
    except (TypeError, ValueError):
        return []
    reference_now = normalize_utc(now or datetime.now(UTC))
    created: list[dict[str, Any]] = []
    try:
        with SyncSessionLocal.begin() as session:
            if session.execute(select(Users.id).where(Users.id == parsed_user_id)).scalar_one_or_none() is None:
                return []
            for index, candidate in enumerate(candidates):
                try:
                    request = ConditionalMessageCreateRequest.model_validate(
                        {
                            **candidate,
                            "clientRequestId": f"chat:{source_message_id}:{index}",
                            "sourceMessageId": source_message_id,
                            "sourceTurnId": source_turn_id,
                        }
                    )
                    values = build_create_values(parsed_user_id, request, reference_now)
                except Exception:
                    logging.warning("条件消息候选格式无效，已跳过 candidate_index=%s", index)
                    continue
                existing = session.execute(
                    select(ConditionalMessage).where(
                        ConditionalMessage.user_id == parsed_user_id,
                        ConditionalMessage.dedupe_key == values["dedupe_key"],
                    )
                ).scalar_one_or_none()
                if existing is None:
                    existing = ConditionalMessage(id=uuid4(), **values)
                    session.add(existing)
                    session.flush()
                else:
                    ensure_same_create(existing, values)
                created.append(conditional_message_dict(existing))
        return created
    except Exception:
        logging.exception("显式时间胶囊或秘密保险箱保存失败 user_id=%s", parsed_user_id)
        return []


def build_create_values(
    user_id: UUID,
    request: ConditionalMessageCreateRequest,
    now: datetime,
) -> dict[str, Any]:
    """把经过 Pydantic 校验的请求转换成可写入 ORM 的规范字段。"""

    deliver_at = normalize_optional_datetime(request.deliver_at)
    expires_at = normalize_optional_datetime(request.expires_at)
    if deliver_at is not None and deliver_at <= now:
        raise ConditionalMessageServiceError("时间胶囊的 deliverAt 必须晚于当前时间")
    if expires_at is not None and expires_at <= now:
        raise ConditionalMessageServiceError("expiresAt 必须晚于当前时间")
    if deliver_at is not None and expires_at is not None and expires_at <= deliver_at:
        raise ConditionalMessageServiceError("expiresAt 必须晚于 deliverAt")

    condition = normalize_condition(request.condition_type, request.condition)
    unlock_secret_hash = None
    if request.condition_type == "passphrase":
        unlock_secret_hash = _password_hash.hash(request.passphrase or "")
    return {
        "user_id": user_id,
        "message_type": request.message_type,
        "condition_type": request.condition_type,
        "title": request.title,
        "content": request.content,
        "status": "sealed",
        "deliver_at": deliver_at,
        "condition_json": condition,
        "unlock_secret_hash": unlock_secret_hash,
        "dedupe_key": f"request:{request.client_request_id}",
        "source_message_id": request.source_message_id,
        "source_turn_id": request.source_turn_id,
        "expires_at": expires_at,
        "version": 1,
        "metadata_json": sanitize_creation_metadata(request.metadata),
    }


def normalize_condition(condition_type: str, condition: dict[str, Any]) -> dict[str, Any]:
    """仅保留每种条件实际参与匹配的白名单字段。"""

    if condition_type == "time" or condition_type == "passphrase":
        return {}
    if condition_type == "keyword":
        match_mode = normalize_token(condition.get("matchMode") or "contains")
        if match_mode not in {"contains", "exact"}:
            raise ConditionalMessageServiceError("关键词 matchMode 只能是 contains 或 exact")
        return {
            "keyword": required_token(condition, "keyword", "关键词"),
            "matchMode": match_mode,
        }
    if condition_type == "project_status":
        return {
            "projectKey": required_token(condition, "projectKey", "项目标识"),
            "expectedStatus": required_token(condition, "expectedStatus", "目标状态"),
        }
    if condition_type == "github_event":
        normalized = {
            "repository": required_token(condition, "repository", "GitHub 仓库"),
            "event": required_token(condition, "event", "GitHub 事件"),
        }
        for key in ("action", "conclusion", "ref"):
            value = normalize_optional_token(condition.get(key))
            if value:
                normalized[key] = value
        return normalized
    raise ConditionalMessageServiceError("不支持的条件类型")


def queue_record(
    session,
    record: ConditionalMessage,
    now: datetime,
    trigger_source: str,
    event_metadata: dict[str, Any],
) -> ProactiveMessage | None:
    """把一条已锁定的 sealed 记录推进到 queued，并创建唯一 outbox。"""

    if record.status != "sealed" or expire_if_needed(record, now):
        return None
    outbox = ProactiveMessage(
        id=uuid4(),
        user_id=record.user_id,
        trigger_type=CAPSULE_TRIGGER_TYPE,
        title=record.title,
        content=opened_message_content(record),
        scheduled_at=now,
        status="pending",
        dedupe_key=f"conditional_message:{record.id}:{record.version}",
        metadata_json={
            "source": "conditional_message",
            "conditional_message_id": str(record.id),
            "message_type": record.message_type,
            "condition_type": record.condition_type,
            "trigger_source": trigger_source,
            "trigger_event": safe_metadata(event_metadata),
        },
    )
    session.add(outbox)
    record.status = "queued"
    record.triggered_at = now
    record.outbox_message_id = outbox.id
    record.version += 1
    return outbox


def opened_message_content(record: ConditionalMessage) -> str:
    """生成打开后的聊天文本，保留用户原文且只添加一行动作前缀。"""

    action = "（拆开那枚时间胶囊。）" if record.message_type == "time_capsule" else "（打开秘密保险箱。）"
    return f"{action}\n{record.content.strip()}"


async def ensure_event(
    session: AsyncSession,
    user_id: UUID,
    event_type: str,
    event_id: str,
    payload: dict[str, Any],
    now: datetime,
) -> tuple[ConditionalMessageEvent, bool]:
    """幂等写入事件账本；重复 ID 的负载不同则拒绝复用。"""

    clean_event_id = str(event_id or "").strip()
    if not clean_event_id:
        raise ConditionalMessageServiceError("eventId 不能为空")
    clean_event_id = clean_event_id[:128]
    normalized_payload = safe_metadata(payload)
    statement = (
        pg_insert(ConditionalMessageEvent)
        .values(
            id=uuid4(),
            user_id=user_id,
            event_type=event_type,
            event_id=clean_event_id,
            payload=normalized_payload,
            matched_count=0,
            occurred_at=now,
        )
        .on_conflict_do_nothing(
            constraint="uq_conditional_message_event_user_event"
        )
        .returning(ConditionalMessageEvent.id)
    )
    inserted_id = (await session.execute(statement)).scalar_one_or_none()
    if inserted_id is not None:
        event = await session.get(ConditionalMessageEvent, inserted_id)
        return event, True

    result = await session.execute(
        select(ConditionalMessageEvent).where(
            ConditionalMessageEvent.user_id == user_id,
            ConditionalMessageEvent.event_type == event_type,
            ConditionalMessageEvent.event_id == clean_event_id,
        )
    )
    event = result.scalar_one()
    if canonical_json(event.payload_json) != canonical_json(normalized_payload):
        raise ConditionalMessageServiceError("eventId 已被另一份事件内容使用", 409)
    return event, False


async def expire_due_records(session: AsyncSession, now: datetime) -> int:
    """把仍密封但已经超过有效期的记录推进到 expired。"""

    result = await session.execute(
        select(ConditionalMessage)
        .where(
            ConditionalMessage.status == "sealed",
            ConditionalMessage.expires_at.is_not(None),
            ConditionalMessage.expires_at <= now,
        )
        .with_for_update(skip_locked=True)
        .limit(MAX_CONDITION_SCAN)
    )
    changed = 0
    for record in result.scalars().all():
        if expire_if_needed(record, now):
            changed += 1
    return changed


def expire_if_needed(record: ConditionalMessage, now: datetime) -> bool:
    """在已经锁定的 ORM 记录上应用到期终态。"""

    expires_at = normalize_optional_datetime(record.expires_at)
    if record.status == "sealed" and expires_at is not None and expires_at <= now:
        record.status = "expired"
        record.version += 1
        return True
    return record.status == "expired"


def keyword_matches(condition: dict[str, Any], message: str) -> bool:
    """按 contains/exact 规则匹配真实用户消息，大小写使用 casefold 统一。"""

    keyword = normalize_token(condition.get("keyword"))
    text = normalize_token(message)
    if not keyword or not text:
        return False
    if re.search(rf"(?:不|没|没有|并不)\s*{re.escape(keyword)}", text):
        return False
    if condition.get("matchMode") == "exact":
        return text == keyword
    return keyword in text


def is_same_creation_message(
    record: ConditionalMessage,
    event_type: str,
    event_id: str,
) -> bool:
    """阻止“创建关键词保险箱”的那句话同时成为首次触发消息。"""

    if event_type != "keyword" or not record.source_message_id:
        return False
    normalized_event_id = str(event_id or "")
    source_event_id = normalized_event_id[5:] if normalized_event_id.startswith("chat:") else normalized_event_id
    return source_event_id == record.source_message_id


def project_status_matches(condition: dict[str, Any], payload: dict[str, Any]) -> bool:
    """要求项目标识和目标状态同时相等。"""

    return (
        normalize_token(condition.get("projectKey")) == normalize_token(payload.get("projectKey"))
        and normalize_token(condition.get("expectedStatus")) == normalize_token(payload.get("status"))
    )


def github_event_matches(condition: dict[str, Any], payload: dict[str, Any]) -> bool:
    """匹配仓库和事件，并对条件中出现的可选字段执行严格相等。"""

    required_pairs = (("repository", "repository"), ("event", "event"))
    if any(normalize_token(condition.get(a)) != normalize_token(payload.get(b)) for a, b in required_pairs):
        return False
    for key in ("action", "conclusion", "ref"):
        expected = normalize_optional_token(condition.get(key))
        if expected is not None and expected != normalize_optional_token(payload.get(key)):
            return False
    return True


def conditional_message_dict(record: ConditionalMessage) -> dict[str, Any]:
    """生成公开快照；sealed/queued/expired 状态不会泄露密封正文。"""

    reveal_content = record.status in {"delivered", "cancelled"}
    return {
        "id": str(record.id),
        "messageType": record.message_type,
        "conditionType": record.condition_type,
        "title": record.title,
        "content": record.content if reveal_content else None,
        "contentSealed": not reveal_content,
        "status": record.status,
        "deliverAt": iso_datetime(record.deliver_at),
        "condition": dict(record.condition_json or {}),
        "triggeredAt": iso_datetime(record.triggered_at),
        "deliveredAt": iso_datetime(record.delivered_at),
        "cancelledAt": iso_datetime(record.cancelled_at),
        "expiresAt": iso_datetime(record.expires_at),
        "version": record.version,
        "createdAt": iso_datetime(record.created_at),
        "updatedAt": iso_datetime(record.updated_at),
        "metadata": dict(record.metadata_json or {}) if reveal_content else {},
    }


async def require_record(
    session: AsyncSession,
    user_id: str,
    message_id: str,
) -> ConditionalMessage:
    """读取当前用户记录，不泄露其他用户是否存在相同 ID。"""

    parsed_user_id = parse_uuid(user_id, "用户 ID")
    parsed_message_id = parse_uuid(message_id, "条件消息 ID")
    result = await session.execute(
        select(ConditionalMessage).where(
            ConditionalMessage.id == parsed_message_id,
            ConditionalMessage.user_id == parsed_user_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise ConditionalMessageServiceError("条件消息不存在", 404)
    return record


async def find_by_dedupe(
    session: AsyncSession,
    user_id: UUID,
    dedupe_key: str,
) -> ConditionalMessage | None:
    """按用户和幂等键查询创建结果。"""

    result = await session.execute(
        select(ConditionalMessage).where(
            ConditionalMessage.user_id == user_id,
            ConditionalMessage.dedupe_key == dedupe_key,
        )
    )
    return result.scalar_one_or_none()


def ensure_same_create(record: ConditionalMessage, values: dict[str, Any]) -> None:
    """防止客户端复用幂等键却悄悄改变正文或触发条件。"""

    comparable = {
        "message_type": record.message_type,
        "condition_type": record.condition_type,
        "title": record.title,
        "content": record.content,
        "deliver_at": iso_datetime(record.deliver_at),
        "condition": dict(record.condition_json or {}),
        "expires_at": iso_datetime(record.expires_at),
    }
    requested = {
        "message_type": values["message_type"],
        "condition_type": values["condition_type"],
        "title": values["title"],
        "content": values["content"],
        "deliver_at": iso_datetime(values["deliver_at"]),
        "condition": values["condition_json"],
        "expires_at": iso_datetime(values["expires_at"]),
    }
    if canonical_json(comparable) != canonical_json(requested):
        raise ConditionalMessageServiceError("clientRequestId 已被另一条条件消息使用", 409)


def verify_secret(plain: str, digest: str | None) -> bool:
    """安全校验口令摘要；损坏或缺失摘要一律视为不匹配。"""

    if not plain or not digest:
        return False
    try:
        return _password_hash.verify(plain, digest)
    except Exception:
        return False


def required_token(condition: dict[str, Any], key: str, label: str) -> str:
    """读取条件白名单字段，并在为空时抛出中文领域错误。"""

    value = normalize_token(condition.get(key))
    if not value:
        raise ConditionalMessageServiceError(f"{label}不能为空")
    return value[:240]


def normalize_token(value: Any) -> str:
    """把外部条件值规范成去空白、大小写无关的比较文本。"""

    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.split()).casefold()


def normalize_optional_token(value: Any) -> str | None:
    """规范可选比较字段，空值返回 ``None``。"""

    normalized = normalize_token(value)
    return normalized or None


def normalize_utc(value: datetime) -> datetime:
    """把有/无时区时间统一为 UTC。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_optional_datetime(value: datetime | None) -> datetime | None:
    """规范可选日期时间。"""

    return normalize_utc(value) if value is not None else None


def parse_uuid(value: str, label: str) -> UUID:
    """解析外部 UUID，并把格式错误转换成稳定中文响应。"""

    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ConditionalMessageServiceError(f"{label}格式无效") from exc


def safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    """限制审计元数据体积并确保其中只有 JSON 可序列化值。"""

    if not isinstance(value, dict):
        return {}
    encoded = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(encoded) > 8000:
        raise ConditionalMessageServiceError("metadata 过大，不能超过 8000 个字符")
    return json.loads(encoded)


def sanitize_creation_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
    """剥离客户端不能用来伪造授权或复制密封正文的保留 metadata。"""

    cleaned = safe_metadata(value)
    reserved = {
        "authorization",
        "authorized",
        "authorized_by_user",
        "proactive_allowed",
        "user_id",
        "userid",
        "content",
        "sealed_content",
        "passphrase",
        "password",
        "secret",
        "unlock_secret_hash",
    }
    return {
        key: item
        for key, item in cleaned.items()
        if str(key).strip().casefold() not in reserved
    }


def canonical_json(value: Any) -> str:
    """生成字段顺序稳定的 JSON，用于幂等负载比较。"""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def text_digest(value: Any) -> str:
    """为事件幂等比较生成摘要，避免在事件 inbox 重复保存整条聊天正文。"""

    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def iso_datetime(value: datetime | None) -> str | None:
    """把数据库时间转换成 UTC ISO 字符串。"""

    return normalize_utc(value).isoformat() if value is not None else None
