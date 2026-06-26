from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuraSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ConversationSessionRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    id: str | None = None
    aura_profile_id: str | None = Field(default=None, alias="auraProfileId")
    channel: str | None = None
    title: str | None = None
    status: str | None = None
    summary: str | None = None
    metadata: Any = None


class EmotionSnapshotRequest(AuraSchema):
    session_id: str | None = Field(default=None, alias="sessionId")
    message_id: str | None = Field(default=None, alias="messageId")
    source: str | None = None
    dominant_emotion: str | None = Field(default=None, alias="dominantEmotion")
    valence: Decimal | None = None
    arousal: Decimal | None = None
    intensity: Decimal | None = None
    emotion_scores: Any = Field(default=None, alias="emotionScores")
    reason: str | None = None


class ChatMessageRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    sender_type: str = Field(alias="senderType")
    sender_id: str | None = Field(default=None, alias="senderId")
    content: str
    content_type: str | None = Field(default=None, alias="contentType")
    emotion_label: str | None = Field(default=None, alias="emotionLabel")
    token_count: int | None = Field(default=None, alias="tokenCount")
    metadata: Any = None
    emotion_snapshot: EmotionSnapshotRequest | None = Field(default=None, alias="emotionSnapshot")


class RelationshipEventRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    relationship_state_id: str | None = Field(default=None, alias="relationshipStateId")
    event_type: str = Field(alias="eventType")
    title: str | None = None
    description: str | None = None
    delta_intimacy: int | None = Field(default=None, alias="deltaIntimacy")
    delta_trust: int | None = Field(default=None, alias="deltaTrust")
    delta_affection: int | None = Field(default=None, alias="deltaAffection")
    delta_conflict: int | None = Field(default=None, alias="deltaConflict")
    occurred_at: datetime | None = Field(default=None, alias="occurredAt")
    metadata: Any = None


class MemoryItemRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    aura_profile_id: str | None = Field(default=None, alias="auraProfileId")
    source_session_id: str | None = Field(default=None, alias="sourceSessionId")
    source_message_id: str | None = Field(default=None, alias="sourceMessageId")
    memory_type: str = Field(alias="memoryType")
    title: str | None = None
    content: str
    embedding: Any = None
    salience: int | None = None
    confidence: Decimal | None = None
    status: str | None = None
    tags: Any = None
    metadata: Any = None


class ConversationFeedbackRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    session_id: str = Field(alias="sessionId")
    score: int = Field(ge=1, le=5)
    comment: str | None = None


class UserBehaviorEventRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    message_id: str | None = Field(default=None, alias="messageId")
    event_type: str = Field(alias="eventType")
    event_time: datetime | None = Field(default=None, alias="eventTime")
    metadata: Any = None


class ReportPurchaseRequest(AuraSchema):
    user_id: str = Field(alias="userId")


class AuraProfileRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    id: str | None = None
    nickname: str | None = None
    persona_summary: str | None = Field(default=None, alias="personaSummary")
    voice_style: str | None = Field(default=None, alias="voiceStyle")
    appearance: str | None = None
    boundaries: str | None = None
    system_prompt: str | None = Field(default=None, alias="systemPrompt")
    greeting_style: str | None = Field(default=None, alias="greetingStyle")


class UserProfileRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    display_name: str | None = Field(default=None, alias="displayName")
    birthday: str | None = None
    pronouns: str | None = None
    timezone: str | None = None
    locale: str | None = None
    preferences: Any = None
    boundaries: Any = None
    taboos: Any = None
    city_adcode: str | None = Field(default=None, alias="cityAdcode")


class RelationshipStateRequest(AuraSchema):
    user_id: str = Field(alias="userId")
    id: str | None = None
    aura_profile_id: str | None = Field(default=None, alias="auraProfileId")
    relationship_stage: str | None = Field(default=None, alias="relationshipStage")
    intimacy_level: int | None = Field(default=None, alias="intimacyLevel")
    trust_level: int | None = Field(default=None, alias="trustLevel")
    affection_level: int | None = Field(default=None, alias="affectionLevel")
    conflict_level: int | None = Field(default=None, alias="conflictLevel")
    current_mood: str | None = Field(default=None, alias="currentMood")
    last_interaction_at: datetime | None = Field(default=None, alias="lastInteractionAt")
    metadata: Any = None
