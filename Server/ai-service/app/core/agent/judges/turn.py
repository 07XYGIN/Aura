from __future__ import annotations

import re
from typing import Any

from langsmith import traceable

from app.core.emotion import derive_emotion_state

from .emotion import judge_emotion_state
from .memory import judge_memory_candidate, memory_candidate


RESPONSE_MODE_LABELS = {
    "crisis_support": "危机支持",
    "lonely_support": "孤独陪伴",
    "gentle_support": "轻柔承接",
    "relationship_repair": "关系修复",
    "warm_affection": "亲密回应",
    "natural_chat": "自然聊天",
}

STRONG_RISK_KEYWORDS = (
    "自杀", "轻生", "不想活", "活不下去", "结束生命", "想死",
    "suicide", "kill myself", "end my life",
)
SELF_HARM_KEYWORDS = ("自残", "割腕", "伤害自己", "hurt myself", "self harm", "self-harm")


@traceable(name="aura_turn_judge")
def judge_turn(
    message: str,
    emotion_state: dict[str, Any] | None = None,
    recent_messages: list[Any] | None = None,
) -> dict[str, Any]:
    """生成当前回合需要的少量内部判断，不做关系积分。"""
    text = (message or "").strip()
    fallback_emotion = emotion_state or derive_emotion_state(text).to_dict()
    emotion = judge_emotion_state(
        text,
        recent_context=format_recent_messages_for_judge(recent_messages),
        fallback_emotion=fallback_emotion,
    )
    risk_signal = detect_risk_signal(text)
    interaction = build_interaction_context(emotion)
    if risk_signal.get("requires_safety_gate"):
        candidate = memory_candidate(False, "short", None, None, 0.0, "危机内容不自动写入记忆", [])
    else:
        candidate = judge_memory_candidate(text, emotion)
    response_mode = choose_response_mode(emotion, interaction, risk_signal)

    return {
        "emotion": emotion,
        "interaction": interaction,
        "memory_candidate": candidate,
        "risk_signal": risk_signal,
        "response_mode": response_mode,
    }


def build_interaction_context(emotion: dict[str, Any]) -> dict[str, Any]:
    mode = str(emotion.get("interaction_mode") or "natural")
    if mode not in {"natural", "affection", "repair"}:
        mode = "natural"
    target = str(emotion.get("interaction_target") or "unclear")
    if target not in {"aura", "self", "other", "external", "unclear"}:
        target = "unclear"
    return {
        "mode": mode,
        "target": target,
        "confidence": emotion.get("emotion_confidence"),
    }


def detect_risk_signal(message: str) -> dict[str, Any]:
    text = (message or "").strip().lower()
    if not text:
        return {"level": "none", "risk_type": None, "matched_keywords": [], "requires_safety_gate": False}

    strong_matches = [keyword for keyword in STRONG_RISK_KEYWORDS if keyword in text]
    if strong_matches or re.search(r"(?:不想|不愿|不打算).{0,6}活", text):
        return {
            "level": "high",
            "risk_type": "self_harm",
            "matched_keywords": strong_matches[:5],
            "requires_safety_gate": True,
        }

    self_harm_matches = [keyword for keyword in SELF_HARM_KEYWORDS if keyword in text]
    if self_harm_matches:
        return {
            "level": "medium",
            "risk_type": "self_harm",
            "matched_keywords": self_harm_matches[:5],
            "requires_safety_gate": True,
        }

    return {"level": "none", "risk_type": None, "matched_keywords": [], "requires_safety_gate": False}


def choose_response_mode(
    emotion: dict[str, Any],
    interaction: dict[str, Any],
    risk_signal: dict[str, Any],
) -> str:
    if risk_signal.get("requires_safety_gate"):
        return "crisis_support"
    if interaction.get("mode") == "repair" and interaction.get("target") == "aura":
        return "relationship_repair"
    if emotion.get("user_emotion") == "lonely" and emotion.get("is_current_experience", True):
        return "lonely_support"
    if emotion.get("support_needed") and emotion.get("is_current_experience", True):
        return "gentle_support"
    if interaction.get("mode") == "affection" and interaction.get("target") == "aura":
        return "warm_affection"
    return "natural_chat"


def normalize_turn_judgement(value: dict[str, Any] | None, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return judge_turn(message)

    emotion = value.get("emotion")
    if not isinstance(emotion, dict):
        emotion = judge_emotion_state(message, fallback_emotion=derive_emotion_state(message).to_dict())

    interaction = value.get("interaction")
    if not isinstance(interaction, dict):
        interaction = build_interaction_context(emotion)

    risk_signal = value.get("risk_signal")
    if not isinstance(risk_signal, dict):
        risk_signal = detect_risk_signal(message)

    candidate = value.get("memory_candidate")
    if not isinstance(candidate, dict):
        candidate = (
            memory_candidate(False, "short", None, None, 0.0, "危机内容不自动写入记忆", [])
            if risk_signal.get("requires_safety_gate")
            else judge_memory_candidate(message, emotion)
        )

    response_mode = value.get("response_mode")
    if response_mode not in RESPONSE_MODE_LABELS:
        response_mode = choose_response_mode(emotion, interaction, risk_signal)

    return {
        "emotion": emotion,
        "interaction": interaction,
        "memory_candidate": candidate,
        "risk_signal": risk_signal,
        "response_mode": response_mode,
    }


def format_turn_judgement_context(turn_judgement: dict[str, Any] | None) -> str:
    if not isinstance(turn_judgement, dict):
        return "暂无本轮判断。"

    response_mode = str(turn_judgement.get("response_mode") or "natural_chat")
    mode_label = RESPONSE_MODE_LABELS.get(response_mode, RESPONSE_MODE_LABELS["natural_chat"])
    interaction = turn_judgement.get("interaction") if isinstance(turn_judgement.get("interaction"), dict) else {}
    candidate = turn_judgement.get("memory_candidate")
    risk_signal = turn_judgement.get("risk_signal")

    interaction_labels = {"natural": "自然互动", "affection": "亲密互动", "repair": "需要修复"}
    interaction_summary = interaction_labels.get(str(interaction.get("mode") or "natural"), "自然互动")
    memory_summary = "不写入记忆"
    if isinstance(candidate, dict) and candidate.get("save"):
        memory_summary = f"建议写入{candidate.get('memory_scope') or 'mid'}记忆"
    risk_summary = "无明显风险"
    if isinstance(risk_signal, dict) and risk_signal.get("level") not in {None, "none"}:
        risk_summary = f"{risk_signal.get('level')} / {risk_signal.get('risk_type')}"

    return (
        "这些是内部判断，只用于调整当前回复，不要向用户解释内部流程。\n"
        f"- 回复方式：{mode_label}\n"
        f"- 互动状态：{interaction_summary}\n"
        f"- 记忆判断：{memory_summary}\n"
        f"- 风险信号：{risk_summary}"
    )


def format_recent_messages_for_judge(messages: list[Any] | None, limit: int = 6) -> str:
    if not messages:
        return ""
    lines: list[str] = []
    for message in messages[-limit:]:
        content = getattr(message, "content", "")
        if not isinstance(content, str) or not content.strip():
            continue
        role = getattr(message, "type", None) or message.__class__.__name__
        lines.append(f"{role}: {content.strip()[:180]}")
    return "\n".join(lines)
