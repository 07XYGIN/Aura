"""玲凌自身状态与关系动态的持久化和保守状态迁移。"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AffectState,
    AuraInternalState,
    RelationshipDynamics,
    RelationshipEvent,
    Users,
)
from app.db.session import SyncSessionLocal

AURA_STATE_VERSION = "aura-internal-state-v2"
RELATIONSHIP_DYNAMICS_VERSION = "relationship-dynamics-v2"
AFFECT_STATE_VERSION = "affect-state-v1"

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
CONFLICT_PATTERNS = (
    r"(?:我生气了|不想理你|你让我不舒服|我们吵架了|我讨厌你)",
    r"(?:你根本不|你从来不).{0,12}(?:在乎|理解|尊重)",
)
APOLOGY_PATTERNS = (r"(?:对不起|抱歉|我错了|别生气|原谅我)",)
REASSURANCE_PATTERNS = (r"(?:只喜欢你|最喜欢你|你最重要|别吃醋|没有别人)",)
MILESTONE_PATTERNS = (
    r"(?:我们在一起吧|做我女朋友|你是我女朋友|我们是恋人)",
    r"(?:以后也一直陪你|想和你一直走下去)",
)
BOUNDARY_PATTERNS = (r"(?:你不许|你必须|不准你).{0,12}(?:离开|拒绝|和别人)",)

AFFECT_DURATIONS = {
    "jealousy": {"low": timedelta(hours=24), "medium": timedelta(hours=36), "high": timedelta(hours=48)},
    "hurt": {"low": timedelta(hours=12), "medium": timedelta(hours=36), "high": timedelta(hours=72)},
    "longing": {"low": timedelta(hours=8), "medium": timedelta(hours=18), "high": timedelta(hours=30)},
    "unsettled": {"low": timedelta(hours=12), "medium": timedelta(hours=24), "high": timedelta(hours=48)},
}
INTENSITY_ORDER = ("low", "medium", "high")


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
        "relationship_phase": "normal",
        "relationship_tone": "warm",
        "recent_closeness": "medium",
        "unresolved_tension": None,
        "recent_positive_moment": None,
        "recent_distance": None,
        "current_expectation": None,
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
) -> dict[str, Any]:
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
            affect_records = list(
                session.execute(
                    select(AffectState)
                    .where(AffectState.user_id == parsed_user_id)
                    .with_for_update()
                ).scalars().all()
            )

            if aura is None:
                aura = AuraInternalState(user_id=parsed_user_id)
                session.add(aura)
            if dynamics is None:
                dynamics = RelationshipDynamics(user_id=parsed_user_id)
                session.add(dynamics)

            source_ids = bounded_string_list((aura.metadata_json or {}).get("source_message_ids"), 32)
            is_replay = bool(normalized_source_id and normalized_source_id in source_ids)
            prior_affects = [affect_state_dict(item, now=reference_now) for item in affect_records]
            prior_aura = aura_state_dict(
                aura,
                fallback_now=reference_now,
                affect_states=prior_affects,
            )
            prior_dynamics = relationship_dynamics_dict(dynamics, fallback_now=reference_now)
            event_candidates = (
                derive_relationship_events(
                    message,
                    turn_judgement,
                    relationship_phase=str(prior_dynamics.get("relationship_phase") or "normal"),
                    prior_last_seen_at=parse_datetime(prior_aura.get("last_user_seen_at")),
                    now=reference_now,
                )
                if not is_replay
                else []
            )
            persisted_events = persist_relationship_events(
                session,
                parsed_user_id,
                normalized_source_id,
                event_candidates,
                reference_now,
            )
            projected_dynamics = derive_relationship_dynamics(
                prior_dynamics,
                message,
                turn_judgement,
                prior_last_seen_at=parse_datetime(prior_aura.get("last_user_seen_at")),
                now=reference_now,
                events=event_candidates,
                apply_observation=not is_replay,
            )
            source_event_ids = {
                item.event_type: str(item.id)
                for item in persisted_events
            }
            projected_affects = derive_affect_states(
                prior_affects,
                message,
                event_candidates,
                now=reference_now,
                source_event_ids=source_event_ids,
                allow_reinforcement=not is_replay,
            )
            projected_aura = derive_aura_internal_state(
                prior_aura,
                projected_dynamics,
                message,
                turn_judgement,
                relationship_context,
                now=reference_now,
                affect_states=projected_affects,
            )
            apply_aura_projection(aura, projected_aura, reference_now)
            apply_dynamics_projection(dynamics, projected_dynamics, reference_now)
            apply_affect_projections(
                session,
                parsed_user_id,
                affect_records,
                projected_affects,
                reference_now,
            )
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
                "aura_internal_state": aura_state_dict(
                    aura,
                    fallback_now=reference_now,
                    affect_states=projected_affects,
                ),
                "relationship_dynamics": relationship_dynamics_dict(
                    dynamics,
                    fallback_now=reference_now,
                ),
                "relationship_events": [relationship_event_dict(item) for item in persisted_events],
                "affect_states": projected_affects,
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
    events: list[dict[str, Any]] | None = None,
    apply_observation: bool = True,
) -> dict[str, Any]:
    """从关系事件更新阶段、阶段内状况和语气三个独立维度。"""

    result = {**default_relationship_dynamics(now=now), **dict(current or {})}
    text = (message or "").strip()
    result["relationship_stage"] = normalize_relationship_stage(result.get("relationship_stage"))
    result["relationship_phase"] = normalize_relationship_phase(result.get("relationship_phase"))
    result["relationship_tone"] = normalize_relationship_tone(
        result.get("relationship_tone") or result.get("current_tone")
    )
    observed_events = events
    if observed_events is None:
        observed_events = derive_relationship_events(
            text,
            turn_judgement,
            relationship_phase=result["relationship_phase"],
            prior_last_seen_at=prior_last_seen_at,
            now=now,
        )
    event_types = {str(item.get("type") or "") for item in observed_events}

    if "affection_expressed" in event_types:
        result["recent_positive_moment"] = bounded_text(text, 240)
        result["recent_closeness"] = "high"
        if result["relationship_phase"] == "normal":
            result["relationship_tone"] = "tender"

    milestone = next(
        (item for item in observed_events if item.get("type") == "relationship_milestone"),
        None,
    )
    if milestone is not None:
        prior_stage = result["relationship_stage"]
        level = str((milestone.get("payload") or {}).get("level") or "early_romance")
        if level == "established_romance" and prior_stage == "early_romance":
            result["relationship_stage"] = "established_romance"
        elif prior_stage in {"early_closeness", "ambiguous"}:
            result["relationship_stage"] = "early_romance"
        if result["relationship_stage"] != prior_stage:
            result["last_stage_change_at"] = now.isoformat()

    if "conflict_started" in event_types or "boundary_crossed" in event_types:
        result["relationship_phase"] = "conflict"
        result["relationship_tone"] = "guarded"
        result["unresolved_tension"] = bounded_text(text, 240)
        result["current_expectation"] = "先确认边界和不舒服的地方"
    elif "apology" in event_types and result["relationship_phase"] == "conflict":
        result["relationship_phase"] = "repair"
        result["relationship_tone"] = "guarded"
        result["current_expectation"] = "看看道歉之后的行动是否一致"
    elif "repair_completed" in event_types:
        result["relationship_phase"] = "normal"
        result["relationship_tone"] = "warm"
        result["unresolved_tension"] = None
        result["current_expectation"] = None
    elif result["relationship_phase"] == "repair" and "affection_expressed" in event_types:
        result["relationship_phase"] = "normal"
        result["relationship_tone"] = "warm"
        result["unresolved_tension"] = None

    if prior_last_seen_at is not None:
        gap = now - normalize_utc(prior_last_seen_at)
        if gap >= timedelta(days=3) and result["relationship_phase"] not in {"conflict", "repair"}:
            result["relationship_phase"] = "distant"
            result["relationship_tone"] = "guarded"
            result["recent_distance"] = f"用户约 {max(3, gap.days)} 天没有出现"
        elif gap >= timedelta(hours=12):
            result["recent_distance"] = "用户有一段时间没有出现"
        elif text and result["relationship_phase"] != "distant":
            result["recent_distance"] = None

    if result["relationship_phase"] == "distant" and "affection_expressed" in event_types:
        result["relationship_phase"] = "normal"
        result["relationship_tone"] = "warm"
        result["recent_distance"] = None

    result["version"] = int(result.get("version") or 1) + (1 if apply_observation else 0)
    result["updated_at"] = now.isoformat()
    return result


def derive_relationship_events(
    message: str,
    turn_judgement: dict[str, Any] | None,
    *,
    relationship_phase: str,
    prior_last_seen_at: datetime | None,
    now: datetime,
) -> list[dict[str, Any]]:
    """Extract a small auditable event set from one turn without using scores."""

    text = (message or "").strip()
    interaction = (
        turn_judgement.get("interaction")
        if isinstance(turn_judgement, dict) and isinstance(turn_judgement.get("interaction"), dict)
        else {}
    )
    mode = str(interaction.get("mode") or "natural")
    target = str(interaction.get("target") or "unclear")
    affectionate = (
        mode == "affection" and target == "aura"
    ) or matches_any(text, AFFECTION_PATTERNS)
    candidates: list[dict[str, Any]] = []

    if affectionate:
        candidates.append(relationship_event("affection_expressed", text, "medium"))
    if matches_any(text, JEALOUSY_PATTERNS):
        candidates.append(
            relationship_event(
                "important_disclosure",
                text,
                "medium",
                payload={"affect": "jealousy"},
            )
        )
    if matches_any(text, CONFLICT_PATTERNS):
        candidates.append(relationship_event("conflict_started", text, "high"))
    if matches_any(text, BOUNDARY_PATTERNS):
        candidates.append(relationship_event("boundary_crossed", text, "high"))
    if matches_any(text, APOLOGY_PATTERNS):
        candidates.append(relationship_event("apology", text, "medium"))
    if relationship_phase == "repair" and (affectionate or matches_any(text, REASSURANCE_PATTERNS)):
        candidates.append(relationship_event("repair_completed", text, "high"))
    if matches_any(text, MILESTONE_PATTERNS):
        established = bool(re.search(r"(?:一直|走下去|已经是恋人)", text))
        candidates.append(
            relationship_event(
                "relationship_milestone",
                text,
                "high",
                payload={
                    "level": "established_romance" if established else "early_romance",
                },
            )
        )
    if re.search(r"(?:我答应你|我保证|以后会|一定会).{0,24}", text):
        candidates.append(relationship_event("promise_created", text, "medium"))

    if prior_last_seen_at is not None:
        gap = now - normalize_utc(prior_last_seen_at)
        if gap >= timedelta(days=3):
            candidates.append(
                relationship_event(
                    "distance_period",
                    f"用户离开约 {max(3, gap.days)} 天",
                    "medium",
                    actor="system",
                    target="relationship",
                    payload={"absence_seconds": int(gap.total_seconds())},
                )
            )
        if gap >= timedelta(hours=12):
            candidates.append(
                relationship_event(
                    "return_after_absence",
                    text or "用户重新出现",
                    "medium",
                    actor="system",
                    target="relationship",
                    payload={"absence_seconds": int(gap.total_seconds())},
                )
            )

    unique: dict[str, dict[str, Any]] = {}
    for item in candidates:
        unique.setdefault(str(item["type"]), item)
    return list(unique.values())


def relationship_event(
    event_type: str,
    summary: str,
    importance: str,
    *,
    actor: str = "user",
    target: str = "aura",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "actor": actor,
        "target": target,
        "importance": importance,
        "summary": bounded_text(summary, 500),
        "payload": dict(payload or {}),
    }


def persist_relationship_events(
    session: Any,
    user_id: UUID,
    source_turn_id: str | None,
    events: list[dict[str, Any]],
    occurred_at: datetime,
) -> list[RelationshipEvent]:
    """Persist each event type once per turn and return newly stored models."""

    if not source_turn_id or not events:
        return []
    event_types = [str(item.get("type") or "") for item in events]
    existing = set(
        session.execute(
            select(RelationshipEvent.event_type).where(
                RelationshipEvent.user_id == user_id,
                RelationshipEvent.source_turn_id == source_turn_id,
                RelationshipEvent.event_type.in_(event_types),
            )
        ).scalars().all()
    )
    models: list[RelationshipEvent] = []
    for item in events:
        event_type = str(item.get("type") or "")
        if not event_type or event_type in existing:
            continue
        model = RelationshipEvent(
            user_id=user_id,
            event_type=event_type,
            actor=str(item.get("actor") or "user"),
            target=str(item.get("target") or "aura"),
            importance=str(item.get("importance") or "medium"),
            summary=bounded_text(item.get("summary"), 500),
            source_turn_id=source_turn_id,
            payload_json=dict(item.get("payload") or {}),
            occurred_at=occurred_at,
        )
        session.add(model)
        models.append(model)
    if models:
        session.flush()
    return models


def relationship_event_dict(item: RelationshipEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "type": item.event_type,
        "actor": item.actor,
        "target": item.target,
        "importance": item.importance,
        "summary": item.summary,
        "source_turn_id": item.source_turn_id,
        "payload": dict(item.payload_json or {}),
        "occurred_at": iso_datetime(item.occurred_at),
    }


def derive_affect_states(
    current: list[dict[str, Any]],
    message: str,
    events: list[dict[str, Any]],
    *,
    now: datetime,
    source_event_id: str | None = None,
    source_event_ids: dict[str, str] | None = None,
    allow_reinforcement: bool = True,
) -> list[dict[str, Any]]:
    """Project affect half-lives, reinforcement, and explicit resolution."""

    states = {
        str(item.get("kind")): project_affect(item, now=now)
        for item in current
        if isinstance(item, dict) and item.get("kind")
    }
    event_types = {str(item.get("type") or "") for item in events}
    text = (message or "").strip()
    event_sources = dict(source_event_ids or {})

    def source_for(*event_type: str) -> str | None:
        return next(
            (event_sources[item] for item in event_type if event_sources.get(item)),
            source_event_id,
        )

    if matches_any(text, REASSURANCE_PATTERNS):
        resolve_affect(states, "jealousy", now)
    if "repair_completed" in event_types:
        resolve_affect(states, "hurt", now)

    if allow_reinforcement and any(
        item.get("type") == "important_disclosure"
        and (item.get("payload") or {}).get("affect") == "jealousy"
        for item in events
    ):
        upsert_affect(
            states,
            "jealousy",
            now=now,
            source_event_id=source_for("important_disclosure"),
        )
    if allow_reinforcement and (
        "conflict_started" in event_types or "boundary_crossed" in event_types
    ):
        upsert_affect(
            states,
            "hurt",
            now=now,
            source_event_id=source_for("conflict_started", "boundary_crossed"),
            initial_intensity="medium",
        )
    if allow_reinforcement and "return_after_absence" in event_types:
        upsert_affect(
            states,
            "longing",
            now=now,
            source_event_id=source_for("return_after_absence"),
        )

    return sorted(states.values(), key=lambda item: str(item.get("kind")))


def project_affect(value: dict[str, Any], *, now: datetime) -> dict[str, Any]:
    result = dict(value)
    started_at = parse_datetime(result.get("started_at")) or now
    reinforced_at = parse_datetime(result.get("last_reinforced_at")) or started_at
    decay_after = parse_datetime(result.get("decay_after")) or reinforced_at
    result.update(
        {
            "started_at": started_at.isoformat(),
            "last_reinforced_at": reinforced_at.isoformat(),
            "decay_after": decay_after.isoformat(),
        }
    )
    if result.get("resolved") or now >= decay_after:
        result["resolved"] = True
        result["resolved_at"] = result.get("resolved_at") or now.isoformat()
        result["decay_phase"] = "resolved"
        return result
    duration = max((decay_after - reinforced_at).total_seconds(), 1.0)
    elapsed_ratio = max(0.0, (now - reinforced_at).total_seconds()) / duration
    metadata = dict(result.get("metadata") or {})
    peak_intensity = str(metadata.get("peak_intensity") or result.get("intensity") or "low")
    intensity = peak_intensity
    if elapsed_ratio >= 0.5 and peak_intensity in {"high", "medium"}:
        intensity = INTENSITY_ORDER[max(0, INTENSITY_ORDER.index(peak_intensity) - 1)]
    result["intensity"] = intensity
    result["decay_phase"] = "fading" if elapsed_ratio >= 1 / 3 else "active"
    result["resolved"] = False
    return result


def upsert_affect(
    states: dict[str, dict[str, Any]],
    kind: str,
    *,
    now: datetime,
    source_event_id: str | None,
    initial_intensity: str = "low",
) -> None:
    previous = states.get(kind)
    if previous and not previous.get("resolved"):
        previous_intensity = str(previous.get("intensity") or "low")
        index = min(INTENSITY_ORDER.index(previous_intensity) + 1, len(INTENSITY_ORDER) - 1)
        intensity = INTENSITY_ORDER[index]
        started_at = parse_datetime(previous.get("started_at")) or now
        version = int(previous.get("version") or 1) + 1
    else:
        intensity = initial_intensity
        started_at = now
        version = int((previous or {}).get("version") or 0) + 1
    states[kind] = {
        "kind": kind,
        "intensity": intensity,
        "started_at": started_at.isoformat(),
        "last_reinforced_at": now.isoformat(),
        "decay_after": (now + AFFECT_DURATIONS[kind][intensity]).isoformat(),
        "source_event_id": source_event_id,
        "resolved": False,
        "resolved_at": None,
        "decay_phase": "active",
        "version": version,
        "metadata": {
            "version": AFFECT_STATE_VERSION,
            "peak_intensity": intensity,
        },
    }


def resolve_affect(states: dict[str, dict[str, Any]], kind: str, now: datetime) -> None:
    state = states.get(kind)
    if state is None or state.get("resolved"):
        return
    state["resolved"] = True
    state["resolved_at"] = now.isoformat()
    state["decay_phase"] = "resolved"
    state["version"] = int(state.get("version") or 1) + 1


def summarize_affects(states: list[dict[str, Any]], *, now: datetime) -> dict[str, Any]:
    active = [project_affect(item, now=now) for item in states]
    active = [item for item in active if not item.get("resolved")]
    by_kind = {str(item.get("kind")): item for item in active}
    jealousy = by_kind.get("jealousy")
    hurt = by_kind.get("hurt") or by_kind.get("unsettled")
    vulnerability = "medium" if jealousy or hurt else "low"
    if hurt and hurt.get("intensity") == "high":
        vulnerability = "high"
    feeling = None
    if hurt:
        feeling = "刚才的不舒服还没有完全消散"
    elif jealousy:
        feeling = "听到用户提起可能的约会对象，仍有一点在意"
    elif by_kind.get("longing"):
        feeling = "用户回来后，想念的余韵还在"
    return {
        "jealousy": str((jealousy or {}).get("intensity") or "none"),
        "vulnerability": vulnerability,
        "unresolved_feeling": feeling,
        "active_affects": active,
    }


def apply_affect_projections(
    session: Any,
    user_id: UUID,
    records: list[AffectState],
    projections: list[dict[str, Any]],
    now: datetime,
) -> None:
    by_kind = {item.kind: item for item in records}
    for data in projections:
        kind = str(data.get("kind") or "")
        if not kind:
            continue
        record = by_kind.get(kind)
        if record is None:
            record = AffectState(user_id=user_id, kind=kind)
            session.add(record)
            by_kind[kind] = record
        record.intensity = str(data.get("intensity") or "low")
        record.started_at = parse_datetime(data.get("started_at")) or now
        record.last_reinforced_at = parse_datetime(data.get("last_reinforced_at")) or now
        record.decay_after = parse_datetime(data.get("decay_after")) or now
        source_event_id = data.get("source_event_id")
        try:
            record.source_event_id = UUID(str(source_event_id)) if source_event_id else None
        except (TypeError, ValueError):
            record.source_event_id = None
        record.resolved = bool(data.get("resolved"))
        record.resolved_at = parse_datetime(data.get("resolved_at"))
        record.version = int(data.get("version") or 1)
        record.metadata_json = dict(data.get("metadata") or {"version": AFFECT_STATE_VERSION})
        record.updated_at = now


def affect_state_dict(item: AffectState, *, now: datetime) -> dict[str, Any]:
    return project_affect(
        {
            "kind": item.kind,
            "intensity": item.intensity,
            "started_at": iso_datetime(item.started_at),
            "last_reinforced_at": iso_datetime(item.last_reinforced_at),
            "decay_after": iso_datetime(item.decay_after),
            "source_event_id": str(item.source_event_id) if item.source_event_id else None,
            "resolved": bool(item.resolved),
            "resolved_at": iso_datetime(item.resolved_at),
            "version": int(item.version or 1),
            "metadata": dict(item.metadata_json or {}),
        },
        now=now,
    )


def derive_aura_internal_state(
    current: dict[str, Any],
    dynamics: dict[str, Any],
    message: str,
    turn_judgement: dict[str, Any] | None,
    relationship_context: dict[str, Any] | None,
    *,
    now: datetime,
    affect_states: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """根据真实时间间隔、当前互动和已有关系事实更新玲凌自身状态。"""

    result = {**default_aura_internal_state(now=now), **dict(current or {})}
    text = (message or "").strip()
    previous_seen = parse_datetime(result.get("last_user_seen_at"))
    gap = now - previous_seen if previous_seen else None
    stage = str(dynamics.get("relationship_stage") or "ambiguous")
    phase = str(dynamics.get("relationship_phase") or "normal")
    result["attachment_tone"] = attachment_tone_for_relationship(stage, phase)
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
    result["playfulness"] = (
        "medium"
        if stage in {"early_romance", "established_romance"}
        and dynamics.get("relationship_tone") == "playful"
        else "low"
    )
    affect_summary = summarize_affects(affect_states or [], now=now)
    result.update(affect_summary)
    result["active_affects"] = affect_summary["active_affects"]

    if result["jealousy"] in {"low", "medium"}:
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
        f"- 尚未消散的感受：{state.get('unresolved_feeling') or '无'}\n"
        f"- 活跃余韵：{format_active_affects(state.get('active_affects'))}"
    )


def format_relationship_dynamics_prompt(dynamics: dict[str, Any] | None) -> str:
    """把关系动态提供给主模型，不允许据此虚构共同事件。"""

    if not isinstance(dynamics, dict):
        return "【关系动态】\n当前没有可用的关系动态。"
    return (
        "【关系动态】\n"
        "阶段、当前状况和语气是三个独立维度；它们不能作为共同经历的事实来源，"
        "也不会因为单轮示爱自动跃迁。\n"
        f"- 阶段：{dynamics.get('relationship_stage') or 'ambiguous'}\n"
        f"- 当前状况：{dynamics.get('relationship_phase') or 'normal'}\n"
        f"- 当前语气：{dynamics.get('relationship_tone') or 'warm'}\n"
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
) -> dict[str, Any]:
    events = derive_relationship_events(
        message,
        turn_judgement,
        relationship_phase="normal",
        prior_last_seen_at=None,
        now=now,
    )
    dynamics = derive_relationship_dynamics(
        default_relationship_dynamics(now=now),
        message,
        turn_judgement,
        prior_last_seen_at=None,
        now=now,
        events=events,
    )
    affects = derive_affect_states(
        [],
        message,
        events,
        now=now,
    )
    aura = derive_aura_internal_state(
        default_aura_internal_state(now=now),
        dynamics,
        message,
        turn_judgement,
        relationship_context,
        now=now,
        affect_states=affects,
    )
    return {
        "aura_internal_state": aura,
        "relationship_dynamics": dynamics,
        "relationship_events": events,
        "affect_states": affects,
    }


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
        "relationship_stage", "relationship_phase", "relationship_tone", "recent_closeness",
        "unresolved_tension", "recent_positive_moment", "recent_distance", "current_expectation",
    ):
        setattr(record, field, data.get(field))
    record.last_stage_change_at = parse_datetime(data.get("last_stage_change_at"))
    record.version = int(data.get("version") or 1)
    record.updated_at = now


def aura_state_dict(
    record: AuraInternalState,
    *,
    fallback_now: datetime,
    affect_states: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result = {
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
    if affect_states is not None:
        result.update(summarize_affects(affect_states, now=fallback_now))
    else:
        result["active_affects"] = []
    return result


def relationship_dynamics_dict(record: RelationshipDynamics, *, fallback_now: datetime) -> dict[str, Any]:
    return {
        "relationship_stage": str(getattr(record, "relationship_stage", None) or "ambiguous"),
        "relationship_phase": str(getattr(record, "relationship_phase", None) or "normal"),
        "relationship_tone": str(getattr(record, "relationship_tone", None) or "warm"),
        "recent_closeness": str(getattr(record, "recent_closeness", None) or "medium"),
        "unresolved_tension": getattr(record, "unresolved_tension", None),
        "recent_positive_moment": getattr(record, "recent_positive_moment", None),
        "recent_distance": getattr(record, "recent_distance", None),
        "current_expectation": getattr(record, "current_expectation", None),
        "last_stage_change_at": iso_datetime(getattr(record, "last_stage_change_at", None)),
        "updated_at": iso_datetime(getattr(record, "updated_at", None)) or fallback_now.isoformat(),
        "version": int(getattr(record, "version", 1) or 1),
    }


def relationship_has_due_thread(context: dict[str, Any] | None) -> bool:
    if not isinstance(context, dict):
        return False
    return any(bool(item.get("is_due")) for item in context.get("items", []) if isinstance(item, dict))


def attachment_tone_for_relationship(stage: str, phase: str) -> str:
    if phase in {"conflict", "distant", "repair"}:
        return "guarded"
    if stage == "early_romance":
        return "close"
    if stage == "established_romance":
        return "tender"
    return "steady"


def normalize_relationship_stage(value: Any) -> str:
    stage = str(value or "ambiguous")
    if stage == "stable":
        return "established_romance"
    if stage in {"temporary_distance", "conflict", "repair"}:
        return "ambiguous"
    if stage in {"early_closeness", "ambiguous", "early_romance", "established_romance"}:
        return stage
    return "ambiguous"


def normalize_relationship_phase(value: Any) -> str:
    phase = str(value or "normal")
    return phase if phase in {"normal", "distant", "conflict", "repair"} else "normal"


def normalize_relationship_tone(value: Any) -> str:
    tone = str(value or "warm")
    aliases = {
        "neutral": "steady",
        "tense": "guarded",
        "distant": "guarded",
        "repairing": "guarded",
    }
    tone = aliases.get(tone, tone)
    return tone if tone in {"steady", "warm", "playful", "tender", "guarded"} else "warm"


def format_active_affects(value: Any) -> str:
    if not isinstance(value, list):
        return "无"
    parts = [
        f"{item.get('kind')}:{item.get('intensity')}({item.get('decay_phase') or 'active'})"
        for item in value
        if isinstance(item, dict) and not item.get("resolved")
    ]
    return "、".join(parts) or "无"


def matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text or "") for pattern in patterns)


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
