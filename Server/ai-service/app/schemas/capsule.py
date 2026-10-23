"""时间胶囊和秘密保险箱 HTTP 接口使用的请求模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ConditionalMessageType = Literal["time_capsule", "secret_vault"]
ConditionalMessageStatus = Literal["sealed", "queued", "delivered", "cancelled", "expired", "failed"]
ConditionType = Literal["time", "keyword", "project_status", "github_event", "passphrase"]


class CapsuleSchema(BaseModel):
    """允许客户端使用 camelCase，同时让服务层继续使用 snake_case。"""

    model_config = ConfigDict(populate_by_name=True)


class ConditionalMessageCreateRequest(CapsuleSchema):
    """显式创建一条密封消息及其唯一触发条件。

    ``condition`` 的字段由 ``conditionType`` 决定：

    - ``keyword``：``keyword`` 和可选 ``matchMode``（contains/exact）；
    - ``project_status``：``projectKey``、``expectedStatus``；
    - ``github_event``：``repository``、``event``，以及可选 action/conclusion/ref；
    - ``passphrase``：不在 condition 中保存口令，改用顶层 ``passphrase``；
    - ``time``：使用顶层 ``deliverAt``，便于数据库索引直接扫描。
    """

    message_type: ConditionalMessageType = Field(alias="messageType")
    condition_type: ConditionType = Field(alias="conditionType")
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=8000)
    deliver_at: datetime | None = Field(default=None, alias="deliverAt")
    condition: dict[str, Any] = Field(default_factory=dict)
    passphrase: str | None = Field(default=None, min_length=1, max_length=128)
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    client_request_id: str = Field(alias="clientRequestId", min_length=1, max_length=128)
    source_message_id: str | None = Field(default=None, alias="sourceMessageId", max_length=128)
    source_turn_id: str | None = Field(default=None, alias="sourceTurnId", max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "content", "client_request_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """拒绝只有空白的标题、正文和幂等键。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("source_message_id", "source_turn_id")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        """把可选文本两端空白去掉，空白值统一视作未提供。"""

        normalized = value.strip() if isinstance(value, str) else ""
        return normalized or None

    @field_validator("passphrase")
    @classmethod
    def validate_passphrase_without_changing_it(cls, value: str | None) -> str | None:
        """拒绝空白口令，但保留前后空格，使后续解锁执行精确比较。"""

        if value is not None and not value.strip():
            raise ValueError("passphrase 不能为空")
        return value

    @model_validator(mode="after")
    def validate_condition_shape(self):
        """在进入服务层前检查各触发类型的必填字段。"""

        if self.condition_type == "time" and self.deliver_at is None:
            raise ValueError("时间条件必须提供 deliverAt")
        if self.condition_type != "time" and self.deliver_at is not None:
            raise ValueError("只有时间条件可以提供 deliverAt")
        if self.condition_type == "keyword" and not clean_condition_text(self.condition, "keyword"):
            raise ValueError("关键词条件必须提供 condition.keyword")
        if self.condition_type == "project_status":
            if not clean_condition_text(self.condition, "projectKey"):
                raise ValueError("项目状态条件必须提供 condition.projectKey")
            if not clean_condition_text(self.condition, "expectedStatus"):
                raise ValueError("项目状态条件必须提供 condition.expectedStatus")
        if self.condition_type == "github_event":
            if not clean_condition_text(self.condition, "repository"):
                raise ValueError("GitHub 条件必须提供 condition.repository")
            if not clean_condition_text(self.condition, "event"):
                raise ValueError("GitHub 条件必须提供 condition.event")
        if self.condition_type == "passphrase" and not self.passphrase:
            raise ValueError("口令条件必须提供 passphrase")
        if self.condition_type != "passphrase" and self.passphrase:
            raise ValueError("只有口令条件可以提供 passphrase")
        return self


class ConditionalMessageCancelRequest(CapsuleSchema):
    """取消尚未投递消息时使用的幂等动作参数。"""

    client_action_id: str = Field(alias="clientActionId", min_length=1, max_length=128)
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)


class PassphraseUnlockRequest(CapsuleSchema):
    """使用口令尝试打开一条秘密保险箱。"""

    passphrase: str = Field(min_length=1, max_length=128)
    event_id: str = Field(alias="eventId", min_length=1, max_length=128)


class ProjectStatusEventRequest(CapsuleSchema):
    """由共同项目模块报告一次经过认证的项目状态变化。"""

    project_key: str = Field(alias="projectKey", min_length=1, max_length=160)
    status: str = Field(min_length=1, max_length=80)
    event_id: str = Field(alias="eventId", min_length=1, max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GitHubEventRequest(CapsuleSchema):
    """GitHub Webhook 适配层使用的规范化事件，不直接接受任意 webhook JSON。"""

    repository: str = Field(min_length=1, max_length=240)
    event: str = Field(min_length=1, max_length=80)
    delivery_id: str = Field(alias="deliveryId", min_length=1, max_length=128)
    action: str | None = Field(default=None, max_length=80)
    conclusion: str | None = Field(default=None, max_length=80)
    ref: str | None = Field(default=None, max_length=240)
    metadata: dict[str, Any] = Field(default_factory=dict)


def clean_condition_text(condition: dict[str, Any], key: str) -> str | None:
    """读取并规范化 condition 中的一个文本字段。"""

    value = condition.get(key)
    normalized = str(value).strip() if value is not None else ""
    return normalized or None
