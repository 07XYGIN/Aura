from __future__ import annotations

import json
import re
from typing import Any, Literal

MemoryScope = Literal["short", "mid", "long"]


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


def memory_reference_event(query: str | None = None) -> dict[str, Any]:
    return {
        "event": "memory_reference",
        "type": "memory_reference",
        "memory_reference": {
            "source": "search_memory_tool",
            "query": query,
        },
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
    from .memory_judge import judge_memory_candidate

    return judge_memory_candidate(message, emotion_state)

    text = (message or "").strip()
    if not text:
        return _memory_candidate(False, "short", None, None, 0.0, "empty_message", [])

    lower_text = text.lower()
    long_signals: list[str] = []
    mid_signals: list[str] = []
    title = "用户信息"

    long_rules = (
        ("name", r"(?:我叫|我的名字是|叫我|my name is)\s*([\w\u4e00-\u9fff·-]{1,30})", "称呼偏好"),
        ("birthday", r"(?:我的)?(?:生日|出生日期|纪念日|birthday)", "重要日期"),
        ("preference", r"(?:我(?:很)?喜欢|我(?:很)?爱|我偏好|我不喜欢|我讨厌|favorite|prefer)", "稳定偏好"),
        ("location", r"(?:我住在|我在.+(?:生活|上班|读书)|我来自|live in)", "常驻地点"),
        ("work_or_study", r"(?:我是.+(?:工程师|学生|老师|医生|设计师|产品|运营)|我的工作|我的专业|我在.+上班|我在.+读书)", "身份与工作学习"),
        ("long_goal", r"(?:长期目标|今年目标|未来想|一直想|打算长期|career goal)", "长期目标"),
        ("relationship_node", r"(?:我们的纪念日|第一次.*(?:见面|聊天|约定)|我希望你以后记得)", "关系节点"),
    )
    for signal, pattern, label in long_rules:
        if re.search(pattern, text, flags=re.IGNORECASE):
            long_signals.append(signal)
            title = label

    mid_rules = (
        ("near_plan", r"(?:今天|明天|后天|这周|本周|下周|最近|今晚).{0,30}(?:计划|准备|打算|要去|要做|面试|考试|项目|ddl|deadline|简历)"),
        ("active_project", r"(?:项目|面试|考试|简历|论文|工作).{0,40}(?:卡住|推进|准备|复盘|截止|压力|焦虑|担心)"),
        ("temporary_emotion", r"(?:最近|这几天|今天).{0,40}(?:难受|焦虑|很累|失眠|压力|委屈|孤独)"),
    )
    for signal, pattern in mid_rules:
        if re.search(pattern, text, flags=re.IGNORECASE):
            mid_signals.append(signal)

    tool_or_small_talk = (
        "天气" in text
        or "几点" in text
        or "现在时间" in text
        or lower_text in {"hi", "hello", "ping"}
        or len(text) <= 6
    )

    if long_signals:
        confidence = min(0.95, 0.62 + 0.08 * len(long_signals))
        return _memory_candidate(
            True,
            "long",
            title,
            text[:160],
            confidence,
            "stable_long_term_signal",
            long_signals,
        )

    if mid_signals and not tool_or_small_talk:
        confidence = min(0.82, 0.48 + 0.08 * len(mid_signals))
        return _memory_candidate(
            True,
            "mid",
            "近期线索",
            text[:160],
            confidence,
            "temporary_context_signal",
            mid_signals,
        )

    if emotion_state.get("support_needed") and emotion_state.get("intensity", 0) >= 0.72 and len(text) >= 12:
        return _memory_candidate(
            True,
            "mid",
            "近期情绪线索",
            text[:160],
            0.54,
            "recent_emotional_context",
            ["temporary_emotion"],
        )

    return _memory_candidate(False, "short", None, None, 0.2, "short_term_chat_only", [])


def _memory_candidate(
    save: bool,
    memory_scope: MemoryScope,
    title: str | None,
    content: str | None,
    confidence: float,
    reason: str,
    signals: list[str],
) -> dict[str, Any]:
    return {
        "save": save,
        "memory_scope": memory_scope,
        "title": title,
        "content": content,
        "confidence": round(confidence, 2),
        "reason": reason,
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
