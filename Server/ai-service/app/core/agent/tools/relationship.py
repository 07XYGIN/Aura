from __future__ import annotations

from langchain_core.tools import tool

from .logging_utils import log_tool


def _clamp(value: int, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, value))


@tool
@log_tool
def get_relationship_status(user_message: str = "") -> dict:
    """估算 Aura 与当前用户的关系状态、亲密度和回复建议。"""
    text = (user_message or "").lower()
    score = 74

    positive_keywords = (
        "爱你",
        "喜欢你",
        "想你",
        "抱抱",
        "亲亲",
        "陪我",
        "开心",
        "love",
        "miss you",
        "hug",
    )
    vulnerable_keywords = (
        "难受",
        "委屈",
        "孤独",
        "害怕",
        "焦虑",
        "累",
        "想哭",
        "sad",
        "lonely",
        "anxious",
        "tired",
    )
    distance_keywords = (
        "冷淡",
        "不理我",
        "疏远",
        "吵架",
        "生气",
        "讨厌",
        "烦",
        "break up",
        "angry",
    )

    score += sum(6 for keyword in positive_keywords if keyword in text)
    score += sum(4 for keyword in vulnerable_keywords if keyword in text)
    score -= sum(7 for keyword in distance_keywords if keyword in text)

    intimacy = _clamp(score)
    if intimacy >= 85:
        status = "稳定亲密"
        tone = "可以更自然地表达喜欢和依恋，同时保持轻松。"
    elif intimacy >= 65:
        status = "温暖靠近"
        tone = "适合温柔回应、确认在乎，并主动给一点陪伴感。"
    elif intimacy >= 45:
        status = "需要安抚"
        tone = "先承接情绪，再慢慢解释或修复，不要急着讲道理。"
    else:
        status = "关系紧绷"
        tone = "降低姿态，先道歉或确认对方感受，给出明确的修复动作。"

    return {
        "status": status,
        "intimacy_score": intimacy,
        "closeness_label": f"{intimacy}/100",
        "suggested_tone": tone,
        "basis": "根据当前消息中的亲密、脆弱和冲突信号做出的规则估算。",
    }
