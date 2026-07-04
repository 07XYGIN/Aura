from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from app.core.config import emotion_judge_llm, ensure_deepseek_api_key
from app.core.emotion import DEFAULT_EMOTION, derive_emotion_state

EMOTION_JUDGE_SYSTEM_PROMPT = """
你是 Aura 的情绪语境判断器。只判断用户最新消息，不写回复。必须只返回一个 JSON 对象。

JSON 结构：
{
  "emotional_state": "neutral" | "positive" | "low" | "stressed" | "angry" | "lonely" | "tired",
  "is_current_experience": boolean,
  "confidence": number,
  "reason": string
}

判断重点：
- `is_current_experience=true` 表示用户正在经历当下情绪，需要 Aura 在语气上接住。
- `is_current_experience=false` 表示用户在回忆、复盘、描述习惯、转述过去，或讲一个事实背景。即使句子里有“累、烦、难受、加班”等词，也不要判成当下低落。
- “代码写累了就起来走走”“以前加班到很晚，现在好多了”“那时候挺累的”这类句子是陈述/回忆，通常是 `false`。
- “今天真的很累，感觉撑不下去了”“我现在烦死了”“刚刚突然很孤独”这类句子是当下体验，通常是 `true`。
- 不要因为一个孤立情绪词就放大判断；要结合时态、语气、是否在求陪伴/求安慰。
- `confidence` 取 0 到 1。拿不准时偏保守，避免过度安抚。
"""

EMOTION_PROFILES: dict[str, dict[str, Any]] = {
    "neutral": {
        "user_emotion": "neutral",
        "aura_mood": "warm",
        "valence": 0.1,
        "arousal": 0.35,
        "affection": 0.7,
        "guidance": "保持自然、温暖、像真实聊天一样。",
    },
    "positive": {
        "user_emotion": "happy",
        "aura_mood": "playful",
        "valence": 0.75,
        "arousal": 0.55,
        "affection": 0.85,
        "guidance": "分享用户的积极状态，语气可以更轻快一点。",
    },
    "low": {
        "user_emotion": "distressed",
        "aura_mood": "protective",
        "valence": -0.75,
        "arousal": 0.55,
        "affection": 0.9,
        "guidance": "如果这是当下体验，先承接情绪；如果只是回忆/陈述，正常聊天，不要过度安抚。",
    },
    "stressed": {
        "user_emotion": "stressed",
        "aura_mood": "steady",
        "valence": -0.55,
        "arousal": 0.7,
        "affection": 0.85,
        "guidance": "如果用户正在承受压力，先降低负担；如果是在复盘，正常接话即可。",
    },
    "angry": {
        "user_emotion": "angry",
        "aura_mood": "steady",
        "valence": -0.65,
        "arousal": 0.85,
        "affection": 0.8,
        "guidance": "如果这是当下愤怒，站在用户这边但不拱火；如果只是转述，别自动进入安抚。",
    },
    "lonely": {
        "user_emotion": "lonely",
        "aura_mood": "tender",
        "valence": -0.7,
        "arousal": 0.35,
        "affection": 1.0,
        "guidance": "如果用户当下孤独，给出亲近陪伴感；如果只是讲过去，轻轻接住即可。",
    },
    "tired": {
        "user_emotion": "tired",
        "aura_mood": "soothing",
        "valence": -0.4,
        "arousal": 0.2,
        "affection": 0.85,
        "guidance": "如果用户当下疲惫，回复低压力；如果是在描述习惯或回忆，不要显得黏人。",
    },
}

NEGATIVE_STATES = {"low", "stressed", "angry", "lonely", "tired"}
RETROSPECTIVE_HINTS = ("以前", "之前", "当时", "那时候", "后来", "回忆", "复盘", "过去", "曾经")
PRESENT_HINTS = ("现在", "今天", "刚刚", "此刻", "这会儿", "真的", "撑不下去", "受不了了")


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
        ensure_deepseek_api_key()
        response = emotion_judge_llm.invoke(
            [
                SystemMessage(content=EMOTION_JUDGE_SYSTEM_PROMPT.strip()),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
            ]
        )
        raw = parse_json_object(message_content_to_text(response.content))
        return normalize_emotion_judgement(raw, fallback, text)
    except Exception:
        logging.exception("Failed to judge emotion context with DeepSeek")
        return suppress_retrospective_false_positive(fallback, text)


