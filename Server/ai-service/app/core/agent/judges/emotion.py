from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.core.config import emotion_judge_llm
from app.core.emotion import DEFAULT_EMOTION, derive_emotion_state


EMOTION_JUDGE_SYSTEM_PROMPT = """
你是 Aura 的对话语境判断器，只分析用户最新消息，不代替 Aura 回复。
必须只返回一个 JSON 对象：

{
  "emotional_state": "neutral" | "positive" | "low" | "stressed" | "angry" | "lonely" | "tired",
  "is_current_experience": boolean,
  "interaction_mode": "natural" | "affection" | "repair",
  "interaction_target": "aura" | "self" | "other" | "external" | "unclear",
  "confidence": number,
  "reason": string
}

判断原则：
- 不要根据单个“累、烦、讨厌、想你”直接下结论，结合对象、时态和上下文。
- 回忆、复盘、习惯描述通常不是正在发生的情绪。
- `repair` 只用于用户明确在批评 Aura、表达双方矛盾、失望、道歉或要求修复关系。
- 用户抱怨工作、天气、游戏或其他人时，不能判成与 Aura 的关系冲突。
- `affection` 用于明确指向 Aura 的喜欢、想念、拥抱、撒娇等亲密互动；它不是情绪疾病，也不代表关系积分变化。
- 普通聊天一律优先判为 `natural`，拿不准时保守处理。
- confidence 取 0 到 1。
"""

EMOTION_PROFILES: dict[str, dict[str, Any]] = {
    "neutral": {"user_emotion": "neutral", "aura_mood": "natural", "guidance": "自然接话，不主动分析情绪。"},
    "positive": {"user_emotion": "happy", "aura_mood": "playful", "guidance": "顺着具体事情一起开心。"},
    "low": {"user_emotion": "distressed", "aura_mood": "steady", "guidance": "如果是当下感受，先接住；如果只是回忆，正常聊天。"},
    "stressed": {"user_emotion": "stressed", "aura_mood": "steady", "guidance": "降低负担，先听清压力来自哪里。"},
    "angry": {"user_emotion": "angry", "aura_mood": "steady", "guidance": "先确认生气的对象和原因，不自动进入关系修复。"},
    "lonely": {"user_emotion": "lonely", "aura_mood": "close", "guidance": "自然陪伴，不把孤独变成依赖或说教。"},
    "tired": {"user_emotion": "tired", "aura_mood": "quiet", "guidance": "回复简短低负担，不自动给休息清单。"},
}

NEGATIVE_STATES = {"low", "stressed", "angry", "lonely", "tired"}
INTERACTION_MODES = {"natural", "affection", "repair"}
INTERACTION_TARGETS = {"aura", "self", "other", "external", "unclear"}
RETROSPECTIVE_HINTS = ("以前", "之前", "当时", "那时候", "后来", "回忆", "复盘", "过去", "曾经")
PRESENT_HINTS = ("现在", "今天", "刚刚", "此刻", "这会儿", "真的", "撑不下去", "受不了了")
AFFECTION_HINTS = ("爱你", "喜欢你", "想你", "抱抱", "亲亲", "陪我", "miss you", "love you", "hug")


