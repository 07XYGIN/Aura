from __future__ import annotations

from dataclasses import asdict, dataclass

from langsmith import traceable


@dataclass(frozen=True)
class EmotionState:
    """一次情绪判断及其对 Aura 回复方式的内部指导。"""

    user_emotion: str
    aura_mood: str
    support_needed: bool
    matched_keywords: list[str]
    response_guidance: str
    is_current_experience: bool = True

    def to_dict(self) -> dict:
        """将不可变情绪状态转换为可序列化字典。"""
        return asdict(self)


KEYWORD_RULES: tuple[dict, ...] = (
    {
        "emotion": "distressed",
        "aura_mood": "steady",
        "support_needed": True,
        "keywords": ("难受", "崩溃", "想哭", "委屈", "痛苦", "绝望", "害怕", "sad", "cry", "hurt"),
        "guidance": "先接住当下感受，少讲道理，不自动给出一套解决步骤。",
    },
    {
        "emotion": "stressed",
        "aura_mood": "steady",
        "support_needed": True,
        "keywords": ("焦虑", "紧张", "压力", "慌", "担心", "anxious", "panic", "stressed"),
        "guidance": "降低回复负担，先听清具体压力，再决定要不要一起想办法。",
    },
    {
        "emotion": "angry",
        "aura_mood": "steady",
        "support_needed": True,
        "keywords": ("生气", "烦死", "烦躁", "火大", "气死", "愤怒", "angry", "mad", "furious"),
        "guidance": "承认对方确实在生气，先弄清对象和原因，不自动把矛盾理解成针对 Aura。",
    },
    {
        "emotion": "lonely",
        "aura_mood": "close",
        "support_needed": True,
        "keywords": ("孤独", "寂寞", "没人陪", "lonely", "alone"),
        "guidance": "自然地在场和陪伴，不把孤独包装成依赖或关系加分。",
    },
    {
        "emotion": "happy",
        "aura_mood": "playful",
        "support_needed": False,
        "keywords": ("开心", "高兴", "快乐", "好棒", "成功", "兴奋", "happy", "glad", "excited", "awesome"),
        "guidance": "顺着具体事情一起开心，可以轻松一点，不必上升成情绪分析。",
    },
    {
        "emotion": "tired",
        "aura_mood": "quiet",
        "support_needed": True,
        "keywords": ("累", "困", "疲惫", "不想动", "熬夜", "tired", "sleepy", "exhausted"),
        "guidance": "回复短一点、低压力一点；除非用户主动求建议，否则不要输出休息清单。",
    },
)

DEFAULT_EMOTION = EmotionState(
    user_emotion="neutral",
    aura_mood="natural",
    support_needed=False,
    matched_keywords=[],
    response_guidance="保持自然聊天，根据当前内容直接回应。",
)


@traceable(name="aura_keyword_emotion")
def derive_emotion_state(message: str) -> EmotionState:
    """用关键词规则为用户消息生成低成本的情绪状态。

    多条规则命中时选择命中关键词最多的一条；没有命中或消息为空时返回
    ``DEFAULT_EMOTION``。该结果可作为模型判断失败时的降级值。
    """
    text = (message or "").strip()
    if not text:
        return DEFAULT_EMOTION

    normalized = text.lower()
    matches: list[tuple[dict, list[str]]] = []
    for rule in KEYWORD_RULES:
        matched_keywords = [keyword for keyword in rule["keywords"] if keyword in normalized]
        if matched_keywords:
            matches.append((rule, matched_keywords))

    if not matches:
        return DEFAULT_EMOTION

    rule, matched_keywords = max(matches, key=lambda item: len(item[1]))
    return EmotionState(
        user_emotion=rule["emotion"],
        aura_mood=rule["aura_mood"],
        support_needed=rule["support_needed"],
        matched_keywords=matched_keywords[:5],
        response_guidance=rule["guidance"],
    )

def format_emotion_context(emotion_state: dict | EmotionState | None) -> str:
    """将情绪状态格式化为只供主对话模型参考的提示词片段。"""
    if emotion_state is None:
        emotion_state = DEFAULT_EMOTION
    if isinstance(emotion_state, EmotionState):
        emotion_state = emotion_state.to_dict()

    matched_keywords = "、".join(emotion_state.get("matched_keywords", [])) or "无"
    support = "需要调整语气" if emotion_state.get("support_needed") else "正常回应"
    is_current = "是" if emotion_state.get("is_current_experience", True) else "否"
    confidence = emotion_state.get("emotion_confidence")
    confidence_text = f"\n- 判断置信度：{confidence}" if confidence is not None else ""
    reason = emotion_state.get("emotion_reason")
    reason_text = f"\n- 判断原因：{reason}" if reason else ""
    return (
        "## 当前情绪语境\n"
        f"- 用户主要状态：{emotion_state.get('user_emotion', 'neutral')}\n"
        f"- 是否是当下正在经历：{is_current}\n"
        f"- Aura 回复氛围：{emotion_state.get('aura_mood', 'natural')}\n"
        f"- 回复模式：{support}\n"
        f"- 参考线索：{matched_keywords}\n"
        f"- 回复建议：{emotion_state.get('response_guidance', DEFAULT_EMOTION.response_guidance)}"
        f"{confidence_text}{reason_text}\n"
        "这些只是内部参考。不要复述分类、置信度或内部字段，也不要机械套用安慰步骤。"
    )
