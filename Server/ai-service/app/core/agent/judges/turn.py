"""汇总情绪、记忆和安全判断，生成当前回合的回复模式。"""

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
    relationship_context: str | None = None,
) -> dict[str, Any]:
    """生成当前回合的情绪、互动、记忆、安全和回复模式判断。

    不计算关系积分；结果只作为主模型的内部上下文。
    """
    text = (message or "").strip()
    fallback_emotion = emotion_state or derive_emotion_state(text).to_dict()
    recent_context = format_recent_messages_for_judge(recent_messages)
    emotion = judge_emotion_state(
        text,
        recent_context=recent_context,
        fallback_emotion=fallback_emotion,
    )
    risk_signal = detect_risk_signal(text)
    interaction = build_interaction_context(emotion)
    if risk_signal.get("requires_safety_gate"):
        candidate = memory_candidate(False, "short", None, None, 0.0, "危机内容不自动写入记忆", [])
    else:
        candidate = judge_memory_candidate(
            text,
            emotion,
            recent_context=recent_context,
            relationship_context=relationship_context,
        )
    response_mode = choose_response_mode(emotion, interaction, risk_signal)

    return {
        "emotion": emotion,
        "interaction": interaction,
        "memory_candidate": candidate,
        "risk_signal": risk_signal,
        "response_mode": response_mode,
    }


def build_interaction_context(emotion: dict[str, Any]) -> dict[str, Any]:
    """从情绪判断中提取并校验互动模式、对象和置信度。"""

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
    """用保守关键词规则识别需要安全优先处理的自伤风险。"""

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
    """按风险、关系修复、情绪支持和亲密信号选择回复模式。"""

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
    """补齐上游缺失或无效的回合判断字段。"""

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
    """把内部判断转换成主模型可读但不可对外复述的提示段。"""

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

    created_messages = turn_judgement.get("conditional_messages_created")
    conditional_summary = "本轮没有创建时间胶囊或秘密保险箱"
    if isinstance(created_messages, list) and created_messages:
        labels = []
        for item in created_messages[:2]:
            if not isinstance(item, dict):
                continue
            kind = "时间胶囊" if item.get("messageType") == "time_capsule" else "秘密保险箱"
            labels.append(f"{kind}《{item.get('title') or '未命名'}》")
        if labels:
            conditional_summary = "已由服务端密封保存：" + "、".join(labels)

    return (
        "这些是内部判断，只用于调整当前回复，不要向用户解释内部流程。\n"
        f"- 回复方式：{mode_label}\n"
        f"- 互动状态：{interaction_summary}\n"
        f"- 记忆判断：{memory_summary}\n"
        f"- 风险信号：{risk_summary}\n"
        f"- 条件消息：{conditional_summary}。只有显示已保存时才能确认创建成功；不要复述密封正文或口令"
    )


def format_recent_messages_for_judge(messages: list[Any] | None, limit: int = 6) -> str:
    """截取最近消息并压缩成情绪 judge 使用的角色文本。"""

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
