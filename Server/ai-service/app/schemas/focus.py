"""一起专注 API 使用的请求模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FocusStatus = Literal[
    "active",
    "paused",
    "check_in_queued",
    "awaiting_report",
    "completed",
    "cancelled",
    "expired",
]
FocusAction = Literal["pause", "resume", "cancel"]


class FocusSchema(BaseModel):
    """同时接受 camelCase 与 snake_case 的专注请求基类。"""

    model_config = ConfigDict(populate_by_name=True)


class FocusStartRequest(FocusSchema):
    """开始一次最长四小时的专注计时。"""

    activity: str = Field(min_length=1, max_length=240)
    duration_minutes: int = Field(alias="durationMinutes", ge=1, le=240)
    start_request_id: str = Field(alias="startRequestId", min_length=1, max_length=128)
    source_message_id: str | None = Field(default=None, alias="sourceMessageId", max_length=128)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("activity", "start_request_id")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        """清理活动和幂等键，并拒绝空白值。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized


class FocusActionRequest(FocusSchema):
    """暂停、恢复或取消专注的乐观并发请求。"""

    action: FocusAction
    client_action_id: str = Field(alias="clientActionId", min_length=1, max_length=128)
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)


class FocusProgressRequest(FocusSchema):
    """时间结束后记录用户汇报的结果和可选卡点。"""

    result_summary: str = Field(alias="resultSummary", min_length=1, max_length=1200)
    blocker: str | None = Field(default=None, max_length=1200)
    client_action_id: str = Field(alias="clientActionId", min_length=1, max_length=128)
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)

    @field_validator("result_summary", "client_action_id")
    @classmethod
    def strip_progress_text(cls, value: str) -> str:
        """结果和幂等键必须包含实际文字。"""

        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空")
        return normalized

    @field_validator("blocker")
    @classmethod
    def strip_optional_blocker(cls, value: str | None) -> str | None:
        """把空白卡点统一成未提供。"""

        normalized = value.strip() if isinstance(value, str) else ""
        return normalized or None

    @model_validator(mode="after")
    def keep_blocker_distinct(self):
        """避免把完整结果原样复制为卡点，减少后续提示词重复。"""

        if self.blocker == self.result_summary:
            self.blocker = None
        return self
