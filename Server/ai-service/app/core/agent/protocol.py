from __future__ import annotations

import json
import re
from typing import Any


def content_event(content: str) -> dict[str, Any]:
    return {
        "event": "content",
        "type": "content",
        "content": content,
    }


def emotion_event(emotion_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": "emotion",
        "type": "emotion",
        "emotion": emotion_state,
    }


def memory_candidate_event(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": "memory_candidate",
        "type": "memory_candidate",
        "memory_candidate": candidate,
    }


def relationship_delta_event(delta: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": "relationship_delta",
        "type": "relationship_delta",
        "relationship_delta": delta,
    }


def error_event(message: str) -> dict[str, Any]:
    return {
        "event": "error",
        "type": "error",
        "message": message,
    }


def sse_data(event: dict[str, Any]) -> str:
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"data: {data}\n\n"


def derive_memory_candidate(message: str, emotion_state: dict[str, Any]) -> dict[str, Any]:
    text = (message or "").strip()
    if not text:
        return {
            "save": False,
            "confidence": 0.0,
            "title": None,
            "content": None,
            "reason": "empty_message",
            "signals": [],
        }

    signals: list[str] = []
    title = "用户信息"
    content = text
    confidence = 0.35

    pattern_rules = (
        ("name", r"(?:我叫|我是|我的名字是|my name is)\s*([\w\u4e00-\u9fff]{1,30})", "姓名"),
        ("birthday", r"(?:生日|出生|birth)", "生日或纪念日"),
        ("preference", r"(?:我喜欢|我爱吃|我讨厌|我不喜欢|favorite|prefer)", "偏好"),
        ("location", r"(?:我住在|我在.+(?:城市|上班|读书)|来自|live in)", "地点"),
        ("work_or_study", r"(?:我是.+(?:工程师|学生|老师|医生|设计师|产品|运营)|工作|上班|学校|专业)", "工作或学习"),
        ("plan", r"(?:计划|打算|准备|约定|承诺|明天|下周|下个月)", "计划或承诺"),
    )
    for signal, pattern, label in pattern_rules:
        if re.search(pattern, text, flags=re.IGNORECASE):
            signals.append(signal)
            title = label
            confidence += 0.15

    if emotion_state.get("support_needed") and emotion_state.get("intensity", 0) >= 0.65:
        signals.append("long_term_emotion")
        title = "情绪线索"
        confidence += 0.1

    save = bool(signals)
    return {
        "save": save,
        "confidence": round(min(confidence, 0.95) if save else 0.2, 2),
        "title": title if save else None,
        "content": content[:120] if save else None,
        "reason": "rule_signal_match" if save else "no_stable_long_term_signal",
        "signals": signals,
    }


def derive_relationship_delta(message: str, emotion_state: dict[str, Any]) -> dict[str, Any]:
    text = (message or "").lower()
    positive_keywords = ("爱你", "喜欢你", "想你", "抱抱", "亲亲", "陪我", "开心", "love", "miss you", "hug")
    vulnerable_keywords = ("难受", "委屈", "孤独", "害怕", "焦虑", "累", "想哭", "sad", "lonely", "anxious", "tired")
    conflict_keywords = ("冷淡", "不理我", "疏远", "吵架", "生气", "讨厌", "烦", "angry", "hate", "break up")

    positive = [keyword for keyword in positive_keywords if keyword in text]
    vulnerable = [keyword for keyword in vulnerable_keywords if keyword in text]
    conflict = [keyword for keyword in conflict_keywords if keyword in text]

    intimacy_delta = len(positive) * 3 + len(vulnerable) - len(conflict) * 4
    trust_delta = len(positive) * 2 + len(vulnerable) * 2 - len(conflict) * 3
    if emotion_state.get("support_needed"):
        trust_delta += 1

    intimacy_delta = max(-10, min(10, intimacy_delta))
    trust_delta = max(-10, min(10, trust_delta))
    if intimacy_delta > 0 or trust_delta > 0:
        label = "靠近"
    elif intimacy_delta < 0 or trust_delta < 0:
        label = "需要修复"
    else:
        label = "稳定"

    return {
        "intimacy_delta": intimacy_delta,
        "trust_delta": trust_delta,
        "label": label,
        "signals": {
            "positive": positive[:5],
            "vulnerable": vulnerable[:5],
            "conflict": conflict[:5],
        },
        "reason": "当前轮消息中的亲密、脆弱和冲突信号",
    }
