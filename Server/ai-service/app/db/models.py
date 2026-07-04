from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, Time, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Users(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    sex: Mapped[int | None] = mapped_column(SmallInteger)
    age: Mapped[int | None] = mapped_column(Integer)


class InvitationCode(Base, TimestampMixin):
    __tablename__ = "invitation_code"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    batch_name: Mapped[str | None] = mapped_column(String(128))
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    last_used_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class InvitationCodeRedemption(Base):
    __tablename__ = "invitation_code_redemption"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    invite_code_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class AuraProfile(Base):
    __tablename__ = "aura_profile"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, default="Aura")
    persona_summary: Mapped[str | None] = mapped_column(Text)
    voice_style: Mapped[str | None] = mapped_column(Text)
    appearance: Mapped[str | None] = mapped_column(Text)
    boundaries: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    greeting_style: Mapped[str | None] = mapped_column(String(64), default="warm")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RelationshipState(Base, TimestampMixin):
    __tablename__ = "relationship_state"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    aura_profile_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    relationship_stage: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    intimacy_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trust_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    affection_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conflict_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_mood: Mapped[str] = mapped_column(String(64), nullable=False, default="neutral")
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class ConversationSession(Base, TimestampMixin):
    __tablename__ = "conversation_session"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    aura_profile_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    title: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversation_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    sender_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    emotion_label: Mapped[str | None] = mapped_column(String(64))
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    batch_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    batch_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EmotionSnapshot(Base):
    __tablename__ = "emotion_snapshot"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    message_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    dominant_emotion: Mapped[str | None] = mapped_column(String(64))
    valence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    arousal: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    intensity: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    emotion_scores: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MemoryItem(Base, TimestampMixin):
    __tablename__ = "memory_item"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    aura_profile_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_session_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source_message_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, default="preference")
    title: Mapped[str | None] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    salience: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    last_recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RelationshipEvent(Base):
    __tablename__ = "relationship_event"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    relationship_state_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    delta_intimacy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delta_trust: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delta_affection: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delta_conflict: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profile"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(64))
    birthday: Mapped[date | None] = mapped_column(Date)
    pronouns: Mapped[str | None] = mapped_column(String(32))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    locale: Mapped[str] = mapped_column(String(32), nullable=False, default="zh-CN")
    preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    boundaries: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    taboos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    city_adcode: Mapped[str | None] = mapped_column(String(6))


class MemoryRelation(Base):
    __tablename__ = "memory_relation"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    memory_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class PromptVersion(Base):
    __tablename__ = "prompt_version"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_type: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class SelfChangelogEntry(Base, TimestampMixin):
    __tablename__ = "self_changelog_entry"
    __table_args__ = (
        UniqueConstraint("change_date", "title", name="uq_self_changelog_entry_change_date_title"),
        Index("idx_self_changelog_unreacted", "reacted", "change_date", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    change_date: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="infra", server_default="infra")
    reacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class SafetyEvent(Base):
    __tablename__ = "safety_event"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    message_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    risk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    intervention: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DailyCheckin(Base, TimestampMixin):
    __tablename__ = "daily_checkin"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    morning_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evening_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mood_label: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class NotificationPlan(Base, TimestampMixin):
    __tablename__ = "notification_plan"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    message_template: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    morning_window_start: Mapped[time | None] = mapped_column(Time)
    morning_window_end: Mapped[time | None] = mapped_column(Time)
    evening_window_start: Mapped[time | None] = mapped_column(Time)
    evening_window_end: Mapped[time | None] = mapped_column(Time)
    next_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    random_seed: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class ProactiveMessage(Base, TimestampMixin):
    __tablename__ = "proactive_message"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    notification_plan_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class UserExportJob(Base):
    __tablename__ = "user_export_job"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    file_url: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    admin_user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ConversationFeedback(Base):
    __tablename__ = "conversation_feedback"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("conversation_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class UserBehaviorEvent(Base):
    __tablename__ = "user_behavior_event"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    session_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    message_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EmotionInsightReport(Base, TimestampMixin):
    __tablename__ = "emotion_insight_report"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="preview")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    preview_keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    preview_text: Mapped[str] = mapped_column(Text, nullable=False)
    full_report: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserMemoryEntitlement(Base, TimestampMixin):
    __tablename__ = "user_memory_entitlement"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    permanent_memory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class LangchainPgCollection(Base):
    __tablename__ = "langchain_pg_collection"

    uuid: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    cmetadata: Mapped[dict | None] = mapped_column(JSONB)


class LangchainPgEmbedding(Base):
    __tablename__ = "langchain_pg_embedding"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    collection_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    document: Mapped[str | None] = mapped_column(String)
    cmetadata: Mapped[dict | None] = mapped_column(JSONB)
