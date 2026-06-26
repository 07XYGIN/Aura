from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TableSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class UsersDto(TableSchema):
    id: str | None = None
    username: str
    password: str | None = None
    email: str | None = None
    sex: int | None = Field(default=None, ge=0, le=1)
    age: int | None = Field(default=None, ge=0, le=150)
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class InvitationCodeDto(TableSchema):
    id: str | None = None
    code: str
    batch_name: str | None = Field(default=None, alias="batchName")
    max_uses: int | None = Field(default=None, alias="maxUses")
    used_count: int | None = Field(default=None, alias="usedCount")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    disabled_at: datetime | None = Field(default=None, alias="disabledAt")
    created_by: str | None = Field(default=None, alias="createdBy")
    last_used_by: str | None = Field(default=None, alias="lastUsedBy")
    last_used_at: datetime | None = Field(default=None, alias="lastUsedAt")
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class InvitationCodeRedemptionDto(TableSchema):
    id: str | None = None
    invite_code_id: str = Field(alias="inviteCodeId")
    user_id: str = Field(alias="userId")
    redeemed_at: datetime | None = Field(default=None, alias="redeemedAt")
    metadata: Any = None


class AuraProfileDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    nickname: str | None = None
    persona_summary: str | None = Field(default=None, alias="personaSummary")
    voice_style: str | None = Field(default=None, alias="voiceStyle")
    appearance: str | None = None
    boundaries: str | None = None
    system_prompt: str | None = Field(default=None, alias="systemPrompt")
    greeting_style: str | None = Field(default=None, alias="greetingStyle")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class UserProfileDto(TableSchema):
    user_id: str = Field(alias="userId")
    display_name: str | None = Field(default=None, alias="displayName")
    birthday: date | None = None
    pronouns: str | None = None
    timezone: str | None = None
    locale: str | None = None
    preferences: Any = None
    boundaries: Any = None
    taboos: Any = None
    city_adcode: str | None = Field(default=None, alias="cityAdcode")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class RelationshipStateDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    aura_profile_id: str | None = Field(default=None, alias="auraProfileId")
    relationship_stage: str | None = Field(default=None, alias="relationshipStage")
    intimacy_level: int | None = Field(default=None, alias="intimacyLevel")
    trust_level: int | None = Field(default=None, alias="trustLevel")
    affection_level: int | None = Field(default=None, alias="affectionLevel")
    conflict_level: int | None = Field(default=None, alias="conflictLevel")
    current_mood: str | None = Field(default=None, alias="currentMood")
    last_interaction_at: datetime | None = Field(default=None, alias="lastInteractionAt")
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class RelationshipEventDto(TableSchema):
    id: str | None = None
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
    created_at: datetime | None = Field(default=None, alias="createdAt")


class ConversationSessionDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    aura_profile_id: str | None = Field(default=None, alias="auraProfileId")
    channel: str | None = None
    title: str | None = None
    status: str | None = None
    started_at: datetime | None = Field(default=None, alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")
    summary: str | None = None
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class ChatMessageDto(TableSchema):
    id: str | None = None
    session_id: str = Field(alias="sessionId")
    user_id: str = Field(alias="userId")
    sender_type: str = Field(alias="senderType")
    sender_id: str | None = Field(default=None, alias="senderId")
    content: str
    content_type: str | None = Field(default=None, alias="contentType")
    emotion_label: str | None = Field(default=None, alias="emotionLabel")
    token_count: int | None = Field(default=None, alias="tokenCount")
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")


class EmotionSnapshotDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    message_id: str | None = Field(default=None, alias="messageId")
    source: str | None = None
    dominant_emotion: str | None = Field(default=None, alias="dominantEmotion")
    valence: Decimal | None = None
    arousal: Decimal | None = None
    intensity: Decimal | None = None
    emotion_scores: Any = Field(default=None, alias="emotionScores")
    reason: str | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")


class MemoryItemDto(TableSchema):
    id: str | None = None
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
    last_recalled_at: datetime | None = Field(default=None, alias="lastRecalledAt")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class MemoryRelationDto(TableSchema):
    id: str | None = None
    memory_id: str = Field(alias="memoryId")
    relation_type: str = Field(alias="relationType")
    target_type: str = Field(alias="targetType")
    target_id: str = Field(alias="targetId")
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")


class PromptVersionDto(TableSchema):
    id: str | None = None
    name: str
    version: str
    prompt_type: str | None = Field(default=None, alias="promptType")
    content: str
    status: str | None = None
    created_by: str | None = Field(default=None, alias="createdBy")
    created_at: datetime | None = Field(default=None, alias="createdAt")


class SafetyEventDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    message_id: str | None = Field(default=None, alias="messageId")
    risk_type: str = Field(alias="riskType")
    risk_level: str | None = Field(default=None, alias="riskLevel")
    intervention: str | None = None
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")


class DailyCheckinDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    checkin_date: date = Field(alias="checkinDate")
    morning_sent_at: datetime | None = Field(default=None, alias="morningSentAt")
    evening_sent_at: datetime | None = Field(default=None, alias="eveningSentAt")
    interaction_count: int | None = Field(default=None, alias="interactionCount")
    streak_days: int | None = Field(default=None, alias="streakDays")
    mood_label: str | None = Field(default=None, alias="moodLabel")
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class NotificationPlanDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    plan_type: str = Field(alias="planType")
    title: str
    message_template: str = Field(alias="messageTemplate")
    timezone: str | None = None
    morning_window_start: time | None = Field(default=None, alias="morningWindowStart")
    morning_window_end: time | None = Field(default=None, alias="morningWindowEnd")
    evening_window_start: time | None = Field(default=None, alias="eveningWindowStart")
    evening_window_end: time | None = Field(default=None, alias="eveningWindowEnd")
    next_fire_at: datetime | None = Field(default=None, alias="nextFireAt")
    random_seed: str | None = Field(default=None, alias="randomSeed")
    status: str | None = None
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class ProactiveMessageDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    notification_plan_id: str | None = Field(default=None, alias="notificationPlanId")
    trigger_type: str = Field(alias="triggerType")
    title: str | None = None
    content: str
    scheduled_at: datetime = Field(alias="scheduledAt")
    sent_at: datetime | None = Field(default=None, alias="sentAt")
    status: str | None = None
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class UserExportJobDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    job_type: str = Field(alias="jobType")
    status: str | None = None
    file_url: str | None = Field(default=None, alias="fileUrl")
    requested_at: datetime | None = Field(default=None, alias="requestedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    metadata: Any = None


class AdminAuditLogDto(TableSchema):
    id: str | None = None
    admin_user_id: str | None = Field(default=None, alias="adminUserId")
    action: str
    target_type: str | None = Field(default=None, alias="targetType")
    target_id: str | None = Field(default=None, alias="targetId")
    detail: Any = None
    ip_address: str | None = Field(default=None, alias="ipAddress")
    created_at: datetime | None = Field(default=None, alias="createdAt")


class ConversationFeedbackDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    session_id: str = Field(alias="sessionId")
    score: int = Field(ge=1, le=5)
    comment: str | None = None
    created_at: datetime | None = Field(default=None, alias="createdAt")


class UserBehaviorEventDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    session_id: str | None = Field(default=None, alias="sessionId")
    message_id: str | None = Field(default=None, alias="messageId")
    event_type: str = Field(alias="eventType")
    event_time: datetime | None = Field(default=None, alias="eventTime")
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")


class UserMemoryEntitlementDto(TableSchema):
    user_id: str = Field(alias="userId")
    permanent_memory: bool | None = Field(default=None, alias="permanentMemory")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    metadata: Any = None
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class EmotionInsightReportDto(TableSchema):
    id: str | None = None
    user_id: str = Field(alias="userId")
    status: str | None = None
    price_cents: int | None = Field(default=None, alias="priceCents")
    preview_keywords: Any = Field(default=None, alias="previewKeywords")
    preview_text: str | None = Field(default=None, alias="previewText")
    full_report: Any = Field(default=None, alias="fullReport")
    paid_at: datetime | None = Field(default=None, alias="paidAt")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")


class LangchainPgCollectionDto(TableSchema):
    uuid: str | None = None
    name: str
    cmetadata: Any = None


class LangchainPgEmbeddingDto(TableSchema):
    id: str
    collection_id: str | None = Field(default=None, alias="collectionId")
    embedding: Any = None
    document: str | None = None
    cmetadata: Any = None
