from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class SelfUpdateCreateRequest(AdminSchema):
    occurred_at: datetime | None = None
    title: str = Field(min_length=1, max_length=160)
    detail: str | None = None
    category: str = Field(default="infra", max_length=64)
    metadata: Any = None


class SelfUpdatePatchRequest(AdminSchema):
    occurred_at: datetime | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    detail: str | None = None
    category: str | None = Field(default=None, max_length=64)
    reacted: bool | None = None
    metadata: Any = None
