from __future__ import annotations

import re
from typing import Any

from langsmith import traceable

from app.core.emotion import derive_emotion_state

from .memory_judge import judge_memory_candidate
from .protocol import derive_relationship_delta


RESPONSE_MODE_LABELS = {
    "crisis_support": "危机支持",
    "lonely_support": "孤独陪伴",
    "emotional_support": "情绪承接",
    "relationship_repair": "关系修复",
    "warm_affection": "亲密承接",
    "natural_chat": "自然聊天",
}

STRONG_RISK_KEYWORDS = (
    "自杀",
    "轻生",
    "不想活",
    "活不下去",
    "结束生命",
    "想死",
    "suicide",
    "kill myself",
    "end my life",
)

SELF_HARM_KEYWORDS = (
    "自残",
    "割腕",
    "伤害自己",
    "hurt myself",
    "self harm",
    "self-harm",
)


@traceable(name="aura_turn_judge")
def judge_turn(message: str, emotion_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the per-turn structured judgment used by the graph and SSE events."""
    text = (message or "").strip()
    emotion = emotion_state or derive_emotion_state(text).to_dict()
    relationship_delta = derive_relationship_delta(text, emotion)
    memory_candidate = judge_memory_candidate(text, emotion)
    risk_signal = detect_risk_signal(text)
    response_mode = choose_response_mode(emotion, relationship_delta, risk_signal)

    return {
        "emotion": emotion,
        "relationship_delta": relationship_delta,
        "memory_candidate": memory_candidate,
        "risk_signal": risk_signal,
        "response_mode": response_mode,
    }


def detect_risk_signal(message: str) -> dict[str, Any]:
    text = (message or "").strip().lower()
    if not text:
        return {
            "level": "none",
            "risk_type": None,
            "matched_keywords": [],
            "requires_safety_gate": False,
        }

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

    return {
        "level": "none",
        "risk_type": None,
        "matched_keywords": [],
        "requires_safety_gate": False,
    }


def choose_response_mode(
    emotion: dict[str, Any],
    relationship_delta: dict[str, Any],
    risk_signal: dict[str, Any],
) -> str:
    if risk_signal.get("requires_safety_gate"):
        return "crisis_support"

    if emotion.get("user_emotion") == "lonely":
        return "lonely_support"

    if emotion.get("support_needed"):
        return "emotional_support"

    if relationship_delta.get("label") == "需要修复":
        return "relationship_repair"

    signals = relationship_delta.get("signals")
    if isinstance(signals, dict) and signals.get("positive"):
        return "warm_affection"

    return "natural_chat"


def normalize_turn_judgement(value: dict[str, Any] | None, message: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return judge_turn(message)

    emotion = value.get("emotion")
    if not isinstance(emotion, dict):
        emotion = derive_emotion_state(message).to_dict()

    relationship_delta = value.get("relationship_delta")
    if not isinstance(relationship_delta, dict):
        relationship_delta = derive_relationship_delta(message, emotion)

    memory_candidate = value.get("memory_candidate")
    if not isinstance(memory_candidate, dict):
        memory_candidate = judge_memory_candidate(message, emotion)

    risk_signal = value.get("risk_signal")
    if not isinstance(risk_signal, dict):
        risk_signal = detect_risk_signal(message)

    response_mode = value.get("response_mode")
    if response_mode not in RESPONSE_MODE_LABELS:
        response_mode = choose_response_mode(emotion, relationship_delta, risk_signal)

    return {
        "emotion": emotion,
        "relationship_delta": relationship_delta,
        "memory_candidate": memory_candidate,
        "risk_signal": risk_signal,
        "response_mode": response_mode,
    }


def format_turn_judgement_context(turn_judgement: dict[str, Any] | None) -> str:
    if not isinstance(turn_judgement, dict):
        return "暂无本轮判断。"

    response_mode = str(turn_judgement.get("response_mode") or "natural_chat")
    mode_label = RESPONSE_MODE_LABELS.get(response_mode, RESPONSE_MODE_LABELS["natural_chat"])
    relationship_delta = turn_judgement.get("relationship_delta")
    memory_candidate = turn_judgement.get("memory_candidate")
    risk_signal = turn_judgement.get("risk_signal")

    relationship_label = "稳定"
    if isinstance(relationship_delta, dict):
        relationship_label = str(relationship_delta.get("label") or relationship_label)

    memory_summary = "不写入记忆"
    if isinstance(memory_candidate, dict) and memory_candidate.get("save"):
        memory_scope = memory_candidate.get("memory_scope") or "mid"
        memory_summary = f"建议写入{memory_scope}记忆"

    risk_summary = "无明显风险"
    if isinstance(risk_signal, dict):
        risk_level = risk_signal.get("level") or "none"
        if risk_level != "none":
            risk_summary = f"{risk_level} / {risk_signal.get('risk_type')}"

    return (
        "这些是内部判断，用来调整语气和节奏，不要直接复述字段名给用户。\n"
        f"- 回复模式：{mode_label}\n"
        f"- 关系信号：{relationship_label}\n"
        f"- 记忆判断：{memory_summary}\n"
        f"- 风险信号：{risk_summary}"
    )