@traceable(name="aura_emotion_judge")
def judge_emotion_state(
    message: str,
    recent_context: str | None = None,
    fallback_emotion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = (message or "").strip()
    fallback = normalize_fallback_emotion(fallback_emotion, text)
    if not text:
        return fallback

    payload = {
        "latest_user_message": text,
        "recent_context": recent_context or "",
        "keyword_fallback": fallback,
    }
    try:
        response = emotion_judge_llm.invoke(
            [
                SystemMessage(content=EMOTION_JUDGE_SYSTEM_PROMPT.strip()),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ]
        )
        raw = parse_json_object(message_content_to_text(response.content))
        return normalize_emotion_judgement(raw, fallback, text)
    except Exception:
        logging.exception("情绪语境判断失败，使用保守回退结果")
        return suppress_retrospective_false_positive(fallback, text)


def normalize_fallback_emotion(fallback_emotion: dict[str, Any] | None, text: str) -> dict[str, Any]:
    emotion = dict(fallback_emotion) if isinstance(fallback_emotion, dict) and fallback_emotion else (
        derive_emotion_state(text).to_dict() if text else DEFAULT_EMOTION.to_dict()
    )
    emotion.setdefault("is_current_experience", True)
    emotion.setdefault("emotion_confidence", 0.45)
    emotion.setdefault("emotion_reason", "关键词保守判断")
    emotion.setdefault("emotion_source", "keyword")
    emotion.setdefault("interaction_mode", infer_interaction_mode(text))
    emotion.setdefault("interaction_target", "aura" if emotion["interaction_mode"] != "natural" else "unclear")
    return emotion


def normalize_emotion_judgement(raw: dict[str, Any], fallback: dict[str, Any], text: str) -> dict[str, Any]:
    emotional_state = clean_string(raw.get("emotional_state"), "neutral").lower()
    if emotional_state not in EMOTION_PROFILES:
        emotional_state = "neutral"

    confidence = clamp_float(raw.get("confidence"), 0.5)
    is_current = as_bool(raw.get("is_current_experience"))
    interaction_mode = clean_string(raw.get("interaction_mode"), infer_interaction_mode(text)).lower()
    if interaction_mode not in INTERACTION_MODES:
        interaction_mode = infer_interaction_mode(text)
    interaction_target = clean_string(raw.get("interaction_target"), "unclear").lower()
    if interaction_target not in INTERACTION_TARGETS:
        interaction_target = "unclear"
    if interaction_mode in {"affection", "repair"} and interaction_target == "unclear":
        interaction_target = "aura"

    profile = EMOTION_PROFILES[emotional_state]
    support_needed = emotional_state in NEGATIVE_STATES and is_current and confidence >= 0.45
    aura_mood = profile["aura_mood"] if is_current else "natural"
    guidance = profile["guidance"] if is_current else "这是回忆、复盘或普通陈述，正常接话，不要主动安慰。"

    return {
        "user_emotion": profile["user_emotion"],
        "aura_mood": aura_mood,
        "support_needed": support_needed,
        "matched_keywords": fallback.get("matched_keywords", [])[:5],
        "response_guidance": guidance,
        "emotional_state": emotional_state,
        "is_current_experience": is_current,
        "emotion_confidence": round(confidence, 2),
        "emotion_reason": clean_string(raw.get("reason"), "LLM 语境判断")[:160],
        "emotion_source": "llm",
        "interaction_mode": interaction_mode,
        "interaction_target": interaction_target,
    }


def suppress_retrospective_false_positive(fallback: dict[str, Any], text: str) -> dict[str, Any]:
    emotion = dict(fallback)
    normalized = text.lower()
    has_retrospective_hint = any(hint in normalized for hint in RETROSPECTIVE_HINTS)
    has_present_hint = any(hint in normalized for hint in PRESENT_HINTS)
    habitual_pattern = bool(re.search(r"(?:累了|烦了|困了|难受了).{0,8}(?:就|会|可以|起来|去)", text))
    if emotion.get("support_needed") and not has_present_hint and (has_retrospective_hint or habitual_pattern):
        emotion["support_needed"] = False
        emotion["aura_mood"] = "natural"
        emotion["is_current_experience"] = False
        emotion["emotion_confidence"] = 0.45
        emotion["emotion_reason"] = "回忆或习惯描述"
        emotion["emotion_source"] = "keyword_context_suppression"
        emotion["response_guidance"] = "正常接话，不要主动安慰。"
    return emotion


def infer_interaction_mode(text: str) -> str:
    normalized = (text or "").lower()
    if any(hint in normalized for hint in AFFECTION_HINTS):
        return "affection"
    direct_to_aura = bool(re.search(r"(?:你|aura).{0,12}(?:让我|总是|刚才|不该|失望|生气|讨厌|难受|不舒服)", normalized))
    direct_from_user = bool(re.search(r"(?:我对你|我不想理你|我讨厌你|我在生你的气)", normalized))
    if direct_to_aura or direct_from_user:
        return "repair"
    return "natural"


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("情绪判断结果必须是 JSON 对象")
    return value


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content).strip()


def as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def clamp_float(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


def clean_string(value: Any, default: str) -> str:
    text = str(value).strip() if value is not None else ""
    return text or default
