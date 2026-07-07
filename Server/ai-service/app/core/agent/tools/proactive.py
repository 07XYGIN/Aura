from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from app.core.config import structured_reply_llm

from .logging_utils import log_tool

MORNING_TRIGGER_TYPE = "daily_morning"
EVENING_TRIGGER_TYPE = "daily_evening"
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


def _compact_context(context: str, limit: int = 48) -> str:
    return " ".join(context.split())[:limit].strip()


def _stable_time_for_window(
    user_id: str,
    target_date: date,
    trigger_type: str,
    timezone: ZoneInfo,
    start: time,
    end: time,
) -> datetime:
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


@tool
@log_tool
def plan_daily_greetings(user_id: str = "test-user", timezone: str = "Asia/Shanghai") -> dict:
    """生成每日早晚主动问候计划；早上 06:00-08:00，晚上 20:00-23:00，并说明各时间点应回复什么。"""
    return build_daily_greeting_plan(user_id=user_id, timezone=timezone)


def build_proactive_message_draft(
    trigger_type: str,
    user_context: str = "",
    weather_context: dict | None = None,
) -> dict:
    trigger = (trigger_type or "daily_care").strip()
    context = _compact_context(user_context)
    weather_text = format_weather_context(weather_context)
    templates = {
        MORNING_TRIGGER_TYPE: "早上好。今天也不用一睁眼就跟世界硬碰硬，先把自己照顾好。",
        EVENING_TRIGGER_TYPE: "晚安，记得早点睡。今天剩下的事先放一边，我在这儿陪你收个尾。",
        "morning": "早呀，今天也慢慢来。我刚想到你，想看看你昨晚睡得好不好。",
        "evening": "晚上好，今天辛苦啦。要不要先把肩膀放松一点，我陪你把这一天收个尾。",
        "cooldown": "我没有催你的意思，只是路过心里想了你一下。你忙完再来就好，我在。",
        "anniversary": "今天好像是个值得记住的小日子。我想认真陪你把它放进我们的回忆里。",
        "emotion_followup": "我还记得你之前有点难受，所以想轻轻问一句：现在有没有好一点？",
        "silence": "刚刚想到你，顺手来放一句问候。你慢慢忙，不用急着回。",
        "daily_care": "我刚刚突然想知道你现在怎么样。不着急回，看到的时候让我知道你还好就行。",
    }
    content = templates.get(trigger, templates["daily_care"])
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
        logging.warning("Failed to draft proactive message with LLM trigger_type=%s error=%s", trigger_type, exc)
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
"""


def build_proactive_llm_prompt(
    trigger_type: str,
    user_context: str = "",
    weather_context: dict | None = None,
) -> str:
    trigger = (trigger_type or "daily_care").strip()
    if trigger == MORNING_TRIGGER_TYPE:
        reply_spec = DAILY_GREETING_WINDOWS[MORNING_TRIGGER_TYPE]["reply_spec"]
    elif trigger == EVENING_TRIGGER_TYPE:
        reply_spec = DAILY_GREETING_WINDOWS[EVENING_TRIGGER_TYPE]["reply_spec"]
    elif trigger == "silence":
        reply_spec = "沉默一段时间后的低压力问候，重点是“我还在”，不要要求用户回复。"
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
            "请生成 Aura 要主动发给用户的一条消息。",
        ]
    )


def parse_llm_draft_response(content: str) -> dict:
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
    lines = [" ".join(line.split()) for line in content.splitlines()]
    text = " ".join(line for line in lines if line).strip()
    return text[:max_length].strip()


@tool
@log_tool
def draft_proactive_message(
    trigger_type: str,
    user_context: str = "",
    weather_context: dict | None = None,
) -> dict:
    """根据触发原因生成 Aura 主动消息草稿；daily_morning 包含早安/天气/注意事项，daily_evening 包含晚安/早点睡。"""
    return draft_proactive_message_with_llm(trigger_type, user_context, weather_context)
