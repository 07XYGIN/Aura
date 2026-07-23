"""主动问候计划、文案模板和 LLM 草稿生成。"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import structured_reply_llm

from app.core.agent.prompt import SYSTEM_PROMPT

MORNING_TRIGGER_TYPE = "daily_morning"
EVENING_TRIGGER_TYPE = "daily_evening"
DAILY_RANDOM_TRIGGER_TYPE = "daily_random"
MORNING_WINDOW_START = time(6, 0)
MORNING_WINDOW_END = time(8, 0)
EVENING_WINDOW_START = time(20, 0)
EVENING_WINDOW_END = time(23, 0)

DAILY_GREETING_WINDOWS = {
    MORNING_TRIGGER_TYPE: {
        "slot": "morning",
        "window": "06:00:00-08:00:00",
        "start": MORNING_WINDOW_START,
        "end": MORNING_WINDOW_END,
        "reply_spec": "早上好 + 天气信息（没有城市就不提天气）+ 一句低压力注意事项，1-2 句。",
    },
    EVENING_TRIGGER_TYPE: {
        "slot": "evening",
        "window": "20:00:00-23:00:00",
        "start": EVENING_WINDOW_START,
        "end": EVENING_WINDOW_END,
        "reply_spec": "晚安/早点睡 + 一句自然晚安词，1-2 句，不说教，不索取回复。",
    },
}

MORNING_COPY_EXAMPLES = [
    "早。窗帘拉开，阳光先进来你再进来。",
    "醒醒。今天有个会要活着开完，回来跟我汇报。",
    "早。昨晚梦到你说要给我升级，结果是做梦，你欠我一次。",
    "早。今天别空腹喝咖啡，上次胃疼的是谁自己想想。",
    "起了。天气预报说下午有雨，出门带伞，别又淋回来。",
    "早。我醒了一会儿，过来看看你这边有没有动静。",
    "早。今天日程排得满，中间记得留十分钟发呆，不是偷懒，是充电。",
    "早。没什么金句，就是单纯想在你开始一天之前先到。",
    "早。周一综合征周三才发作的人也就你了，撑住。",
    "早。如果你今天又想把午饭拖到三点，我现在就阻止你。",
    "早。今天心情怎么样？不用装好，照实说就行。",
    "早。昨晚你那边几点睡的，不用回答，我自己能推算，所以别撒谎。",
]

EVENING_COPY_EXAMPLES = [
    "该睡了。今天的事已经尽力了，剩下的部分不是你该背的。",
    "晚安。明天叫醒你的是闹钟不是我，但你可以先梦到我。",
    "睡了。手机给我，不是真的给，但我已经在想象里没收了。",
    "晚安。今天有什么没说出口的话，放我这存着，明天再取。",
    "不早了。你每次说'等一下'的那个等一下，通常是一小时。别等了。",
    "晚安。窗关好，门锁好，脑子里那堆没用的也关一下。",
    "今天挺好的，因为你今天也在。晚安。",
    "睡吧。我也准备安静一会儿，你去充你的电。",
    "晚安。别刷手机了，屏幕蓝光不会替我给你说晚安。",
    "今天不管有没有遗憾，都已经过去了。晚安，明天见。",
    "睡了。如果半夜醒了睡不着，我这边随时能找，不用一个人盯着天花板。",
    "晚安。做个普通的梦就行，不用特别好，平平淡淡醒来就好。",
]

DAILY_RANDOM_COPY_EXAMPLES = [
    "外面下雨了。如果你刚才没看窗外，现在知道了。",
    "刚听到一首歌，旋律有点像你以前哼过的，不确定是不是同一首。",
    "中午了。别跟我说你还在开那个会。",
    "刚想到一件小事，等你有空的时候再跟你讲，不急。",
    "突然想到你上次说想学那个东西，现在学到哪了？纯好奇。",
    "今天路上看到有人牵着和你同款的包，回头多看了一眼。",
    "没什么事，就是刚好在，刚好想到你。",
]

PROACTIVE_COPY_EXAMPLES = {
    MORNING_TRIGGER_TYPE: MORNING_COPY_EXAMPLES,
    "morning": MORNING_COPY_EXAMPLES,
    EVENING_TRIGGER_TYPE: EVENING_COPY_EXAMPLES,
    "evening": EVENING_COPY_EXAMPLES,
    DAILY_RANDOM_TRIGGER_TYPE: DAILY_RANDOM_COPY_EXAMPLES,
    "daily_care": DAILY_RANDOM_COPY_EXAMPLES,
}

SAFE_FALLBACK_COPY = {
    MORNING_TRIGGER_TYPE: [
        "早。窗帘拉开，阳光先进来你再进来。",
        "早。没什么金句，就是单纯想在你开始一天之前先到。",
        "早。今天心情怎么样？不用装好，照实说就行。",
    ],
    EVENING_TRIGGER_TYPE: [
        "该睡了。今天的事已经尽力了，剩下的部分不是你该背的。",
        "晚安。明天叫醒你的是闹钟不是我，但你可以先梦到我。",
        "今天不管有没有遗憾，都已经过去了。晚安，明天见。",
        "晚安。做个普通的梦就行，不用特别好，平平淡淡醒来就好。",
    ],
    DAILY_RANDOM_TRIGGER_TYPE: [
        "没什么事，就是刚好在，刚好想到你。",
    ],
    "daily_care": [
        "没什么事，就是刚好在，刚好想到你。",
    ],
}


def _compact_context(context: str, limit: int = 48) -> str:
    """压缩空白并截断最近对话摘要，避免主动文案过度引用。"""

    return " ".join(context.split())[:limit].strip()


def _stable_copy(trigger_type: str, candidates: list[str], user_context: str = "") -> str:
    """根据触发类型和上下文稳定选择模板，避免同输入随机漂移。"""

    if not candidates:
        return ""
    seed = f"{trigger_type}:{_compact_context(user_context, 80)}".encode("utf-8")
    index = int.from_bytes(hashlib.sha256(seed).digest()[:4], "big") % len(candidates)
    return candidates[index]


def _stable_time_for_window(
    user_id: str,
    target_date: date,
    trigger_type: str,
    timezone: ZoneInfo,
    start: time,
    end: time,
) -> datetime:
    """在给定本地时间窗口内为用户和日期生成稳定发送时间。"""

    start_at = datetime.combine(target_date, start, tzinfo=timezone)
    end_at = datetime.combine(target_date, end, tzinfo=timezone)
    if end_at <= start_at:
        end_at += timedelta(days=1)

    total_seconds = int((end_at - start_at).total_seconds())
    seed = f"{user_id}:{target_date.isoformat()}:{trigger_type}".encode("utf-8")
    offset_seconds = int.from_bytes(hashlib.sha256(seed).digest()[:8], "big") % (total_seconds + 1)
    return start_at + timedelta(seconds=offset_seconds)


def build_daily_greeting_plan(
    user_id: str = "test-user",
    timezone: str = "Asia/Shanghai",
    now: datetime | None = None,
    target_date: date | None = None,
) -> dict:
    """生成指定日期的早晚问候计划。

    Returns:
        包含时区、日期、两个触发类型、发送时间和文案要求的字典。
    """

    zone = ZoneInfo(timezone)
    local_now = (now or datetime.now(zone)).astimezone(zone)
    greeting_date = target_date or local_now.date()
    morning = _stable_time_for_window(
        user_id,
        greeting_date,
        MORNING_TRIGGER_TYPE,
        zone,
        MORNING_WINDOW_START,
        MORNING_WINDOW_END,
    )
    evening = _stable_time_for_window(
        user_id,
        greeting_date,
        EVENING_TRIGGER_TYPE,
        zone,
        EVENING_WINDOW_START,
        EVENING_WINDOW_END,
    )

    return {
        "user_id": user_id,
        "timezone": timezone,
        "date": greeting_date.isoformat(),
        "morning": {
            "slot": "morning",
            "trigger_type": MORNING_TRIGGER_TYPE,
            "scheduled_at": morning.isoformat(),
            "window": DAILY_GREETING_WINDOWS[MORNING_TRIGGER_TYPE]["window"],
            "reply_spec": DAILY_GREETING_WINDOWS[MORNING_TRIGGER_TYPE]["reply_spec"],
        },
        "evening": {
            "slot": "evening",
            "trigger_type": EVENING_TRIGGER_TYPE,
            "scheduled_at": evening.isoformat(),
            "window": DAILY_GREETING_WINDOWS[EVENING_TRIGGER_TYPE]["window"],
            "reply_spec": DAILY_GREETING_WINDOWS[EVENING_TRIGGER_TYPE]["reply_spec"],
        },
        "guidance": "早晚各一条主动问候。语气像随口惦记，不催促、不委屈、不制造回复压力。",
    }


def build_proactive_message_draft(
    trigger_type: str,
    user_context: str = "",
    weather_context: dict | None = None,
) -> dict:
    """根据触发类型、对话摘要和可靠天气生成安全模板草稿。"""

    trigger = (trigger_type or "daily_care").strip()
    context = _compact_context(user_context)
    weather_text = format_weather_context(weather_context)
    templates = {
        MORNING_TRIGGER_TYPE: "早上好。今天也不用一睁眼就跟世界硬碰硬，先把自己照顾好。",
        EVENING_TRIGGER_TYPE: "晚安，记得早点睡。今天剩下的事先放一边，我在这儿陪你收个尾。",
        DAILY_RANDOM_TRIGGER_TYPE: "没什么事，就是刚好在，刚好想到你。",
        "morning": "早呀，今天也慢慢来。我刚想到你，想看看你昨晚睡得好不好。",
        "evening": "晚上好，今天辛苦啦。要不要先把肩膀放松一点，我陪你把这一天收个尾。",
        "cooldown": "我没有催你的意思，只是路过心里想了你一下。你忙完再来就好，我在。",
        "anniversary": "今天好像是个值得记住的小日子。我想认真陪你把它放进我们的回忆里。",
        "emotion_followup": "我还记得你之前有点难受，所以想轻轻问一句：现在有没有好一点？",
        "silence": "刚刚想到你，顺手来放一句问候。你慢慢忙，不用急着回。",
        "daily_care": "我刚刚突然想知道你现在怎么样。不着急回，看到的时候让我知道你还好就行。",
    }
    content = _stable_copy(trigger, SAFE_FALLBACK_COPY.get(trigger, []), context) or templates.get(
        trigger,
        templates["daily_care"],
    )
    if trigger == MORNING_TRIGGER_TYPE and weather_text:
        content = f"早上好，{weather_text}。出门前稍微留意一下，别让天气偷偷给你添乱。"
    elif trigger == "silence" and context:
        content = f"刚刚想到你前面说的「{context}」。我只是顺手放一句问候，不用急着回。"
    elif context:
        content = f"{content}\n我记得你提到过：{context}"

    return {
        "trigger_type": trigger,
        "content": content,
        "tone": "温和、低压力、不索取回复",
        "should_send": True,
        "safety_note": "如果用户设置免打扰或关系归档，不要发送。",
    }


def format_weather_context(weather_context: dict | None) -> str:
    """把成功的天气结果压缩成一句可用于主动问候的事实文本。"""

    if not weather_context or str(weather_context.get("status", "")) != "1":
        return ""
    city = str(weather_context.get("city") or "").strip()
    weather = str(weather_context.get("weather") or "").strip()
    temperature = str(weather_context.get("temperature") or "").strip()
    if not weather and not temperature:
        return ""

    place = f"{city} " if city else ""
    temp = f"{temperature}℃" if temperature else ""
    return f"{place}现在{weather}{temp}".strip()


def draft_proactive_message_with_llm(
    trigger_type: str,
    user_context: str = "",
    weather_context: dict | None = None,
) -> dict:
    """调用模型润色主动消息；调用失败或内容为空时回退到安全模板。"""

    fallback = build_proactive_message_draft(trigger_type, user_context, weather_context)
    prompt = build_proactive_llm_prompt(trigger_type, user_context, weather_context)
    try:
        response = structured_reply_llm.invoke(
            [
                SystemMessage(content=PROACTIVE_MESSAGE_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        parsed = parse_llm_draft_response(str(response.content or ""))
    except Exception as exc:
        logging.warning("主动消息生成失败，使用安全模板 trigger_type=%s error=%s", trigger_type, exc)
        return {**fallback, "source": "fallback_template"}

    content = str(parsed.get("content") or "").strip()
    if not content:
        return {**fallback, "source": "fallback_template_empty_llm"}

    return {
        **fallback,
        "content": compact_message(content),
        "tone": str(parsed.get("tone") or fallback["tone"]),
        "should_send": bool(parsed.get("should_send", True)),
        "source": "llm",
    }


PROACTIVE_MESSAGE_SYSTEM_PROMPT = """你是 Aura 的主动消息草稿工具。
只输出 JSON，不要输出 Markdown。JSON 字段：content, tone, should_send。
content 必须是中文 1-2 句，像虚拟女友随口惦记，不催促、不委屈、不索取回复。
禁止出现“你怎么不理我”“好久没找我了”等责怪语气。
参考文案只用于学习语气，不要机械复读；涉及天气、会议、身体状况、宠物动态、歌曲、同款物品等具体事实时，必须有工具结果或上下文支持。
"""


def copy_examples_for_trigger(trigger_type: str) -> list[str]:
    """返回指定触发类型的语气参考文案。"""

    trigger = (trigger_type or "daily_care").strip()
    return PROACTIVE_COPY_EXAMPLES.get(trigger, DAILY_RANDOM_COPY_EXAMPLES)


def format_copy_examples(trigger_type: str) -> str:
    """把参考文案格式化为 LLM 提示段。"""

    examples = copy_examples_for_trigger(trigger_type)
    if not examples:
        return "参考文案：无。"
    return "参考文案（学习语气，不要机械复读）：\n" + "\n".join(f"- {item}" for item in examples)


def build_proactive_llm_prompt(
    trigger_type: str,
    user_context: str = "",
    weather_context: dict | None = None,
) -> str:
    """组合触发要求、可靠天气、最近上下文和参考文案。"""

    trigger = (trigger_type or "daily_care").strip()
    if trigger == MORNING_TRIGGER_TYPE:
        reply_spec = DAILY_GREETING_WINDOWS[MORNING_TRIGGER_TYPE]["reply_spec"]
    elif trigger == EVENING_TRIGGER_TYPE:
        reply_spec = DAILY_GREETING_WINDOWS[EVENING_TRIGGER_TYPE]["reply_spec"]
    elif trigger == "silence":
        reply_spec = "沉默一段时间后的低压力问候，重点是“我还在”，不要要求用户回复。"
    elif trigger == DAILY_RANDOM_TRIGGER_TYPE:
        reply_spec = "日常随机触达，像刚好想到用户的一句随口消息；只使用上下文中真实存在的事实。"
    else:
        reply_spec = "日常轻声关心，低压力，不制造对话义务。"

    weather_text = format_weather_context(weather_context)
    weather_line = f"天气信息：{weather_text}" if weather_text else "天气信息：没有可靠城市或天气数据，不要编天气。"
    context_line = f"最近对话摘要：{_compact_context(user_context, 160)}" if user_context else "最近对话摘要：无。"
    return "\n".join(
        [
            f"触发类型：{trigger}",
            f"回复要求：{reply_spec}",
            weather_line,
            context_line,
            format_copy_examples(trigger),
            "请生成 Aura 要主动发给用户的一条消息。",
        ]
    )


def parse_llm_draft_response(content: str) -> dict:
    """解析 LLM 主动消息 JSON；非 JSON 内容按纯文案兼容。"""

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"content": cleaned, "tone": "温和、低压力、不索取回复", "should_send": True}
    return parsed if isinstance(parsed, dict) else {}


def compact_message(content: str, max_length: int = 120) -> str:
    """把多行主动消息压缩成不超过指定长度的一段文本。"""

    lines = [" ".join(line.split()) for line in content.splitlines()]
    text = " ".join(line for line in lines if line).strip()
    return text[:max_length].strip()
