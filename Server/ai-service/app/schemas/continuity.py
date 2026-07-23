"""关系连续性线程的 HTTP 请求模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ThreadType = Literal["open_item", "follow_up", "conflict", "promise", "project_task"]
ThreadPerspective = Literal["user", "aura", "shared"]
WorldLayer = Literal["reality", "shared_history", "imagined", "wish", "promise"]
ThreadStatus = Literal["pending", "followed_up", "resolved", "abandoned"]
ThreadAction = Literal["update", "follow_up", "resolve", "abandon"]


class ContinuitySchema(BaseModel):
    """连续性请求基类，同时接受 camelCase 和 snake_case 字段。"""

    model_config = ConfigDict(populate_by_name=True)


class RelationshipThreadCreateRequest(ContinuitySchema):
    """显式创建一条开放事项、承诺、冲突或项目线程。"""

    thread_type: ThreadType = Field(alias="threadType")
    perspective: ThreadPerspective = "shared"
    world_layer: WorldLayer = Field(default="reality", alias="worldLayer")
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=1200)
    follow_up_at: datetime | None = Field(default=None, alias="followUpAt")
    source_message_id: str | None = Field(default=None, alias="sourceMessageId", max_length=128)
    source_turn_id: str | None = Field(default=None, alias="sourceTurnId", max_length=128)
    client_request_id: str = Field(alias="clientRequestId", min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "summary", "client_request_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """去除幂等键和正文两端空白，并拒绝纯空白输入。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("source_message_id", "source_turn_id")
    @classmethod
    def strip_optional_source_id(cls, value: str | None) -> str | None:
        """规范可选来源 ID，空白值统一为 ``None``。"""

        normalized = value.strip() if isinstance(value, str) else ""
        return normalized or None


class RelationshipThreadTransitionRequest(ContinuitySchema):
    """对关系线程执行一次带版本和幂等键的状态变更。"""

    action: ThreadAction
    client_action_id: str = Field(alias="clientActionId", min_length=1, max_length=128)
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    summary: str | None = Field(default=None, min_length=1, max_length=1200)
    follow_up_at: datetime | None = Field(default=None, alias="followUpAt")
    source_message_id: str | None = Field(default=None, alias="sourceMessageId", max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("client_action_id")
    @classmethod
    def strip_client_action_id(cls, value: str) -> str:
        """规范状态动作幂等键，确保查询与写入使用同一个值。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("clientActionId 不能为空")
        return normalized

    @field_validator("title", "summary")
    @classmethod
    def strip_optional_business_text(cls, value: str | None) -> str | None:
        """可选正文一旦提供就必须包含非空白字符。"""

        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("线程文字不能为空")
        return normalized

    @field_validator("source_message_id")
    @classmethod
    def strip_transition_source_id(cls, value: str | None) -> str | None:
        """规范可选来源消息 ID。"""

        normalized = value.strip() if isinstance(value, str) else ""
        return normalized or None


class RelationshipThreadListFilter(ContinuitySchema):
    """服务层可复用的线程查询过滤条件。"""

    thread_type: ThreadType | None = Field(default=None, alias="threadType")
    status: ThreadStatus | None = None
    world_layer: WorldLayer | None = Field(default=None, alias="worldLayer")
