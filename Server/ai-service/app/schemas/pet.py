"""共同宠物 HTTP 请求模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PetSchema(BaseModel):
    """宠物请求模型基类，同时接受 snake_case 和 camelCase 字段名。"""

    model_config = ConfigDict(populate_by_name=True)


class PetAdoptRequest(PetSchema):
    """领养共同宠物时提交的身份、性格和幂等请求 ID。"""

    name: str = Field(min_length=1, max_length=32)
    species: Literal["cat", "dog", "rabbit"] = "cat"
    personality: Literal["gentle", "playful", "curious", "quiet"] = "gentle"
    adoption_request_id: str = Field(alias="adoptionRequestId", min_length=1, max_length=128)


class PetActionRequest(PetSchema):
    """执行一次确定性宠物照顾动作的请求。"""

    action: Literal["feed", "play", "groom", "bathe", "pet", "sleep"]
    client_action_id: str = Field(alias="clientActionId", min_length=1, max_length=128)
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)


class PetRenameRequest(PetSchema):
    """修改宠物名字时提交的新名字、版本和幂等请求 ID。"""

    name: str = Field(min_length=1, max_length=32)
    client_action_id: str = Field(alias="clientActionId", min_length=1, max_length=128)
    expected_version: int | None = Field(default=None, alias="expectedVersion", ge=1)
