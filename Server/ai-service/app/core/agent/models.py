"""Strongly typed contracts shared by Aura's turn pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InitiativeLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AffectionTone(StrEnum):
    NONE = "none"
    SUBTLE = "subtle"
    CLEAR = "clear"


class AuraDesire(StrEnum):
    NONE = "none"
    STAY_CLOSE = "stay_close"
    ASK_FOLLOW_UP = "ask_follow_up"
    TEASE = "tease"
    EXPRESS_MISSING = "express_missing"
    SEEK_ATTENTION = "seek_attention"
    SHARE_REACTION = "share_reaction"
    SHOW_JEALOUSY = "show_jealousy"
    OFFER_COMFORT = "offer_comfort"
    RECALL_SHARED_MOMENT = "recall_shared_moment"
    WAIT_SILENTLY = "wait_silently"


class JealousyLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"


class VulnerabilityLevel(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResponseMode(StrEnum):
    CRISIS_SUPPORT = "crisis_support"
    LONELY_SUPPORT = "lonely_support"
    GENTLE_SUPPORT = "gentle_support"
    RELATIONSHIP_REPAIR = "relationship_repair"
    WARM_AFFECTION = "warm_affection"
    NATURAL_CHAT = "natural_chat"


class InteractionMode(StrEnum):
    NORMAL = "normal"
    RETRY = "retry"
    ACTIVITY = "activity"


class RelationshipStage(StrEnum):
    EARLY_CLOSENESS = "early_closeness"
    AMBIGUOUS = "ambiguous"
    EARLY_ROMANCE = "early_romance"
    ESTABLISHED_ROMANCE = "established_romance"


class RelationshipPhase(StrEnum):
    NORMAL = "normal"
    DISTANT = "distant"
    CONFLICT = "conflict"
    REPAIR = "repair"


class RelationshipTone(StrEnum):
    STEADY = "steady"
    WARM = "warm"
    PLAYFUL = "playful"
    TENDER = "tender"
    GUARDED = "guarded"


class RelationshipEventType(StrEnum):
    AFFECTION_EXPRESSED = "affection_expressed"
    AURA_EXPRESSED_MISSING = "aura_expressed_missing"
    IMPORTANT_DISCLOSURE = "important_disclosure"
    CONFLICT_STARTED = "conflict_started"
    BOUNDARY_CROSSED = "boundary_crossed"
    APOLOGY = "apology"
    REPAIR_COMPLETED = "repair_completed"
    PROMISE_CREATED = "promise_created"
    PROMISE_FULFILLED = "promise_fulfilled"
    SHARED_MOMENT = "shared_moment"
    RELATIONSHIP_MILESTONE = "relationship_milestone"
    DISTANCE_PERIOD = "distance_period"
    RETURN_AFTER_ABSENCE = "return_after_absence"


class AffectKind(StrEnum):
    JEALOUSY = "jealousy"
    HURT = "hurt"
    LONGING = "longing"
    UNSETTLED = "unsettled"


class AffectState(BaseModel):
    kind: AffectKind
    intensity: InitiativeLevel
    started_at: str
    last_reinforced_at: str
    decay_after: str
    source_event_id: str | None = None
    resolved: bool = False
    decay_phase: str = "active"


class ImpulseCandidate(BaseModel):
    desire: AuraDesire
    strength: InitiativeLevel
    source: str
    affection: AffectionTone = AffectionTone.NONE
    playfulness: InitiativeLevel = InitiativeLevel.LOW
    jealousy: JealousyLevel = JealousyLevel.NONE
    vulnerability: VulnerabilityLevel = VulnerabilityLevel.LOW
    follow_up: bool = False
    silence_preferred: bool = False
    relevance: int = Field(default=0, ge=0, le=100)
    freshness: int = Field(default=50, ge=0, le=100)
    interrupt_risk: int = Field(default=0, ge=0, le=100)
    reason: str = Field(default="", max_length=300)
    source_refs: list[str] = Field(default_factory=list, max_length=4)


class AuraImpulse(BaseModel):
    """Validated expression intent; this is not user-visible chain-of-thought."""

    initiative: InitiativeLevel = InitiativeLevel.NONE
    desire: AuraDesire = AuraDesire.NONE
    affection: AffectionTone = AffectionTone.NONE
    playfulness: InitiativeLevel = InitiativeLevel.LOW
    jealousy: JealousyLevel = JealousyLevel.NONE
    vulnerability: VulnerabilityLevel = VulnerabilityLevel.LOW
    follow_up: bool = False
    silence_preferred: bool = False
    reason: str = Field(default="", max_length=300)
    source_refs: list[str] = Field(default_factory=list, max_length=4)


class RiskSignal(BaseModel):
    level: str = "none"
    risk_type: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    requires_safety_gate: bool = False


class TurnJudgement(BaseModel):
    emotion: dict[str, Any] = Field(default_factory=dict)
    interaction: dict[str, Any] = Field(default_factory=dict)
    memory_candidate: dict[str, Any] = Field(default_factory=dict)
    risk_signal: RiskSignal = Field(default_factory=RiskSignal)
    response_mode: ResponseMode = ResponseMode.NATURAL_CHAT


class InteractionState(BaseModel):
    mode: InteractionMode = InteractionMode.NORMAL
    activity: str | None = None
    branch_id: str | None = None
    retry_message_id: str | None = None


class TurnRequest(BaseModel):
    """Transport-independent input to one conversation turn."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    message: str = ""
    client_message_id: str | None = None
    attachment_ids: list[str] = Field(default_factory=list)
    city_adcode: str | None = None
    branch_id: str | None = None
    retry_message_id: str | None = None


class ActivityResult(BaseModel):
    """Normalized result returned by every optional activity plugin."""

    activity: str
    action: str
    messages: list[str] = Field(min_length=1)
    snapshot: dict[str, Any] | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class TurnPlan(BaseModel):
    """Decision made by the orchestrator before streaming begins."""

    request: TurnRequest
    interaction: InteractionState
    activity_result: ActivityResult | None = None


class RelationshipStateView(BaseModel):
    relationship_stage: RelationshipStage = RelationshipStage.AMBIGUOUS
    relationship_phase: RelationshipPhase = RelationshipPhase.NORMAL
    relationship_tone: RelationshipTone = RelationshipTone.WARM
    current_expectation: str | None = None
    recent_positive_moment: str | None = None
