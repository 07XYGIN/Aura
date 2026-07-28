"""把用户对单条回复的纠偏转为可审计的互动规则。"""

from __future__ import annotations

import hashlib
from typing import Literal

from app.core.continuity.knowledge import capture_relationship_knowledge_sync


ReplyFeedbackCategory = Literal[
    "helpful",
    "too_long",
    "too_preachy",
    "too_clingy",
    "too_many_questions",
    "wrong_context",
]

FEEDBACK_RULES: dict[ReplyFeedbackCategory, tuple[str, str]] = {
    "helpful": (
        "回复偏好：自然直接",
        "这类自然、直接、克制的回应更贴近用户偏好；延续这种风格，不要为了显得周到而过度展开。",
    ),
    "too_long": (
        "回复偏好：更短",
        "除非用户明确要方案、解释或深入讨论，否则优先用一两句接住当下，不要把普通聊天写成长段分析。",
    ),
    "too_preachy": (
        "回复偏好：少说教",
        "用户日常表达或低落时先自然回应，不要自动纠正、教育、安排任务、灌鸡汤或给出正确做法。",
    ),
    "too_clingy": (
        "回复偏好：亲密但克制",
        "亲密表达保持自然和有限，不要制造依赖、占有、反复撒娇或要求用户安抚 Aura。",
    ),
    "too_many_questions": (
        "回复偏好：少追问",
        "默认不要追问；只有缺少关键信息且用户明确寻求帮助时，最多问一个必要问题。",
    ),
    "wrong_context": (
        "回复偏好：不编造上下文",
        "只依据当前对话、已确认记忆、工具结果和真实视觉输入；不要杜撰用户习惯、Aura 日常或共同经历。",
    ),
}


def record_reply_feedback(
    user_id: str,
    message_id: str,
    category: ReplyFeedbackCategory,
) -> bool:
    """用稳定来源键保存一条用户明确确认的互动规则。"""

    title, content = FEEDBACK_RULES[category]
    source_key = hashlib.sha256(f"{message_id}:{category}".encode("utf-8")).hexdigest()[:32]
    changed = capture_relationship_knowledge_sync(
        user_id,
        [
            {
                "operation": "upsert",
                "item_key": f"reply_feedback:{category}",
                "item_type": "interaction_rule",
                "perspective": "user",
                "world_layer": "reality",
                "title": title,
                "content": content,
                "usage_condition": "用户对 Aura 回复的明确反馈。",
                "confidence": 1.0,
                "can_change": True,
                "cooldown_days": 0,
                "metadata": {"source": "reply_feedback", "category": category},
            }
        ],
        None,
        source_message_id=f"feedback-{source_key}",
        source_turn_id=None,
    )
    return changed > 0
