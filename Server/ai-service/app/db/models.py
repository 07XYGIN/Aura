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
    "ix_cmetadata_gin",
    LangchainPgEmbedding.cmetadata,
    postgresql_using="gin",
    postgresql_ops={"cmetadata": "jsonb_path_ops"},
)
