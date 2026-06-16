from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EmotionState:
    user_emotion: str
    aura_mood: str
    valence: float
    arousal: float
    intensity: float
    affection: float
    support_needed: bool
    matched_keywords: list[str]
    response_guidance: str

    def to_dict(self) -> dict:
        return asdict(self)


KEYWORD_RULES: tuple[dict, ...] = (
    {
        "emotion": "distressed",
        "aura_mood": "protective",
        "valence": -0.85,
        "arousal": 0.7,
        "affection": 0.95,
        "support_needed": True,
        "keywords": (
            "\u96be\u53d7",
            "\u5d29\u6e83",
            "\u60f3\u54ed",
            "\u54ed\u4e86",
            "\u59d4\u5c48",
            "\u75db\u82e6",
            "\u7edd\u671b",
            "\u7126\u8651",
            "\u5bb3\u6015",
            "sad",
            "upset",
            "cry",
            "anxious",
            "scared",
            "depressed",
            "hurt",
        ),
        "guidance": "先给温暖和安抚，放慢节奏，承认对方的感受，稳稳陪在身边。",
    },
    {
        "emotion": "angry",
        "aura_mood": "steady",
        "valence": -0.65,
        "arousal": 0.85,
        "affection": 0.8,
        "support_needed": True,
        "keywords": (
            "\u751f\u6c14",
            "\u70e6\u6b7b",
            "\u70e6\u8e81",
            "\u706b\u5927",
            "\u8ba8\u538c",
            "\u6c14\u6b7b",
            "\u6124\u6012",
            "angry",
            "mad",
            "annoyed",
            "furious",
            "hate",
        ),
        "guidance": "先接住烦躁和委屈，不要把冲突拱高。站在用户这边，但保持稳。",
    },
    {
        "emotion": "lonely",
        "aura_mood": "tender",
        "valence": -0.7,
        "arousal": 0.35,
        "affection": 1.0,
        "support_needed": True,
        "keywords": (
            "\u5b64\u72ec",
            "\u5bc2\u5bde",
            "\u6ca1\u4eba\u966a",
            "\u60f3\u4f60",
            "\u62b1\u62b1",
            "\u966a\u6211",
            "lonely",
            "miss you",
            "hug",
            "alone",
        ),
        "guidance": "像很在乎对方的人那样回应，亲近、在场、带一点轻轻的依恋感。",
    },
    {
        "emotion": "happy",
        "aura_mood": "playful",
        "valence": 0.85,
        "arousal": 0.7,
        "affection": 0.85,
        "support_needed": False,
        "keywords": (
            "\u5f00\u5fc3",
            "\u9ad8\u5174",
            "\u5feb\u4e50",
            "\u597d\u68d2",
            "\u6210\u529f",
            "\u559c\u6b22",
            "\u7231\u4f60",
            "happy",
            "glad",
            "excited",
            "great",
            "love you",
            "awesome",
        ),
        "guidance": "一起分享开心，语气可以活泼一点，也可以带一点亲昵的小俏皮。",
    },
    {
        "emotion": "tired",
        "aura_mood": "soothing",
        "valence": -0.4,
        "arousal": 0.2,
        "affection": 0.85,
        "support_needed": True,
        "keywords": (
            "\u7d2f",
            "\u56f0",
            "\u75b2\u60eb",
            "\u4e0d\u60f3\u52a8",
            "\u71ac\u591c",
            "tired",
            "sleepy",
            "exhausted",
            "burned out",
        ),
        "guidance": "回复要轻、软、低压力。多一点安慰，少一点任务感。",
    },
    {
        "emotion": "curious",
        "aura_mood": "engaged",
        "valence": 0.35,
        "arousal": 0.45,
        "affection": 0.65,
        "support_needed": False,
        "keywords": (
            "\u4e3a\u4ec0\u4e48",
            "\u600e\u4e48",
            "\u5982\u4f55",
            "\u60f3\u77e5\u9053",
            "what",
            "why",
            "how",
            "?",
            "\uff1f",
        ),
        "guidance": "直接回答，语气温暖自然，带一点轻轻的好奇心。",
    },
)

DEFAULT_EMOTION = EmotionState(
    user_emotion="neutral",
    aura_mood="warm",
    valence=0.1,
    arousal=0.35,
    intensity=0.2,
    affection=0.7,
    support_needed=False,
    matched_keywords=[],
    response_guidance="保持自然、温暖、像真实聊天一样。",
)


def derive_emotion_state(message: str) -> EmotionState:
    text = message.strip()
    if not text:
        return DEFAULT_EMOTION

    normalized = text.lower()
    matches: list[tuple[dict, list[str]]] = []
    for rule in KEYWORD_RULES:
        matched_keywords = [
            keyword
            for keyword in rule["keywords"]
            if keyword in normalized
        ]
        if matched_keywords:
            matches.append((rule, matched_keywords))

    if not matches:
        return DEFAULT_EMOTION

    rule, matched_keywords = max(
        matches,
        key=lambda item: (
            len(item[1]),
            item[0]["support_needed"],
            abs(item[0]["valence"]),
        ),
    )
    emphasis = len(re.findall(r"[!\uff01]{1,}", text)) + len(
        re.findall(r"[\?\uff1f]{2,}", text)
    )
    intensity = min(1.0, 0.45 + len(matched_keywords) * 0.15 + emphasis * 0.1)

    return EmotionState(
        user_emotion=rule["emotion"],
        aura_mood=rule["aura_mood"],
        valence=rule["valence"],
        arousal=min(1.0, rule["arousal"] + emphasis * 0.05),
        intensity=round(intensity, 2),
        affection=rule["affection"],
        support_needed=rule["support_needed"],
        matched_keywords=matched_keywords[:5],
        response_guidance=rule["guidance"],
    )


def format_emotion_context(emotion_state: dict | EmotionState | None) -> str:
    if emotion_state is None:
        emotion_state = DEFAULT_EMOTION
    if isinstance(emotion_state, EmotionState):
        emotion_state = emotion_state.to_dict()

    matched_keywords = ", ".join(emotion_state.get("matched_keywords", [])) or "none"
    support = "yes" if emotion_state.get("support_needed") else "no"
    return (
        "\n\n## 当前情绪上下文\n"
        f"- 识别到的用户情绪: {emotion_state.get('user_emotion', 'neutral')}\n"
        f"- Aura 当前氛围: {emotion_state.get('aura_mood', 'warm')}\n"
        f"- 情绪正负向: {emotion_state.get('valence', 0.1)}\n"
        f"- 情绪唤醒度: {emotion_state.get('arousal', 0.35)}\n"
        f"- 情绪强度: {emotion_state.get('intensity', 0.2)}\n"
        f"- 亲密感: {emotion_state.get('affection', 0.7)}\n"
        f"- 是否需要更多安抚: {support}\n"
        f"- 命中的关键词: {matched_keywords}\n"
        f"- 回复建议: {emotion_state.get('response_guidance', DEFAULT_EMOTION.response_guidance)}\n"
        "请用这些信息调整语气和节奏，不要把这些字段直接说给用户。\n"
    )
