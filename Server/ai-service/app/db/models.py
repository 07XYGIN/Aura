from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """项目所有 SQLAlchemy 声明式模型的基类。"""

    pass


class TimestampMixin:
    """为业务表提供由数据库维护的创建时间和更新时间字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Users(Base, TimestampMixin):
    """登录用户账号与基础资料表。"""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("sex IS NULL OR sex IN (0, 1)", name="chk_users_sex"),
        CheckConstraint("age IS NULL OR age BETWEEN 0 AND 150", name="chk_users_age"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    sex: Mapped[int | None] = mapped_column(SmallInteger)
    age: Mapped[int | None] = mapped_column(Integer)


class SelfChangelogEntry(Base, TimestampMixin):
    """Aura 自身功能变更记录，用于在对话中告知用户近期更新。"""

    __tablename__ = "self_changelog_entry"
    __table_args__ = (
        UniqueConstraint("change_date", "title", name="uq_self_changelog_entry_change_date_title"),
        Index("idx_self_changelog_unreacted", "reacted", "change_date", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    change_date: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="infra", server_default="infra")
    reacted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class ProactiveMessage(Base, TimestampMixin):
    """计划发送的主动消息及其调度、发送状态。"""

    __tablename__ = "proactive_message"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'skipped', 'failed', 'cancelled')",
            name="chk_proactive_message_status",
        ),
        UniqueConstraint("user_id", "dedupe_key", name="uq_proactive_message_user_dedupe"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str | None] = mapped_column(String(160))
    delivery_message_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default=lambda: str(uuid4()),
        server_default=text("(gen_random_uuid())::text"),
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class ConditionalMessage(Base, TimestampMixin):
    """保存需要在未来条件成立后才交给小乔的密封消息。

    业务表只负责记录消息正文、触发条件和状态；真正投递仍由
    :class:`ProactiveMessage` 可靠 outbox 完成。``sealed`` 表示条件尚未成立，
    ``queued`` 表示已经生成唯一 outbox，``delivered`` 只会在聊天历史写入成功
    后设置。这样调度进程重启或重复收到 GitHub 事件都不会重复打开同一条消息。
    """

    __tablename__ = "conditional_message"
    __table_args__ = (
        CheckConstraint(
            "message_type IN ('time_capsule', 'secret_vault')",
            name="chk_conditional_message_type",
        ),
        CheckConstraint(
            "condition_type IN ('time', 'keyword', 'project_status', 'github_event', 'passphrase')",
            name="chk_conditional_message_condition_type",
        ),
        CheckConstraint(
            "status IN ('sealed', 'queued', 'delivered', 'cancelled', 'expired', 'failed')",
            name="chk_conditional_message_status",
        ),
        CheckConstraint(
            "condition_type <> 'time' OR deliver_at IS NOT NULL",
            name="chk_conditional_message_time_requires_delivery",
        ),
        CheckConstraint("version >= 1", name="chk_conditional_message_version"),
        UniqueConstraint("user_id", "dedupe_key", name="uq_conditional_message_user_dedupe"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_type: Mapped[str] = mapped_column(String(24), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sealed", server_default="sealed")
    deliver_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    condition_json: Mapped[dict] = mapped_column("condition", JSONB, nullable=False, default=dict, server_default="{}")
    unlock_secret_hash: Mapped[str | None] = mapped_column(String(255))
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    outbox_message_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "proactive_message.id",
            ondelete="SET NULL",
            deferrable=True,
            initially="DEFERRED",
        ),
        unique=True,
    )
    source_message_id: Mapped[str | None] = mapped_column(String(128))
    source_turn_id: Mapped[str | None] = mapped_column(String(128))
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class ConditionalMessageEvent(Base):
    """记录一次条件评估事件，防止相同 Webhook 或客户端重试被重复消费。"""

    __tablename__ = "conditional_message_event"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('keyword', 'project_status', 'github_event', 'passphrase')",
            name="chk_conditional_message_event_type",
        ),
        CheckConstraint("matched_count >= 0", name="chk_conditional_message_event_matched_count"),
        UniqueConstraint(
            "user_id",
            "event_type",
            "event_id",
            name="uq_conditional_message_event_user_event",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict] = mapped_column("payload", JSONB, nullable=False, default=dict, server_default="{}")
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RelationshipThread(Base, TimestampMixin):
    """保存一条需要跨对话延续的关系线程及其当前权威状态。

    线程用于承载未完成事项、后续关心、冲突修复、承诺和共同项目任务。
    ``perspective`` 区分事实属于小乔、Aura 还是双方共同经历，
    ``world_layer`` 则防止现实、共同历史、想象、愿望与承诺相互混淆。
    业务更新必须递增 ``version``，并同时追加一条
    :class:`RelationshipThreadEvent`，从而兼顾快速读取当前状态与完整追溯。
    """

    __tablename__ = "relationship_thread"
    __table_args__ = (
        CheckConstraint(
            "thread_type IN ('open_item', 'follow_up', 'conflict', 'promise', 'project_task')",
            name="chk_relationship_thread_type",
        ),
        CheckConstraint(
            "perspective IN ('user', 'aura', 'shared')",
            name="chk_relationship_thread_perspective",
        ),
        CheckConstraint(
            "world_layer IN ('reality', 'shared_history', 'imagined', 'wish', 'promise')",
            name="chk_relationship_thread_world_layer",
        ),
        CheckConstraint(
            "status IN ('pending', 'followed_up', 'resolved', 'abandoned')",
            name="chk_relationship_thread_status",
        ),
        CheckConstraint("version >= 1", name="chk_relationship_thread_version"),
        UniqueConstraint("user_id", "source_key", name="uq_relationship_thread_user_source"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    thread_type: Mapped[str] = mapped_column(String(32), nullable=False)
    perspective: Mapped[str] = mapped_column(String(16), nullable=False)
    world_layer: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(String(128))
    source_turn_id: Mapped[str | None] = mapped_column(String(128))
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_followed_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class RelationshipThreadEvent(Base):
    """记录关系线程每次状态变化的不可变审计事件。

    ``sequence_no`` 在单条线程内严格递增，用于稳定重放；
    ``state_before`` 与 ``state_after`` 保存变更前后的业务快照。
    客户端发起的动作可以携带 ``client_action_id``，其线程内唯一约束
    保证网络重试不会重复解决、放弃或跟进同一事项。
    """

    __tablename__ = "relationship_thread_event"
    __table_args__ = (
        CheckConstraint("sequence_no >= 1", name="chk_relationship_thread_event_sequence"),
        CheckConstraint(
            "actor IN ('user', 'aura', 'system')",
            name="chk_relationship_thread_event_actor",
        ),
        CheckConstraint(
            "event_type IN ('created', 'updated', 'followed_up', 'resolved', 'abandoned')",
            name="chk_relationship_thread_event_type",
        ),
        UniqueConstraint(
            "thread_id",
            "sequence_no",
            name="uq_relationship_thread_event_sequence",
        ),
        UniqueConstraint(
            "thread_id",
            "client_action_id",
            name="uq_relationship_thread_event_client_action",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    thread_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("relationship_thread.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    state_before: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    state_after: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    source_message_id: Mapped[str | None] = mapped_column(String(128))
    client_action_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class RelationshipItem(Base, TimestampMixin):
    """保存稳定的共同关系物件、私人语言、Aura 立场和交互纠偏。"""

    __tablename__ = "relationship_item"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('shared_memory', 'nickname', 'running_joke', 'codeword', "
            "'ritual', 'shared_object', 'action_style', 'aura_stance', "
            "'interaction_rule', 'boundary')",
            name="chk_relationship_item_type",
        ),
        CheckConstraint(
            "perspective IN ('user', 'aura', 'shared')",
            name="chk_relationship_item_perspective",
        ),
        CheckConstraint(
            "world_layer IN ('reality', 'shared_history', 'imagined', 'wish', 'promise')",
            name="chk_relationship_item_world_layer",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive', 'superseded')",
            name="chk_relationship_item_status",
        ),
        CheckConstraint("use_count >= 0", name="chk_relationship_item_use_count"),
        CheckConstraint("cooldown_days BETWEEN 0 AND 3650", name="chk_relationship_item_cooldown"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="chk_relationship_item_confidence"),
        CheckConstraint("version >= 1", name="chk_relationship_item_version"),
        UniqueConstraint("user_id", "item_key", name="uq_relationship_item_user_key"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    perspective: Mapped[str] = mapped_column(String(16), nullable=False)
    world_layer: Mapped[str] = mapped_column(String(24), nullable=False)
    item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    usage_condition: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        default=1,
        server_default="1",
    )
    can_change: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    cooldown_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=14, server_default="14")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_message_id: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class RelationshipChapter(Base, TimestampMixin):
    """按时间顺序保存由真实重要事件形成的关系章节。"""

    __tablename__ = "relationship_chapter"
    __table_args__ = (
        CheckConstraint("sequence_no >= 1", name="chk_relationship_chapter_sequence"),
        CheckConstraint(
            "status IN ('current', 'closed')",
            name="chk_relationship_chapter_status",
        ),
        UniqueConstraint("user_id", "sequence_no", name="uq_relationship_chapter_user_sequence"),
        UniqueConstraint("user_id", "source_key", name="uq_relationship_chapter_user_source"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="current", server_default="current")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    representative_message_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class AuraDailyState(Base, TimestampMixin):
    """Aura 在一个本地自然日内保持一致的轻量设定生活状态。"""

    __tablename__ = "aura_daily_state"
    __table_args__ = (
        CheckConstraint(
            "energy IN ('rested', 'steady', 'low')",
            name="chk_aura_daily_state_energy",
        ),
        CheckConstraint(
            "mood IN ('calm', 'focused', 'playful', 'annoyed', 'tired', 'cozy')",
            name="chk_aura_daily_state_mood",
        ),
        CheckConstraint(
            "generated_by IN ('deterministic', 'model', 'user')",
            name="chk_aura_daily_state_generated_by",
        ),
        UniqueConstraint("user_id", "local_date", name="uq_aura_daily_state_user_date"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai")
    activity: Mapped[str] = mapped_column(Text, nullable=False)
    energy: Mapped[str] = mapped_column(String(16), nullable=False)
    mood: Mapped[str] = mapped_column(String(24), nullable=False)
    location: Mapped[str] = mapped_column(String(160), nullable=False)
    pet_event: Mapped[str | None] = mapped_column(Text)
    current_content: Mapped[str | None] = mapped_column(Text)
    daily_event: Mapped[str | None] = mapped_column(Text)
    generated_by: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="deterministic",
        server_default="deterministic",
    )
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class EmotionalAfterglow(Base, TimestampMixin):
    """保存会自然衰减、但不会在下一轮立刻消失的情绪余温。"""

    __tablename__ = "emotional_afterglow"
    __table_args__ = (
        CheckConstraint(
            "emotion IN ('happy', 'distressed', 'stressed', 'angry', 'lonely', 'tired', "
            "'affectionate', 'unsettled')",
            name="chk_emotional_afterglow_emotion",
        ),
        CheckConstraint(
            "interaction_mode IN ('natural', 'affection', 'repair')",
            name="chk_emotional_afterglow_interaction_mode",
        ),
        CheckConstraint(
            "intensity BETWEEN 0 AND 1",
            name="chk_emotional_afterglow_intensity",
        ),
        CheckConstraint("version >= 1", name="chk_emotional_afterglow_version"),
        UniqueConstraint("user_id", name="uq_emotional_afterglow_user"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    emotion: Mapped[str] = mapped_column(String(24), nullable=False)
    interaction_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    intensity: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    source_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class SharedScene(Base, TimestampMixin):
    """保存双方当前想象场景的位置、物件和有限状态机进度。"""

    __tablename__ = "shared_scene"
    __table_args__ = (
        CheckConstraint(
            "scene_type IN ('room', 'date', 'imagined')",
            name="chk_shared_scene_type",
        ),
        CheckConstraint(
            "world_layer IN ('imagined', 'wish')",
            name="chk_shared_scene_world_layer",
        ),
        CheckConstraint(
            "status IN ('active', 'closed')",
            name="chk_shared_scene_status",
        ),
        CheckConstraint("version >= 1", name="chk_shared_scene_version"),
        UniqueConstraint("user_id", "source_key", name="uq_shared_scene_user_source"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scene_type: Mapped[str] = mapped_column(String(16), nullable=False)
    world_layer: Mapped[str] = mapped_column(String(24), nullable=False, default="imagined", server_default="imagined")
    place: Mapped[str] = mapped_column(String(160), nullable=False)
    participants: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    objects: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    state_json: Mapped[dict] = mapped_column("state", JSONB, nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    source_key: Mapped[str] = mapped_column(String(160), nullable=False)
    source_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class AuraThoughtSeed(Base, TimestampMixin):
    """保存有真实来源、但未必需要展示或主动发送的 Aura 思绪候选。"""

    __tablename__ = "aura_thought_seed"
    __table_args__ = (
        CheckConstraint(
            "thought_type IN ('second_thought', 'offline_reflection', 'surprise', 'night_reflection')",
            name="chk_aura_thought_seed_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'queued', 'used', 'cancelled', 'expired')",
            name="chk_aura_thought_seed_status",
        ),
        CheckConstraint("relevance BETWEEN 0 AND 1", name="chk_aura_thought_seed_relevance"),
        UniqueConstraint("user_id", "dedupe_key", name="uq_aura_thought_seed_user_dedupe"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    thought_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    dedupe_key: Mapped[str] = mapped_column(String(160), nullable=False)
    relevance: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=1, server_default="1")
    visible_on_next_chat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    source_message_id: Mapped[str | None] = mapped_column(String(128))
    source_turn_id: Mapped[str | None] = mapped_column(String(128))
    eligible_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class AuraSleepCycle(Base, TimestampMixin):
    """记录一次每日关系与记忆整理，保证夜间维护可追溯且每天只运行一次。"""

    __tablename__ = "aura_sleep_cycle"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="chk_aura_sleep_cycle_status",
        ),
        CheckConstraint("consolidated_count >= 0", name="chk_aura_sleep_cycle_consolidated_count"),
        UniqueConstraint("user_id", "local_date", name="uq_aura_sleep_cycle_user_date"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing", server_default="processing")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reflection: Mapped[str] = mapped_column(Text, nullable=False)
    open_threads: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    avoid_topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    consolidated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class BashGameSession(Base, TimestampMixin):
    """一局巴什博弈的当前权威状态和并发版本。"""

    __tablename__ = "bash_game_session"
    __table_args__ = (
        CheckConstraint("initial_stones BETWEEN 5 AND 100", name="chk_bash_game_initial_stones"),
        CheckConstraint("max_take BETWEEN 1 AND 10 AND max_take < initial_stones", name="chk_bash_game_max_take"),
        CheckConstraint(
            "remaining_stones BETWEEN 0 AND initial_stones",
            name="chk_bash_game_remaining_stones",
        ),
        CheckConstraint("first_player IN ('user', 'aura')", name="chk_bash_game_first_player"),
        CheckConstraint(
            "current_player IS NULL OR current_player IN ('user', 'aura')",
            name="chk_bash_game_current_player",
        ),
        CheckConstraint(
            "difficulty IN ('serious', 'casual', 'teaching')",
            name="chk_bash_game_difficulty",
        ),
        CheckConstraint(
            "status IN ('active', 'finished', 'resigned')",
            name="chk_bash_game_status",
        ),
        CheckConstraint(
            "winner IS NULL OR winner IN ('user', 'aura')",
            name="chk_bash_game_winner",
        ),
        UniqueConstraint("user_id", "start_request_id", name="uq_bash_game_start_request"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    initial_stones: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=15, server_default="15")
    remaining_stones: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_take: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3, server_default="3")
    first_player: Mapped[str] = mapped_column(String(16), nullable=False)
    current_player: Mapped[str | None] = mapped_column(String(16))
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="serious", server_default="serious")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    winner: Mapped[str | None] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    start_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BashGameMove(Base):
    """巴什博弈不可变的单步行动事件。"""

    __tablename__ = "bash_game_move"
    __table_args__ = (
        CheckConstraint("turn_no >= 1", name="chk_bash_move_turn_no"),
        CheckConstraint("player IN ('user', 'aura')", name="chk_bash_move_player"),
        CheckConstraint("take_count >= 1", name="chk_bash_move_take_count"),
        CheckConstraint(
            "remaining_before - remaining_after = take_count AND remaining_after >= 0",
            name="chk_bash_move_remaining",
        ),
        CheckConstraint(
            "(player = 'user' AND client_move_id IS NOT NULL) OR "
            "(player = 'aura' AND client_move_id IS NULL)",
            name="chk_bash_move_client_id",
        ),
        UniqueConstraint("session_id", "turn_no", name="uq_bash_move_turn"),
        UniqueConstraint("session_id", "client_move_id", name="uq_bash_move_client_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bash_game_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_no: Mapped[int] = mapped_column(Integer, nullable=False)
    player: Mapped[str] = mapped_column(String(16), nullable=False)
    take_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    remaining_before: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    remaining_after: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    strategy: Mapped[str | None] = mapped_column(String(32))
    client_move_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CompanionPet(Base, TimestampMixin):
    """用户与 Aura 共同照顾的一只温和型陪伴宠物。"""

    __tablename__ = "companion_pet"
    __table_args__ = (
        CheckConstraint("species IN ('cat', 'dog', 'rabbit')", name="chk_companion_pet_species"),
        CheckConstraint(
            "personality IN ('gentle', 'playful', 'curious', 'quiet')",
            name="chk_companion_pet_personality",
        ),
        CheckConstraint(
            "growth_stage IN ('baby', 'young', 'adult')",
            name="chk_companion_pet_growth_stage",
        ),
        CheckConstraint("satiety BETWEEN 0 AND 100", name="chk_companion_pet_satiety"),
        CheckConstraint("energy BETWEEN 0 AND 100", name="chk_companion_pet_energy"),
        CheckConstraint("cleanliness BETWEEN 0 AND 100", name="chk_companion_pet_cleanliness"),
        CheckConstraint(
            "mood IN ('calm', 'content', 'playful', 'curious', 'sleepy')",
            name="chk_companion_pet_mood",
        ),
        CheckConstraint(
            "current_activity IN ('idle', 'eating', 'playing', 'grooming', 'bathing', 'cuddling', 'sleeping')",
            name="chk_companion_pet_activity",
        ),
        CheckConstraint("version >= 1", name="chk_companion_pet_version"),
        UniqueConstraint("user_id", name="uq_companion_pet_user"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    species: Mapped[str] = mapped_column(String(16), nullable=False)
    personality: Mapped[str] = mapped_column(String(16), nullable=False)
    growth_stage: Mapped[str] = mapped_column(String(16), nullable=False, default="baby", server_default="baby")
    satiety: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=80, server_default="80")
    energy: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=80, server_default="80")
    cleanliness: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=80, server_default="80")
    mood: Mapped[str] = mapped_column(String(24), nullable=False, default="calm", server_default="calm")
    current_activity: Mapped[str] = mapped_column(String(24), nullable=False, default="idle", server_default="idle")
    adopted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    mood_until_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activity_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")


class PetEvent(Base):
    """一次宠物领养、照顾、改名或成长的不可变事实事件。"""

    __tablename__ = "pet_event"
    __table_args__ = (
        CheckConstraint("actor IN ('user', 'aura', 'system')", name="chk_pet_event_actor"),
        CheckConstraint(
            "event_type IN ('adoption', 'action', 'rename', 'growth', 'system')",
            name="chk_pet_event_type",
        ),
        UniqueConstraint("pet_id", "client_action_id", name="uq_pet_event_client_action"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    pet_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("companion_pet.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    state_before: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    state_after: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    client_action_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LangchainPgCollection(Base):
    """LangChain PGVector 使用的向量集合元数据表。"""

    __tablename__ = "langchain_pg_collection"

    uuid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    cmetadata: Mapped[dict | None] = mapped_column(JSON)


class LangchainPgEmbedding(Base):
    """LangChain PGVector 的记忆文档、向量和业务元数据表。"""

    __tablename__ = "langchain_pg_embedding"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    collection_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("langchain_pg_collection.uuid", ondelete="CASCADE"),
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    document: Mapped[str | None] = mapped_column(String)
    cmetadata: Mapped[dict | None] = mapped_column(JSONB)


Index("idx_self_changelog_occurred_at", SelfChangelogEntry.occurred_at.desc())
Index(
    "idx_proactive_message_user_schedule",
    ProactiveMessage.user_id,
    ProactiveMessage.status,
    ProactiveMessage.scheduled_at,
)
Index(
    "idx_proactive_message_claim",
    ProactiveMessage.status,
    ProactiveMessage.scheduled_at,
    ProactiveMessage.claimed_until,
)
Index(
    "idx_conditional_message_time_due",
    ConditionalMessage.status,
    ConditionalMessage.deliver_at,
    postgresql_where=text("((condition_type)::text = 'time'::text)"),
)
Index(
    "idx_conditional_message_user_status",
    ConditionalMessage.user_id,
    ConditionalMessage.status,
    ConditionalMessage.created_at.desc(),
)
Index(
    "idx_conditional_message_event_user_time",
    ConditionalMessageEvent.user_id,
    ConditionalMessageEvent.occurred_at.desc(),
)
Index(
    "idx_relationship_thread_user_status_follow_up",
    RelationshipThread.user_id,
    RelationshipThread.status,
    RelationshipThread.follow_up_at,
)
Index(
    "idx_relationship_thread_event_thread_occurred",
    RelationshipThreadEvent.thread_id,
    RelationshipThreadEvent.occurred_at.desc(),
)
Index(
    "idx_relationship_item_user_type_status",
    RelationshipItem.user_id,
    RelationshipItem.item_type,
    RelationshipItem.status,
    RelationshipItem.updated_at.desc(),
)
Index(
    "uq_relationship_chapter_current_user",
    RelationshipChapter.user_id,
    unique=True,
    postgresql_where=text("((status)::text = 'current'::text)"),
)
Index(
    "idx_relationship_chapter_user_sequence",
    RelationshipChapter.user_id,
    RelationshipChapter.sequence_no.desc(),
)
Index(
    "idx_aura_daily_state_user_date",
    AuraDailyState.user_id,
    AuraDailyState.local_date.desc(),
)
Index(
    "idx_emotional_afterglow_user_expires",
    EmotionalAfterglow.user_id,
    EmotionalAfterglow.expires_at,
)
Index(
    "uq_shared_scene_active_user",
    SharedScene.user_id,
    unique=True,
    postgresql_where=text("((status)::text = 'active'::text)"),
)
Index(
    "idx_shared_scene_user_started",
    SharedScene.user_id,
    SharedScene.started_at.desc(),
)
Index(
    "idx_aura_thought_seed_status_eligible",
    AuraThoughtSeed.status,
    AuraThoughtSeed.eligible_at,
    AuraThoughtSeed.expires_at,
)
Index(
    "idx_aura_thought_seed_user_created",
    AuraThoughtSeed.user_id,
    AuraThoughtSeed.created_at.desc(),
)
Index(
    "idx_aura_sleep_cycle_user_date",
    AuraSleepCycle.user_id,
    AuraSleepCycle.local_date.desc(),
)
Index(
    "uq_bash_game_active_user",
    BashGameSession.user_id,
    unique=True,
    postgresql_where=text("((status)::text = 'active'::text)"),
)
Index(
    "idx_bash_game_user_created",
    BashGameSession.user_id,
    BashGameSession.created_at.desc(),
)
Index(
    "idx_bash_move_session_created",
    BashGameMove.session_id,
    BashGameMove.created_at,
)
Index(
    "idx_pet_event_pet_occurred",
    PetEvent.pet_id,
    PetEvent.occurred_at.desc(),
)
Index(
    "ix_cmetadata_gin",
    LangchainPgEmbedding.cmetadata,
    postgresql_using="gin",
    postgresql_ops={"cmetadata": "jsonb_path_ops"},
)
