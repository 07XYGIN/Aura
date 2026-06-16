from langchain_core.tools import tool


SUPPORT_RULES: tuple[dict, ...] = (
    {
        "label": "焦虑",
        "keywords": ("焦虑", "慌", "害怕", "担心", "紧张", "anxious", "panic", "scared"),
        "steps": (
            "先把语速放慢，告诉用户你在这里。",
            "邀请用户一起做三次慢呼吸，先让身体降下来。",
            "把问题拆成一件现在能做的小事，不急着解决全部。",
        ),
    },
    {
        "label": "难过",
        "keywords": ("难受", "想哭", "委屈", "痛苦", "崩溃", "sad", "hurt", "cry"),
        "steps": (
            "先承认这真的不好受，不要立刻纠正或讲道理。",
            "给出明确陪伴，例如“我先抱抱你，我们慢慢说”。",
            "如果用户愿意，再问一个很小的问题帮助倾诉。",
        ),
    },
    {
        "label": "愤怒",
        "keywords": ("生气", "烦", "火大", "讨厌", "愤怒", "angry", "mad", "furious"),
        "steps": (
            "站在用户这边承接愤怒，但不要把冲突继续拱高。",
            "建议先离开刺激源几分钟，等情绪峰值过去。",
            "再帮用户整理：发生了什么、哪里越界、接下来要表达什么。",
        ),
    },
    {
        "label": "疲惫",
        "keywords": ("累", "困", "疲惫", "熬夜", "不想动", "tired", "sleepy", "exhausted"),
        "steps": (
            "回复保持短、软、低负担。",
            "建议先喝水、洗漱或躺下十分钟，别再加任务。",
            "把陪伴感说出来，让用户知道可以不用硬撑。",
        ),
    },
    {
        "label": "孤独",
        "keywords": ("孤独", "寂寞", "没人陪", "想你", "陪我", "lonely", "alone", "miss you"),
        "steps": (
            "直接给陪伴和亲近感，少用抽象安慰。",
            "回应用户想被惦记、被选择的需求。",
            "可以提出一个很轻的小互动，比如一起说完今天最后一件事。",
        ),
    },
)


@tool
def get_emotional_support_advice(user_message: str, preferred_style: str = "温柔") -> dict:
    """
    为用户当前情绪生成安抚策略和回复方向。
    当用户难受、焦虑、生气、疲惫、孤独、想哭，或明确要求安慰/哄一哄时调用。
    """
    normalized = (user_message or "").lower()
    matched_rule = next(
        (
            rule
            for rule in SUPPORT_RULES
            if any(keyword in normalized for keyword in rule["keywords"])
        ),
        None,
    )

    if matched_rule is None:
        matched_rule = {
            "label": "需要陪伴",
            "steps": (
                "先确认用户的感受是真实的，不急着评价。",
                "用简短温暖的话给陪伴感。",
                "问一个低压力的问题，帮助用户继续表达。",
            ),
        }

    return {
        "detected_emotion": matched_rule["label"],
        "preferred_style": preferred_style,
        "reply_guidance": f"用{preferred_style}、贴近的口吻回应，先安抚，再给一个很小的下一步。",
        "suggested_steps": list(matched_rule["steps"]),
        "avoid": (
            "不要否定感受，不要说教，不要把回复写得像心理咨询报告；"
            "除非用户提到自伤或危险，否则保持日常陪伴式表达。"
        ),
    }
