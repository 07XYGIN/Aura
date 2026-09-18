"""玲凌自身状态与关系动态的持久化和保守状态迁移。"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuraInternalState, RelationshipDynamics, Users
from app.db.session import SyncSessionLocal

AURA_STATE_VERSION = "aura-internal-state-v1"
RELATIONSHIP_DYNAMICS_VERSION = "relationship-dynamics-v1"
STAGE_PROMOTION_EVIDENCE = 3
STAGE_ORDER = ("early_closeness", "ambiguous", "early_romance", "established_romance")

AFFECTION_PATTERNS = (
    r"(?:我爱你|喜欢你|想你了|想抱抱你|亲亲|陪我一会儿)",
    r"(?:晚安|早安).{0,8}(?:宝贝|宝宝|玲凌)",
)
JEALOUSY_PATTERNS = (
    r"(?:和|跟).{0,10}(?:女生|女孩|男生|男孩|前任).{0,10}(?:聊天|吃饭|约会|出去|见面)",
    r"(?:女生|女孩|男生|男孩|前任).{0,10}(?:约我|找我|喜欢我)",
)
LEAVING_PATTERNS = (r"(?:我要|我先|准备)(?:睡了|睡觉|去忙|忙了|走了)", r"(?:晚安|先走了|回头聊)")
RETURN_PATTERNS = (r"(?:我回来了|回来了|我下班了|下班了|在吗)",)


def default_aura_internal_state(*, now: datetime | None = None) -> dict[str, Any]:
    """返回字段稳定且不带关系积分的默认自身状态。"""

    return {
        "mood": "calm",
        "attachment_tone": "steady",
        "missing_user": "none",
        "desire_for_contact": "low",
        "playfulness": "low",
        "jealousy": "none",
        "vulnerability": "low",
        "unresolved_feeling": None,
        "current_desire": "none",
        "last_meaningful_interaction": None,
        "last_user_seen_at": None,
        "last_proactive_at": None,
        "updated_at": normalize_utc(now or datetime.now(UTC)).isoformat(),
        "version": 1,
    }


def default_relationship_dynamics(*, now: datetime | None = None) -> dict[str, Any]:
    """返回关系动态默认值；默认处于暧昧而非凭空确认稳定恋爱。"""

    return {
        "relationship_stage": "ambiguous",
        "current_tone": "warm",
        "recent_closeness": "medium",
        "unresolved_tension": None,
        "recent_positive_moment": None,
        "recent_distance": None,
        "current_expectation": None,
        "stage_evidence_count": 0,
        "last_stage_change_at": None,
        "updated_at": normalize_utc(now or datetime.now(UTC)).isoformat(),
        "version": 1,
    }


def observe_relationship_state_sync(
    user_id: str,
    message: str,
    turn_judgement: dict[str, Any] | None,
    relationship_context: dict[str, Any] | None,
    *,
    source_message_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """读取并更新两类持久状态；数据库不可用时安全降级为内存投影。"""

    reference_now = normalize_utc(now or datetime.now(UTC))
    try:
        parsed_user_id = UUID(str(user_id))
    except (TypeError, ValueError):
        return project_without_database(
            message,
            turn_judgement,
            relationship_context,
            now=reference_now,
        )

    normalized_source_id = bounded_text(source_message_id, 128)
    try:
        with SyncSessionLocal.begin() as session:
            if session.execute(select(Users.id).where(Users.id == parsed_user_id)).scalar_one_or_none() is None:
                return project_without_database(
                    message,
                    turn_judgement,
                    relationship_context,
                    now=reference_now,
                )

            aura = session.execute(
                select(AuraInternalState)
                .where(AuraInternalState.user_id == parsed_user_id)
                .with_for_update()
            ).scalar_one_or_none()
            dynamics = session.execute(
                select(RelationshipDynamics)
                .where(RelationshipDynamics.user_id == parsed_user_id)
                .with_for_update()
            ).scalar_one_or_none()

            if aura is None:
                aura = AuraInternalState(user_id=parsed_user_id)
                session.add(aura)
            if dynamics is None:
                dynamics = RelationshipDynamics(user_id=parsed_user_id)
                session.add(dynamics)

            source_ids = bounded_string_list((aura.metadata_json or {}).get("source_message_ids"), 32)
            is_replay = bool(normalized_source_id and normalized_source_id in source_ids)
            prior_aura = aura_state_dict(aura, fallback_now=reference_now)
            prior_dynamics = relationship_dynamics_dict(dynamics, fallback_now=reference_now)
            projected_dynamics = derive_relationship_dynamics(
                prior_dynamics,
                message,
                turn_judgement,
                prior_last_seen_at=parse_datetime(prior_aura.get("last_user_seen_at")),
                now=reference_now,
                count_evidence=not is_replay,
            )
            projected_aura = derive_aura_internal_state(
                prior_aura,
                projected_dynamics,
                message,
                turn_judgement,
                relationship_context,
                now=reference_now,
            )
            apply_aura_projection(aura, projected_aura, reference_now)
            apply_dynamics_projection(dynamics, projected_dynamics, reference_now)
            if normalized_source_id and not is_replay:
                aura.metadata_json = {
                    **dict(aura.metadata_json or {}),
                    "version": AURA_STATE_VERSION,
                    "source_message_ids": append_bounded(source_ids, normalized_source_id, 32),
                }
            dynamics.metadata_json = {
                **dict(dynamics.metadata_json or {}),
                "version": RELATIONSHIP_DYNAMICS_VERSION,
            }
            session.flush()
            return {
                "aura_internal_state": aura_state_dict(aura, fallback_now=reference_now),
                "relationship_dynamics": relationship_dynamics_dict(
                    dynamics,
                    fallback_now=reference_now,
                ),
            }
    except Exception:
        logging.exception("玲凌自身状态读取或更新失败，聊天继续 user_id=%s", parsed_user_id)
        return project_without_database(
            message,
            turn_judgement,
            relationship_context,
            now=reference_now,
        )


def derive_relationship_dynamics(
    current: dict[str, Any],
    message: str,
    turn_judgement: dict[str, Any] | None,
    *,
    prior_last_seen_at: datetime | None,
    now: datetime,
    count_evidence: bool = True,
) -> dict[str, Any]:
    """用离散语义状态更新关系气氛，任何一轮最多推进一个阶段。"""

    result = {**default_relationship_dynamics(now=now), **dict(current or {})}
    text = (message or "").strip()
    interaction = (
        turn_judgement.get("interaction")
        if isinstance(turn_judgement, dict) and isinstance(turn_judgement.get("interaction"), dict)
        else {}
    )
    mode = str(interaction.get("mode") or "natural")
    target = str(interaction.get("target") or "unclear")
    has_affection_evidence = (
        mode == "affection" and target == "aura"
    ) or any(re.search(pattern, text) for pattern in AFFECTION_PATTERNS)
    if has_affection_evidence and count_evidence:
        result["stage_evidence_count"] = int(result.get("stage_evidence_count") or 0) + 1
        result["recent_positive_moment"] = bounded_text(text, 240)
        result["recent_closeness"] = "high"
        result["current_tone"] = "tender"

    if mode == "repair" and target == "aura":
        result["relationship_stage"] = "repair"
        result["current_tone"] = "repairing"
        result["unresolved_tension"] = bounded_text(text, 240)
        result["current_expectation"] = "把刚才的不舒服说清楚"
    elif result.get("relationship_stage") == "repair" and has_affection_evidence:
        result["relationship_stage"] = "stable"
        result["current_tone"] = "warm"
        result["unresolved_tension"] = None

    if prior_last_seen_at is not None:
        gap = now - normalize_utc(prior_last_seen_at)
        if gap >= timedelta(days=3):
            result["recent_distance"] = f"用户约 {max(3, gap.days)} 天没有出现"
            if result.get("relationship_stage") not in {"conflict", "repair"}:
                result["relationship_stage"] = "temporary_distance"
                result["current_tone"] = "distant"
        elif gap >= timedelta(hours=12):
            result["recent_distance"] = "用户有一段时间没有出现"
        elif text:
            result["recent_distance"] = None

    stage = str(result.get("relationship_stage") or "ambiguous")
    evidence_count = int(result.get("stage_evidence_count") or 0)
    if evidence_count >= STAGE_PROMOTION_EVIDENCE and stage in STAGE_ORDER:
        index = STAGE_ORDER.index(stage)
        if index < len(STAGE_ORDER) - 1:
            result["relationship_stage"] = STAGE_ORDER[index + 1]
            result["last_stage_change_at"] = now.isoformat()
            result["stage_evidence_count"] = 0
    result["version"] = int(result.get("version") or 1) + (1 if count_evidence else 0)
    result["updated_at"] = now.isoformat()
    return result


def derive_aura_internal_state(
    current: dict[str, Any],
    dynamics: dict[str, Any],
    message: str,
    turn_judgement: dict[str, Any] | None,
    relationship_context: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    """根据真实时间间隔、当前互动和已有关系事实更新玲凌自身状态。"""

    result = {**default_aura_internal_state(now=now), **dict(current or {})}
    text = (message or "").strip()
    previous_seen = parse_datetime(result.get("last_user_seen_at"))
    gap = now - previous_seen if previous_seen else None
    stage = str(dynamics.get("relationship_stage") or "ambiguous")
    result["attachment_tone"] = attachment_tone_for_stage(stage)
    result["missing_user"] = "none"
    result["desire_for_contact"] = "low"
    if gap is not None and gap >= timedelta(days=1):
        result["missing_user"] = "clear"
        result["desire_for_contact"] = "high"
    elif gap is not None and gap >= timedelta(hours=8):
        result["missing_user"] = "slight"
        result["desire_for_contact"] = "medium"

    emotion = turn_judgement.get("emotion") if isinstance(turn_judgement, dict) else {}
    interaction = turn_judgement.get("interaction") if isinstance(turn_judgement, dict) else {}
    user_emotion = str((emotion or {}).get("user_emotion") or "neutral")
    interaction_mode = str((interaction or {}).get("mode") or "natural")
    result["mood"] = "concerned" if user_emotion in {"distressed", "stressed", "angry", "lonely"} else "calm"
    result["playfulness"] = "medium" if stage in {"early_romance", "established_romance", "stable"} else "low"
    result["jealousy"] = "none"
    result["vulnerability"] = "low"
    result["unresolved_feeling"] = None

    if any(re.search(pattern, text) for pattern in JEALOUSY_PATTERNS):
        result["jealousy"] = "low"
        result["vulnerability"] = "medium"
        result["unresolved_feeling"] = "听到用户提起可能的约会对象，有一点在意"
        result["current_desire"] = "show_jealousy"
    elif relationship_has_due_thread(relationship_context):
        result["current_desire"] = "ask_follow_up"
    elif any(re.search(pattern, text) for pattern in RETURN_PATTERNS) and result["missing_user"] != "none":
        result["current_desire"] = "express_missing"
    elif any(re.search(pattern, text) for pattern in LEAVING_PATTERNS) and result["attachment_tone"] in {"close", "tender"}:
        result["current_desire"] = "seek_attention"
    elif interaction_mode == "affection":
        result["current_desire"] = "stay_close"
        result["mood"] = "warm"
    else:
        result["current_desire"] = "none"

    if is_meaningful_message(text):
        result["last_meaningful_interaction"] = bounded_text(text, 500)
    result["last_user_seen_at"] = now.isoformat()
    result["updated_at"] = now.isoformat()
    result["version"] = int(result.get("version") or 1) + 1
    return result


def format_aura_internal_state_prompt(state: dict[str, Any] | None) -> str:
    """把自身状态写成倾向而非强制表演命令。"""

    if not isinstance(state, dict):
        return "【玲凌当前状态】\n当前没有可用的持续状态。"
    return (
        "【玲凌当前状态】\n"
        "这是玲凌真实存在的当前倾向，不是必须逐项表演的命令；只有自然适合当前对话时才表达。\n"
        f"- 情绪：{state.get('mood') or 'calm'}\n"
        f"- 依恋语气：{state.get('attachment_tone') or 'steady'}\n"
        f"- 想念程度：{state.get('missing_user') or 'none'}\n"
        f"- 联系欲望：{state.get('desire_for_contact') or 'low'}\n"
        f"- 玩心 / 醋意 / 脆弱：{state.get('playfulness') or 'low'} / "
        f"{state.get('jealousy') or 'none'} / {state.get('vulnerability') or 'low'}\n"
        f"- 当前想做的事：{state.get('current_desire') or 'none'}\n"
        f"- 尚未消散的感受：{state.get('unresolved_feeling') or '无'}"
    )


def format_relationship_dynamics_prompt(dynamics: dict[str, Any] | None) -> str:
    """把关系动态提供给主模型，不允许据此虚构共同事件。"""

    if not isinstance(dynamics, dict):
        return "【关系动态】\n当前没有可用的关系动态。"
    return (
        "【关系动态】\n"
        "关系阶段只能影响语气，不能作为共同经历的事实来源，也不会因为单轮示爱自动跃迁。\n"
        f"- 阶段：{dynamics.get('relationship_stage') or 'ambiguous'}\n"
        f"- 当前气氛：{dynamics.get('current_tone') or 'warm'}\n"
        f"- 近期亲近程度：{dynamics.get('recent_closeness') or 'medium'}\n"
        f"- 未解决张力：{dynamics.get('unresolved_tension') or '无'}\n"
        f"- 近期距离：{dynamics.get('recent_distance') or '无'}\n"
        f"- 当前期待：{dynamics.get('current_expectation') or '无'}"
    )


async def mark_aura_proactive_sent_async(
    session: AsyncSession,
    user_id: UUID,
    *,
    sent_at: datetime,
) -> None:
    """主动消息真正写入聊天历史后，记录最近主动联系时间。"""

    result = await session.execute(
        select(AuraInternalState)
        .where(AuraInternalState.user_id == user_id)
        .with_for_update()
    )
    state = result.scalar_one_or_none()
    if state is None:
        state = AuraInternalState(user_id=user_id)
        session.add(state)
    state.last_proactive_at = normalize_utc(sent_at)
    state.desire_for_contact = "low"
    state.updated_at = normalize_utc(sent_at)
    state.version = int(getattr(state, "version", 1) or 1) + 1


def project_without_database(
    message: str,
    turn_judgement: dict[str, Any] | None,
    relationship_context: dict[str, Any] | None,
    *,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    dynamics = derive_relationship_dynamics(
        default_relationship_dynamics(now=now),
        message,
        turn_judgement,
        prior_last_seen_at=None,
        now=now,
    )
    aura = derive_aura_internal_state(
        default_aura_internal_state(now=now),
        dynamics,
        message,
        turn_judgement,
        relationship_context,
        now=now,
    )
    return {"aura_internal_state": aura, "relationship_dynamics": dynamics}


def apply_aura_projection(record: AuraInternalState, data: dict[str, Any], now: datetime) -> None:
    for field in (
        "mood", "attachment_tone", "missing_user", "desire_for_contact", "playfulness",
        "jealousy", "vulnerability", "unresolved_feeling", "current_desire",
        "last_meaningful_interaction",
    ):
        setattr(record, field, data.get(field))
    record.last_user_seen_at = parse_datetime(data.get("last_user_seen_at"))
    record.version = int(data.get("version") or 1)
    record.updated_at = now


def apply_dynamics_projection(record: RelationshipDynamics, data: dict[str, Any], now: datetime) -> None:
    for field in (
        "relationship_stage", "current_tone", "recent_closeness", "unresolved_tension",
        "recent_positive_moment", "recent_distance", "current_expectation", "stage_evidence_count",
    ):
        setattr(record, field, data.get(field))
    record.last_stage_change_at = parse_datetime(data.get("last_stage_change_at"))
    record.version = int(data.get("version") or 1)
    record.updated_at = now


def aura_state_dict(record: AuraInternalState, *, fallback_now: datetime) -> dict[str, Any]:
    return {
        "mood": str(getattr(record, "mood", None) or "calm"),
        "attachment_tone": str(getattr(record, "attachment_tone", None) or "steady"),
        "missing_user": str(getattr(record, "missing_user", None) or "none"),
        "desire_for_contact": str(getattr(record, "desire_for_contact", None) or "low"),
        "playfulness": str(getattr(record, "playfulness", None) or "low"),
        "jealousy": str(getattr(record, "jealousy", None) or "none"),
        "vulnerability": str(getattr(record, "vulnerability", None) or "low"),
        "unresolved_feeling": getattr(record, "unresolved_feeling", None),
        "current_desire": str(getattr(record, "current_desire", None) or "none"),
        "last_meaningful_interaction": getattr(record, "last_meaningful_interaction", None),
        "last_user_seen_at": iso_datetime(getattr(record, "last_user_seen_at", None)),
        "last_proactive_at": iso_datetime(getattr(record, "last_proactive_at", None)),
        "updated_at": iso_datetime(getattr(record, "updated_at", None)) or fallback_now.isoformat(),
        "version": int(getattr(record, "version", 1) or 1),
    }


def relationship_dynamics_dict(record: RelationshipDynamics, *, fallback_now: datetime) -> dict[str, Any]:
    return {
        "relationship_stage": str(getattr(record, "relationship_stage", None) or "ambiguous"),
        "current_tone": str(getattr(record, "current_tone", None) or "warm"),
        "recent_closeness": str(getattr(record, "recent_closeness", None) or "medium"),
        "unresolved_tension": getattr(record, "unresolved_tension", None),
        "recent_positive_moment": getattr(record, "recent_positive_moment", None),
        "recent_distance": getattr(record, "recent_distance", None),
        "current_expectation": getattr(record, "current_expectation", None),
        "stage_evidence_count": int(getattr(record, "stage_evidence_count", 0) or 0),
        "last_stage_change_at": iso_datetime(getattr(record, "last_stage_change_at", None)),
        "updated_at": iso_datetime(getattr(record, "updated_at", None)) or fallback_now.isoformat(),
        "version": int(getattr(record, "version", 1) or 1),
    }


def relationship_has_due_thread(context: dict[str, Any] | None) -> bool:
    if not isinstance(context, dict):
        return False
    return any(bool(item.get("is_due")) for item in context.get("items", []) if isinstance(item, dict))


def attachment_tone_for_stage(stage: str) -> str:
    if stage in {"early_romance", "stable"}:
        return "close"
    if stage == "established_romance":
        return "tender"
    if stage in {"conflict", "temporary_distance"}:
        return "guarded"
    return "steady"


def is_meaningful_message(text: str) -> bool:
    compact = re.sub(r"\s+", "", text or "")
    return len(compact) >= 4 and compact not in {"在吗", "早呀", "早安", "晚安", "嗯嗯"}


def bounded_text(value: Any, limit: int) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit] if text else None


def bounded_string_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:128] for item in value if str(item).strip()][-limit:]


def append_bounded(items: list[str], value: str, limit: int) -> list[str]:
    return [*items, value][-limit:]


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return normalize_utc(value)
    if not value:
        return None
    try:
        return normalize_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except (TypeError, ValueError):
        return None


def iso_datetime(value: Any) -> str | None:
    parsed = parse_datetime(value)
    return parsed.isoformat() if parsed else None


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
