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
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
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
    "ix_cmetadata_gin",
    LangchainPgEmbedding.cmetadata,
    postgresql_using="gin",
    postgresql_ops={"cmetadata": "jsonb_path_ops"},
)
