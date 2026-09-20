"""Pure decision layer for relationship-driven proactive messages."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


RELATIONSHIP_CONTACT_COOLDOWN = timedelta(hours=18)
RELATIONSHIP_CONTACT_RECENT_ACTIVITY = timedelta(hours=6)
RELATIONSHIP_CONTACT_DAILY_LIMIT = 1


class ProactiveIntent(BaseModel):
    reason: str
    content: str
    source: str
    importance: int = Field(default=1, ge=1, le=5)
    not_before: datetime
    expires_at: datetime
    cooldown_group: str = "relationship_contact"
    metadata: dict[str, Any] = Field(default_factory=dict)


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_optional_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return normalize_utc(value)
    if not value:
        return None
    try:
        return normalize_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except (TypeError, ValueError):
        return None


def relationship_contact_eligibility(
    aura_state: dict[str, object],
    relationship_dynamics: dict[str, object],
    *,
    now: datetime,
    daily_contact_count: int,
    has_open_thread: bool,
    deep_night: bool = False,
) -> tuple[bool, str]:
    reference_now = normalize_utc(now)
    if deep_night:
        return False, "deep_night"
    if daily_contact_count >= RELATIONSHIP_CONTACT_DAILY_LIMIT:
        return False, "daily_limit"
    last_user_seen = parse_optional_datetime(aura_state.get("last_user_seen_at"))
    if last_user_seen is None:
        return False, "no_user_activity"
    if reference_now - last_user_seen < RELATIONSHIP_CONTACT_RECENT_ACTIVITY:
        return False, "recent_user_activity"
    last_proactive = parse_optional_datetime(aura_state.get("last_proactive_at"))
    if last_proactive is not None and reference_now - last_proactive < RELATIONSHIP_CONTACT_COOLDOWN:
        return False, "cooldown"
    if last_proactive is not None and last_proactive >= last_user_seen:
        return False, "awaiting_user_return"
    desire = str(aura_state.get("desire_for_contact") or "none")
    missing = str(aura_state.get("missing_user") or "none")
    unresolved = bool(aura_state.get("unresolved_feeling"))
    expectation = bool(relationship_dynamics.get("current_expectation"))
    if desire not in {"medium", "high"}:
        return False, "insufficient_desire"
    if not (missing in {"slight", "clear"} or unresolved or expectation or has_open_thread):
        return False, "no_relationship_reason"
    return True, "eligible"


def plan_relationship_contact(
    aura_state: dict[str, object],
    relationship_dynamics: dict[str, object],
    *,
    now: datetime,
    daily_contact_count: int,
    deep_night: bool,
    thread_title: str | None = None,
    thread_summary: str | None = None,
    thread_id: str | None = None,
) -> ProactiveIntent | None:
    """Return a bounded intent; persistence and delivery belong to the scheduler."""

    eligible, reason = relationship_contact_eligibility(
        aura_state,
        relationship_dynamics,
        now=now,
        daily_contact_count=daily_contact_count,
        has_open_thread=bool(thread_id),
        deep_night=deep_night,
    )
    if not eligible:
        return None
    reference_now = normalize_utc(now)
    if thread_id:
        subject = " ".join(str(thread_title or thread_summary or "你之前提到的那件事").split())
        content = f"你之前说的“{subject[:60]}”，后来怎么样了？"
        source = "relationship_thread"
    elif aura_state.get("unresolved_feeling"):
        content = "没什么。就是想叫你一下。"
        source = "aura_unresolved_feeling"
    else:
        content = "刚刚想起你了。忙的话不用急着回。"
        source = "aura_missing_user"
    return ProactiveIntent(
        reason=reason,
        content=content,
        source=source,
        importance=2 if thread_id else 1,
        not_before=reference_now,
        expires_at=reference_now + timedelta(hours=6),
        metadata={"relationship_thread_id": thread_id},
    )

