"""受控的 Aura 屏幕存在感状态。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


PresenceExpression = Literal["calm", "warm", "playful", "thinking", "soft", "concerned"]
PresenceMotion = Literal["idle", "acknowledge", "wave"]


class Live2DPresence(BaseModel):
    """主回复允许影响 Live2D 的极小、受限侧信道。"""

    model_config = ConfigDict(extra="ignore")

    expression: PresenceExpression = "calm"
    motion: PresenceMotion = "idle"
    intensity: int = Field(default=1, ge=0, le=2)


def resolve_live2d_presence(
    raw_presence: Any,
    turn_judgement: dict[str, Any] | None,
) -> dict[str, Any]:
    """合并模型侧信道与安全的回合级默认表情。"""

    fallback = default_live2d_presence(turn_judgement)
    if not isinstance(raw_presence, dict):
        return fallback.model_dump()

    try:
        return Live2DPresence.model_validate(raw_presence).model_dump()
    except ValidationError:
        return fallback.model_dump()


def default_live2d_presence(turn_judgement: dict[str, Any] | None) -> Live2DPresence:
    """当模型未给出合法侧信道时，按已验证回合判断给出克制的默认值。"""

    judgement = turn_judgement if isinstance(turn_judgement, dict) else {}
    response_mode = str(judgement.get("response_mode") or "natural_chat")
    emotion = judgement.get("emotion") if isinstance(judgement.get("emotion"), dict) else {}
    user_emotion = str(emotion.get("user_emotion") or "")

    if response_mode == "crisis_support":
        return Live2DPresence(expression="concerned", motion="acknowledge", intensity=1)
    if response_mode in {"lonely_support", "gentle_support", "relationship_repair"}:
        return Live2DPresence(expression="soft", motion="acknowledge", intensity=1)
    if response_mode == "warm_affection":
        return Live2DPresence(expression="warm", motion="acknowledge", intensity=1)
    if user_emotion in {"happy", "excited", "playful"}:
        return Live2DPresence(expression="playful", motion="wave", intensity=1)
    if user_emotion in {"confused", "thinking", "stressed"}:
        return Live2DPresence(expression="thinking", motion="idle", intensity=1)
    return Live2DPresence()