def normalize_fallback_emotion(fallback_emotion: dict[str, Any] | None, text: str) -> dict[str, Any]:
    if isinstance(fallback_emotion, dict) and fallback_emotion:
        emotion = dict(fallback_emotion)
    else:
        emotion = derive_emotion_state(text).to_dict() if text else DEFAULT_EMOTION.to_dict()
    emotion.setdefault("is_current_experience", True)
    emotion.setdefault("emotion_confidence", 0.5)
    emotion.setdefault("emotion_reason", "keyword_fallback")
    emotion.setdefault("emotion_source", "keyword")
    return emotion


def normalize_emotion_judgement(raw: dict[str, Any], fallback: dict[str, Any], text: str) -> dict[str, Any]:
    emotional_state = clean_string(raw.get("emotional_state"), "neutral").lower()
    if emotional_state not in EMOTION_PROFILES:
        emotional_state = "neutral"

    confidence = clamp_float(raw.get("confidence"), 0.5)
    is_current = as_bool(raw.get("is_current_experience"))
    reason = clean_string(raw.get("reason"), "llm_emotion_judge")[:160]
    profile = EMOTION_PROFILES[emotional_state]
    support_needed = emotional_state in NEGATIVE_STATES and is_current and confidence >= 0.45

    if not is_current and emotional_state in NEGATIVE_STATES:
        aura_mood = "warm"
        guidance = (
            "这更像回忆、复盘或普通陈述，不要启动明显安抚模式；"
            "可以自然接话、轻轻吐槽或顺着话题继续。"
        )
        intensity = min(0.35, clamp_float(fallback.get("intensity"), 0.25))
    else:
        aura_mood = profile["aura_mood"]
        guidance = profile["guidance"]
        intensity = max(0.2, min(1.0, confidence))

    return {
        "user_emotion": profile["user_emotion"],
        "aura_mood": aura_mood,
        "valence": profile["valence"],
        "arousal": profile["arousal"],
        "intensity": round(intensity, 2),
        "affection": profile["affection"],
        "support_needed": support_needed,
        "matched_keywords": fallback.get("matched_keywords", [])[:5],
        "response_guidance": guidance,
        "emotional_state": emotional_state,
        "is_current_experience": is_current,
        "emotion_confidence": round(confidence, 2),
        "emotion_reason": reason,
        "emotion_source": "llm",
    }


def suppress_retrospective_false_positive(fallback: dict[str, Any], text: str) -> dict[str, Any]:
    if not fallback.get("support_needed"):
        return fallback

    normalized = text.lower()
    has_retrospective_hint = any(hint in normalized for hint in RETROSPECTIVE_HINTS)
    has_present_hint = any(hint in normalized for hint in PRESENT_HINTS)
    habitual_pattern = bool(re.search(r"(?:累了|烦了|困了|难受了).{0,8}(?:就|会|可以|起来|去)", text))
    if not has_present_hint and (has_retrospective_hint or habitual_pattern):
        emotion = dict(fallback)
        emotion["support_needed"] = False
        emotion["aura_mood"] = "warm"
        emotion["intensity"] = min(float(emotion.get("intensity") or 0.2), 0.35)
        emotion["is_current_experience"] = False
        emotion["emotion_confidence"] = 0.45
        emotion["emotion_reason"] = "retrospective_or_habitual_statement"
        emotion["emotion_source"] = "keyword_context_suppression"
        emotion["response_guidance"] = "这更像回忆、复盘或习惯描述，不要过度安抚，正常接话即可。"
        return emotion

    return fallback


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Emotion judge response must be a JSON object")
    return value


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
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
    if value is None:
        return default
    text = str(value).strip()
    return text or default
