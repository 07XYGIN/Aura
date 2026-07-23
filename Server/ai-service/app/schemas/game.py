"""互动游戏 HTTP 请求模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GameSchema(BaseModel):
    """游戏请求模型基类，同时接受 snake_case 与 camelCase 字段名。"""

    model_config = ConfigDict(populate_by_name=True)


class BashGameStartRequest(GameSchema):
    """创建巴什博弈会话所需的规则、难度和幂等请求 ID。"""

    initial_stones: int = Field(default=15, alias="initialStones", ge=5, le=100)
    max_take: int = Field(default=3, alias="maxTake", ge=1, le=10)
    first_player: Literal["user", "aura", "random"] = Field(default="user", alias="firstPlayer")
    difficulty: Literal["serious", "casual", "teaching"] = "serious"
    start_request_id: str = Field(alias="startRequestId", min_length=1, max_length=128)


class BashGameMoveRequest(GameSchema):
    """提交一次用户取子行动所需的数量、版本和幂等请求 ID。"""

    take_count: int = Field(alias="takeCount", ge=1, le=10)
    expected_version: int = Field(alias="expectedVersion", ge=0)
    client_move_id: str = Field(alias="clientMoveId", min_length=1, max_length=128)


class BashGameResignRequest(GameSchema):
    """认输操作携带的乐观并发版本。"""

    expected_version: int = Field(alias="expectedVersion", ge=0)
