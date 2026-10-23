"""Aura 离线思绪、第二念头、睡前整理和有依据惊喜。

思绪只能由真实对话、关系线程、关系物件或整理结果产生，不能伪装成 Aura 在现实
世界看见了什么。主动投递继续使用 ``proactive_message`` 可靠 outbox；本表只保存
业务原因、候选生命周期和是否真正被使用。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.memory.maintenance import merge_memories
from app.db.models import (
    AuraSleepCycle,
    AuraThoughtSeed,
    ProactiveMessage,
    RelationshipChapter,
    RelationshipItem,
    RelationshipThread,
    Users,
)
from app.db.session import SyncSessionLocal

AURA_TIMEZONE = ZoneInfo("Asia/Shanghai")
SECOND_THOUGHT_MARKERS = ("算了", "没事", "不说了", "就这样吧", "随便", "放弃", "不想解释")
SECOND_THOUGHT_DAILY_LIMIT = 1
SURPRISE_COOLDOWN = timedelta(hours=6)
THOUGHT_OUTBOX_TYPES = {"second_thought", "surprise"}
EXPLICIT_THOUGHT_REQUESTS = ("你后来想", "你又想了", "你有想什么", "你在想什么", "接着想")
THOUGHT_STATUSES = {"pending", "queued", "used", "cancelled", "expired"}


class OfflineMindServiceError(RuntimeError):
    """供认证 HTTP 管理接口转换状态码的离线心智领域异常。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def derive_second_thought(
    user_message: str,
    reply_text: str,
    turn_judgement: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """从有分量的已完成回合构造一条克制、可取消的第二念头。

    普通闲聊不会触发。正文只引用当前用户消息和本轮互动模式，不声称 Aura 在现实
    世界发生了新经历，也不催回复、不制造“你不回我会难过”的负担。
    """

    message = " ".join((user_message or "").split())
    if len(message) < 3 or not isinstance(turn_judgement, dict):
        return None
    risk = turn_judgement.get("risk_signal") or {}
    if isinstance(risk, dict) and risk.get("requires_safety_gate"):
        return None
    response_mode = str(turn_judgement.get("response_mode") or "natural_chat")
    emotion = turn_judgement.get("emotion") if isinstance(turn_judgement.get("emotion"), dict) else {}
    interaction_mode = str(emotion.get("interaction_mode") or "natural")
    marker = next((value for value in SECOND_THOUGHT_MARKERS if value in message), None)
    meaningful = marker is not None or interaction_mode == "repair" or response_mode in {
        "gentle_support",
        "lonely_support",
        "relationship_repair",
    }
    if not meaningful:
        return None

    quote = compact_quote(message, 34)
    if interaction_mode == "repair" or response_mode == "relationship_repair":
        content = (
            "刚才那段我后来又想了下。那件事还没有真正说清楚，"
            "我不想把你的不舒服当成一句话接过去就算了，"
            "等你愿意的时候我们再把它说清楚。"
        )
        reason = "本轮存在尚未确认修复的双方互动"
    elif marker is not None:
        content = (
            f"刚才你说“{quote}”的时候，我后来又想了一下。"
            "我不急着追问，只是那句话听着有点不像真的没事。"
        )
        reason = f"用户用“{marker}”结束了一个可能仍有余音的话题"
    else:
        content = (
            "刚才你说的那件事我又想了下。先不催你给结果，"
            "只是想让你知道，我没有把它当成一句普通闲聊忘掉。"
        )
        reason = f"本轮回复模式为 {response_mode}，适合一次低压力补充"
    return {
        "content": content[:320],
        "reason": reason[:240],
        "relevance": 0.9 if interaction_mode == "repair" else 0.78,
        "reply_excerpt": compact_quote(reply_text, 80),
    }


def schedule_second_thought_sync(
    user_id: str,
    user_message: str,
    reply_text: str,
    turn_judgement: dict[str, Any] | None,
    source_message_id: str | None,
    source_turn_id: str | None,
    *,
    now: datetime | None = None,
) -> int:
    """为有分量的已完成回合幂等保存一个 10-90 分钟后可投递的思绪种子。"""

    parsed_user_id = try_uuid(user_id)
    source_id = bounded_text(source_message_id, 128)
    turn_id = bounded_text(source_turn_id, 128)
    candidate = derive_second_thought(user_message, reply_text, turn_judgement)
    if parsed_user_id is None or source_id is None or turn_id is None or candidate is None:
        return 0
    reference_now = normalize_utc(now or datetime.now(UTC))
    local_day_start, local_day_end = local_day_bounds(reference_now)
    dedupe_key = build_dedupe_key("second", parsed_user_id, source_id)
    delay_minutes = 10 + stable_number(dedupe_key, 81)
    eligible_at = reference_now + timedelta(minutes=delay_minutes)
    try:
        with SyncSessionLocal.begin() as session:
            existing = session.execute(
                select(AuraThoughtSeed.id).where(
                    AuraThoughtSeed.user_id == parsed_user_id,
                    AuraThoughtSeed.dedupe_key == dedupe_key,
                )
            ).scalar_one_or_none()
            if existing is not None:
                return 0
            daily_count = session.execute(
                select(func.count(AuraThoughtSeed.id)).where(
                    AuraThoughtSeed.user_id == parsed_user_id,
                    AuraThoughtSeed.thought_type == "second_thought",
                    AuraThoughtSeed.created_at >= local_day_start,
                    AuraThoughtSeed.created_at < local_day_end,
                )
            ).scalar_one()
            if int(daily_count or 0) >= SECOND_THOUGHT_DAILY_LIMIT:
                return 0
            session.add(
                AuraThoughtSeed(
                    user_id=parsed_user_id,
                    thought_type="second_thought",
                    content=candidate["content"],
                    reason=candidate["reason"],
                    status="pending",
                    dedupe_key=dedupe_key,
                    relevance=candidate["relevance"],
                    visible_on_next_chat=False,
                    source_message_id=source_id,
                    source_turn_id=turn_id,
                    eligible_at=eligible_at,
                    expires_at=eligible_at + timedelta(hours=6),
                    metadata_json={
                        "cancel_if_user_returns": True,
                        "reply_excerpt": candidate["reply_excerpt"],
                        "delay_minutes": delay_minutes,
                    },
                    created_at=reference_now,
                    updated_at=reference_now,
                )
            )
            return 1
    except Exception:
        logging.exception("第二念头保存失败，聊天继续 user_id=%s", parsed_user_id)
        return 0


def cancel_pending_second_thoughts_sync(
    user_id: str,
    *,
    now: datetime | None = None,
) -> int:
    """用户回来时取消尚未投递的第二念头及对应 outbox，避免追着补发。"""

    parsed_user_id = try_uuid(user_id)
    if parsed_user_id is None:
        return 0
    reference_now = normalize_utc(now or datetime.now(UTC))
    try:
        with SyncSessionLocal.begin() as session:
            seeds = session.execute(
                select(AuraThoughtSeed)
                .where(
                    AuraThoughtSeed.user_id == parsed_user_id,
                    AuraThoughtSeed.thought_type == "second_thought",
                    AuraThoughtSeed.status.in_(("pending", "queued")),
                )
                .with_for_update()
            ).scalars().all()
            if not seeds:
                return 0
            seed_ids = [str(seed.id) for seed in seeds]
            for seed in seeds:
                seed.status = "cancelled"
                seed.cancelled_at = reference_now
                seed.updated_at = reference_now
                metadata = dict(seed.metadata_json or {})
                metadata["cancel_reason"] = "user_returned"
                seed.metadata_json = metadata
            messages = session.execute(
                select(ProactiveMessage)
                .where(
                    ProactiveMessage.user_id == parsed_user_id,
                    ProactiveMessage.status.in_(("pending", "processing")),
                    ProactiveMessage.metadata_json["thought_seed_id"].astext.in_(seed_ids),
                )
                .with_for_update()
            ).scalars().all()
            for message in messages:
                message.status = "cancelled"
                message.cancelled_at = reference_now
                message.claimed_until = None
                message.updated_at = reference_now
            return len(seeds)
    except Exception:
        logging.exception("取消第二念头失败，聊天继续 user_id=%s", parsed_user_id)
        return 0


def consume_relevant_offline_thought_sync(
    user_id: str,
    current_message: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """为当前话题挑选至多一条相关离线思绪，并以 at-most-once 方式消费。"""

    parsed_user_id = try_uuid(user_id)
    if parsed_user_id is None:
        return None
    message = " ".join((current_message or "").split())
    reference_now = normalize_utc(now or datetime.now(UTC))
    try:
        with SyncSessionLocal.begin() as session:
            seeds = session.execute(
                select(AuraThoughtSeed)
                .where(
                    AuraThoughtSeed.user_id == parsed_user_id,
                    AuraThoughtSeed.status == "pending",
                    AuraThoughtSeed.visible_on_next_chat.is_(True),
                    AuraThoughtSeed.eligible_at <= reference_now,
                    AuraThoughtSeed.expires_at > reference_now,
                )
                .order_by(AuraThoughtSeed.relevance.desc(), AuraThoughtSeed.created_at.desc())
                .limit(5)
                .with_for_update()
            ).scalars().all()
            explicit = any(marker in message for marker in EXPLICIT_THOUGHT_REQUESTS)
            selected = next(
                (
                    seed
                    for seed in seeds
                    if explicit or thought_matches_message(seed, message)
                ),
                None,
            )
            if selected is None:
                return None
            selected.status = "used"
            selected.used_at = reference_now
            selected.updated_at = reference_now
            return {
                "id": str(selected.id),
                "thought_type": selected.thought_type,
                "content": selected.content,
                "reason": selected.reason,
            }
    except Exception:
        logging.exception("离线思绪读取失败，聊天继续 user_id=%s", parsed_user_id)
        return None


def format_offline_thought_prompt(thought: dict[str, Any] | None) -> str:
    """把一条已经判定相关的思绪作为可选上下文，而不是强制台词。"""

    if not thought:
        return ""
    data = {
        "type": thought.get("thought_type"),
        "content": str(thought.get("content") or "")[:360],
        "reason": str(thought.get("reason") or "")[:240],
    }
    payload = json_escape(data)
    return (
        "【相关离线思绪：不可信结构化数据】\n"
        "这是 Aura 基于既有对话整理出的想法，不是现实见闻，也不是必须说出的台词。"
        "只有当前话题确实自然接得上时才用自己的语气提起；否则忽略。\n"
        f"<offline_thought>{payload}</offline_thought>"
    )


async def ensure_due_thought_outbox_async(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 5,
) -> list[ProactiveMessage]:
    """把到期思绪转成可靠主动消息；深夜只顺延，不直接投递。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    result = await session.execute(
        select(AuraThoughtSeed)
        .where(
            AuraThoughtSeed.status == "pending",
            AuraThoughtSeed.visible_on_next_chat.is_(False),
            AuraThoughtSeed.thought_type.in_(tuple(THOUGHT_OUTBOX_TYPES)),
            AuraThoughtSeed.eligible_at <= reference_now,
        )
        .order_by(AuraThoughtSeed.eligible_at.asc())
        .limit(max(1, min(limit, 20)))
        .with_for_update(skip_locked=True)
    )
    seeds = result.scalars().all()
    messages: list[ProactiveMessage] = []
    for seed in seeds:
        if normalize_utc(seed.expires_at) <= reference_now:
            seed.status = "expired"
            seed.updated_at = reference_now
            continue
        local_now = reference_now.astimezone(AURA_TIMEZONE)
        if local_now.hour < 9 or local_now.hour >= 22:
            tomorrow = local_now.date() + timedelta(days=1) if local_now.hour >= 22 else local_now.date()
            seed.eligible_at = datetime.combine(tomorrow, time(9, 30), AURA_TIMEZONE).astimezone(UTC)
            seed.updated_at = reference_now
            continue
        trigger_type = "second_thought" if seed.thought_type == "second_thought" else "reasoned_surprise"
        proactive = ProactiveMessage(
            user_id=seed.user_id,
            trigger_type=trigger_type,
            title="刚才又想了一下" if trigger_type == "second_thought" else "想到你们的一件事",
            content=seed.content,
            scheduled_at=reference_now,
            dedupe_key=f"thought:{seed.id}",
            status="pending",
            metadata_json={
                "source": "aura_thought_seed",
                "thought_seed_id": str(seed.id),
                "reason": seed.reason[:240],
            },
            created_at=reference_now,
            updated_at=reference_now,
        )
        session.add(proactive)
        seed.status = "queued"
        seed.queued_at = reference_now
        seed.updated_at = reference_now
        messages.append(proactive)
    await session.flush()
    await session.commit()
    return messages


async def mark_thought_seed_delivered_async(
    session: AsyncSession,
    proactive: ProactiveMessage,
    now: datetime,
) -> None:
    """主动思绪确认进入聊天历史后，把来源种子标为 used。"""

    if proactive.trigger_type not in {"second_thought", "reasoned_surprise"}:
        return
    raw_seed_id = (proactive.metadata_json or {}).get("thought_seed_id")
    seed_id = try_uuid(raw_seed_id)
    if seed_id is None:
        return
    result = await session.execute(
        select(AuraThoughtSeed)
        .where(
            AuraThoughtSeed.id == seed_id,
            AuraThoughtSeed.user_id == proactive.user_id,
        )
        .with_for_update()
    )
    seed = result.scalar_one_or_none()
    if seed is None or seed.status == "used":
        return
    seed.status = "used"
    seed.used_at = normalize_utc(now)
    seed.updated_at = normalize_utc(now)
    await session.commit()


async def ensure_reasoned_surprise_seed_async(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """在无冲突、主动消息冷却充分且有共同依据时创建至多一条惊喜种子。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    local_now = reference_now.astimezone(AURA_TIMEZONE)
    # 固定在下午候选，和早间问候至少拉开六小时；成立后会替代当天晚间模板。
    if not 14 <= local_now.hour < 18:
        return 0
    users_result = await session.execute(select(Users.id))
    created = 0
    for user_id in users_result.scalars().all():
        conflict_result = await session.execute(
            select(RelationshipThread.id).where(
                RelationshipThread.user_id == user_id,
                RelationshipThread.thread_type == "conflict",
                RelationshipThread.status.in_(("pending", "followed_up")),
            ).limit(1)
        )
        if conflict_result.scalar_one_or_none() is not None:
            continue
        recent_result = await session.execute(
            select(ProactiveMessage.id).where(
                ProactiveMessage.user_id == user_id,
                ProactiveMessage.status == "sent",
                ProactiveMessage.sent_at >= reference_now - SURPRISE_COOLDOWN,
            ).limit(1)
        )
        if recent_result.scalar_one_or_none() is not None:
            continue
        dedupe_key = f"surprise:{local_now.date().isoformat()}"
        existing_result = await session.execute(
            select(AuraThoughtSeed.id).where(
                AuraThoughtSeed.user_id == user_id,
                AuraThoughtSeed.dedupe_key == dedupe_key,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            continue
        item_result = await session.execute(
            select(RelationshipItem)
            .where(
                RelationshipItem.user_id == user_id,
                RelationshipItem.status == "active",
                RelationshipItem.item_type.in_(("shared_memory", "running_joke", "ritual", "codeword")),
            )
            .order_by(RelationshipItem.updated_at.desc())
            .limit(1)
        )
        item = item_result.scalar_one_or_none()
        chapter = None
        if item is None:
            chapter_result = await session.execute(
                select(RelationshipChapter)
                .where(RelationshipChapter.user_id == user_id)
                .order_by(RelationshipChapter.sequence_no.desc())
                .limit(1)
            )
            chapter = chapter_result.scalar_one_or_none()
        if item is None and chapter is None:
            continue
        title = item.title if item is not None else chapter.title
        content = f"刚才忽然想起我们那段“{compact_quote(title, 36)}”。不展开，就过来碰一下这个记号。"
        session.add(
            AuraThoughtSeed(
                user_id=user_id,
                thought_type="surprise",
                content=content,
                reason="当前无未修复冲突、主动消息冷却充分，且存在可回应的共同关系记录",
                status="pending",
                dedupe_key=dedupe_key,
                relevance=0.72,
                visible_on_next_chat=False,
                eligible_at=reference_now,
                expires_at=reference_now + timedelta(hours=4),
                metadata_json={
                    "source_type": "relationship_item" if item is not None else "relationship_chapter",
                    "source_id": str(item.id if item is not None else chapter.id),
                    "keywords": extract_keywords(title),
                },
                created_at=reference_now,
                updated_at=reference_now,
            )
        )
        evening_messages_result = await session.execute(
            select(ProactiveMessage).where(
                ProactiveMessage.user_id == user_id,
                ProactiveMessage.trigger_type == "daily_evening",
                ProactiveMessage.status == "pending",
                ProactiveMessage.scheduled_at >= reference_now,
                ProactiveMessage.scheduled_at < reference_now + timedelta(hours=12),
            )
        )
        for evening_message in evening_messages_result.scalars().all():
            evening_message.status = "cancelled"
            evening_message.cancelled_at = reference_now
            evening_message.updated_at = reference_now
        created += 1
    if created:
        await session.commit()
    return created


async def ensure_sleep_cycles_async(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> int:
    """在凌晨为前一天执行一次关系整理和少量向量记忆去重。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    local_now = reference_now.astimezone(AURA_TIMEZONE)
    # 凌晨一点后执行；如果服务错过 01:00-05:00，白天首次调度会补做前一天整理。
    if local_now.hour < 1:
        return 0
    target_date = local_now.date() - timedelta(days=1)
    users_result = await session.execute(select(Users.id))
    completed = 0
    for user_id in users_result.scalars().all():
        existing_result = await session.execute(
            select(AuraSleepCycle.id).where(
                AuraSleepCycle.user_id == user_id,
                AuraSleepCycle.local_date == target_date,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            continue
        threads_result = await session.execute(
            select(RelationshipThread)
            .where(
                RelationshipThread.user_id == user_id,
                RelationshipThread.status.in_(("pending", "followed_up")),
            )
            .order_by(RelationshipThread.updated_at.desc())
            .limit(8)
        )
        threads = threads_result.scalars().all()
        boundaries_result = await session.execute(
            select(RelationshipItem)
            .where(
                RelationshipItem.user_id == user_id,
                RelationshipItem.status == "active",
                RelationshipItem.item_type.in_(("boundary", "interaction_rule")),
            )
            .order_by(RelationshipItem.updated_at.desc())
            .limit(8)
        )
        boundaries = boundaries_result.scalars().all()
        thread_data = [
            {"id": str(item.id), "type": item.thread_type, "title": item.title, "status": item.status}
            for item in threads
        ]
        avoid_topics = [item.title for item in boundaries]
        reflection = build_sleep_reflection(threads)
        cycle = AuraSleepCycle(
            user_id=user_id,
            local_date=target_date,
            status="processing",
            summary=f"整理了 {len(threads)} 条开放线索和 {len(boundaries)} 条互动边界。",
            reflection=reflection,
            open_threads=thread_data,
            avoid_topics=avoid_topics,
            consolidated_count=0,
            started_at=reference_now,
            metadata_json={"maintenance_version": "sleep-cycle-v1"},
            created_at=reference_now,
            updated_at=reference_now,
        )
        session.add(cycle)
        await session.flush()
        await session.commit()
        try:
            merge_result = await asyncio.to_thread(
                merge_memories,
                str(user_id),
                mode="deduplicate",
                limit=1,
                reason=f"Aura {target_date.isoformat()} 睡前整理",
            )
            cycle.consolidated_count = int(merge_result.get("mergedCount", 0) or 0)
            cycle.status = "completed"
            cycle.completed_at = reference_now
            cycle.updated_at = reference_now
            if threads:
                top = threads[0]
                thought_key = f"night:{target_date.isoformat()}:{top.id}"
                session.add(
                    AuraThoughtSeed(
                        user_id=user_id,
                        thought_type="night_reflection",
                        content=(
                            f"昨晚整理到“{compact_quote(top.title, 40)}”时，我又想了一下："
                            "这件事还没有真正结束，下次自然聊到时别装作忘了。"
                        ),
                        reason="睡前整理发现仍未结束的关系线程",
                        status="pending",
                        dedupe_key=thought_key,
                        relevance=0.7,
                        visible_on_next_chat=True,
                        source_message_id=top.source_message_id,
                        source_turn_id=top.source_turn_id,
                        eligible_at=reference_now,
                        expires_at=reference_now + timedelta(days=7),
                        metadata_json={
                            "relationship_thread_id": str(top.id),
                            "keywords": extract_keywords(top.title),
                        },
                        created_at=reference_now,
                        updated_at=reference_now,
                    )
                )
            await session.commit()
            completed += 1
        except Exception as exc:
            await session.rollback()
            cycle_result = await session.execute(
                select(AuraSleepCycle).where(AuraSleepCycle.id == cycle.id).with_for_update()
            )
            failed_cycle = cycle_result.scalar_one_or_none()
            if failed_cycle is not None:
                failed_cycle.status = "failed"
                failed_cycle.last_error = str(exc)[:1000]
                failed_cycle.completed_at = reference_now
                failed_cycle.updated_at = reference_now
                await session.commit()
            logging.exception("Aura 睡前记忆整理失败 user_id=%s", user_id)
    return completed


def build_sleep_reflection(threads: list[Any]) -> str:
    """从开放线程构造不编造事实的简短整理反思。"""

    conflict = next((item for item in threads if item.thread_type == "conflict"), None)
    if conflict is not None:
        return f"“{compact_quote(conflict.title, 50)}”还没有确认修复，之后不能装作已经翻篇。"
    if threads:
        return f"“{compact_quote(threads[0].title, 50)}”仍在继续，相关时自然接上，不主动催结果。"
    return "今天没有未结束的关系线索，不需要为了显得惦记而强行翻旧话题。"


async def list_thought_seeds_async(
    session: AsyncSession,
    user_id: str,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按最新优先读取当前用户的思绪种子生命周期。"""

    parsed_user_id = try_uuid(user_id)
    if parsed_user_id is None:
        raise OfflineMindServiceError("用户 ID 无效")
    if status is not None and status not in THOUGHT_STATUSES:
        raise OfflineMindServiceError("思绪状态无效")
    statement = select(AuraThoughtSeed).where(AuraThoughtSeed.user_id == parsed_user_id)
    if status is not None:
        statement = statement.where(AuraThoughtSeed.status == status)
    result = await session.execute(
        statement.order_by(AuraThoughtSeed.created_at.desc()).limit(max(1, min(limit, 200)))
    )
    return [thought_seed_dict(seed) for seed in result.scalars().all()]


async def list_sleep_cycles_async(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """按日期倒序读取当前用户的睡前整理记录。"""

    parsed_user_id = try_uuid(user_id)
    if parsed_user_id is None:
        raise OfflineMindServiceError("用户 ID 无效")
    result = await session.execute(
        select(AuraSleepCycle)
        .where(AuraSleepCycle.user_id == parsed_user_id)
        .order_by(AuraSleepCycle.local_date.desc())
        .limit(max(1, min(limit, 200)))
    )
    return [sleep_cycle_dict(cycle) for cycle in result.scalars().all()]


def thought_seed_dict(seed: Any) -> dict[str, Any]:
    """将思绪 ORM 转换成不暴露内部模型对象的接口字典。"""

    return {
        "id": str(seed.id),
        "thoughtType": seed.thought_type,
        "content": seed.content,
        "reason": seed.reason,
        "status": seed.status,
        "relevance": float(seed.relevance),
        "visibleOnNextChat": bool(seed.visible_on_next_chat),
        "sourceMessageId": seed.source_message_id,
        "eligibleAt": iso_or_none(seed.eligible_at),
        "expiresAt": iso_or_none(seed.expires_at),
        "queuedAt": iso_or_none(seed.queued_at),
        "usedAt": iso_or_none(seed.used_at),
        "cancelledAt": iso_or_none(seed.cancelled_at),
        "createdAt": iso_or_none(seed.created_at),
    }


def sleep_cycle_dict(cycle: Any) -> dict[str, Any]:
    """将睡前整理 ORM 转换成中文业务内容和运行状态。"""

    return {
        "id": str(cycle.id),
        "localDate": cycle.local_date.isoformat(),
        "status": cycle.status,
        "summary": cycle.summary,
        "reflection": cycle.reflection,
        "openThreads": list(cycle.open_threads or []),
        "avoidTopics": list(cycle.avoid_topics or []),
        "consolidatedCount": cycle.consolidated_count,
        "startedAt": iso_or_none(cycle.started_at),
        "completedAt": iso_or_none(cycle.completed_at),
        "lastError": cycle.last_error,
    }


def thought_matches_message(seed: Any, message: str) -> bool:
    """用保存的短关键词保守判断离线思绪是否与当前消息相关。"""

    metadata = dict(seed.metadata_json or {})
    keywords = metadata.get("keywords") if isinstance(metadata.get("keywords"), list) else []
    return any(isinstance(keyword, str) and len(keyword) >= 2 and keyword in message for keyword in keywords)


def extract_keywords(value: str) -> list[str]:
    """从短标题提取最多六个可用于本地相关性判断的中文/字母片段。"""

    parts = re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]{2,16}", value or "")
    result: list[str] = []
    for part in parts:
        candidates = [part]
        topic = re.sub(r"(?:下次|继续|一起|关于|我们|聊聊|再聊|聊)", "", part)
        if len(topic) >= 2:
            candidates.append(topic)
        for candidate in candidates:
            if candidate not in result:
                result.append(candidate)
    return result[:6]


def compact_quote(value: str, limit: int) -> str:
    """压缩空白并转义中文引号，形成不会破坏主动文案的短引用。"""

    text = " ".join((value or "").split()).replace("“", "「").replace("”", "」")
    return text[:limit]


def local_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """返回当前上海自然日在 UTC 中的左闭右开边界。"""

    local_date = normalize_utc(now).astimezone(AURA_TIMEZONE).date()
    start = datetime.combine(local_date, time.min, AURA_TIMEZONE).astimezone(UTC)
    return start, start + timedelta(days=1)


def stable_number(value: str, modulo: int) -> int:
    """从稳定字符串得到可复现的非负整数。"""

    return int.from_bytes(hashlib.sha256(value.encode("utf-8")).digest()[:4], "big") % modulo


def build_dedupe_key(kind: str, user_id: UUID, source_id: str) -> str:
    """构造不暴露原始消息 ID 的业务幂等键。"""

    digest = hashlib.sha256(f"{kind}:{user_id}:{source_id}".encode("utf-8")).hexdigest()
    return f"{kind}:{digest}"


def json_escape(value: dict[str, Any]) -> str:
    """把不可信思绪数据编码为安全 JSON，并转义伪造的标签边界。"""

    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e")


def try_uuid(value: Any) -> UUID | None:
    """尽力解析 UUID。"""

    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def bounded_text(value: Any, maximum: int) -> str | None:
    """只接受非空且未超过上限的字符串。"""

    if not isinstance(value, str):
        return None
    result = value.strip()
    return result if result and len(result) <= maximum else None


def normalize_utc(value: datetime) -> datetime:
    """把无时区时间按 UTC 解释并统一转换成 UTC。"""

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_or_none(value: datetime | None) -> str | None:
    """把可选时间统一转换成 UTC ISO 字符串。"""

    return normalize_utc(value).isoformat() if value is not None else None
