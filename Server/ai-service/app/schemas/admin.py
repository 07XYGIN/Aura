from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminSchema(BaseModel):
    """管理端请求模型基类，允许同时使用字段名和别名传参。"""

    model_config = ConfigDict(populate_by_name=True)


class SelfUpdateCreateRequest(AdminSchema):
    """创建 Aura 自更新记录时接收的字段。"""

    occurred_at: datetime | None = None
    title: str = Field(min_length=1, max_length=160)
    detail: str | None = None
    category: str = Field(default="infra", max_length=64)
    metadata: Any = None


class SelfUpdatePatchRequest(AdminSchema):
    """部分修改 Aura 自更新记录时接收的可选字段。"""

    occurred_at: datetime | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    detail: str | None = None
    category: str | None = Field(default=None, max_length=64)
    reacted: bool | None = None
    metadata: Any = None


class MemoryMergeConfirmRequest(AdminSchema):
    """人工确认合并多条记忆时提交的来源键和合并结果。"""

    memory_keys: list[str] = Field(alias="memoryKeys", min_length=2)
    merged_title: str = Field(alias="mergedTitle", min_length=1, max_length=80)
    merged_content: str = Field(alias="mergedContent", min_length=1, max_length=320)
    reason: str | None = Field(default=None, max_length=160)
