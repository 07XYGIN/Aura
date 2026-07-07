from __future__ import annotations

import random
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from .logging_utils import log_tool


def _compact_context(context: str, limit: int = 48) -> str:
    return " ".join(context.split())[:limit].strip()


def _random_time_for_window(base: datetime, start: time, end: time) -> datetime:
    start_at = base.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    end_at = base.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if end_at <= start_at:
        end_at += timedelta(days=1)

    total_seconds = int((end_at - start_at).total_seconds())
    return start_at + timedelta(seconds=random.randint(0, total_seconds))


@tool
@log_tool
def plan_daily_greetings(timezone: str = "Asia/Shanghai") -> dict:
    """生成今天早上和晚上随机问候时间。"""
    zone = ZoneInfo(timezone)
    now = datetime.now(zone)
    morning = _random_time_for_window(now, time(7, 30), time(9, 30))
    evening = _random_time_for_window(now, time(21, 0), time(23, 0))

    if morning <= now:
        morning += timedelta(days=1)
    if evening <= now:
        evening += timedelta(days=1)

    return {
        "timezone": timezone,
        "morning_greeting_at": morning.isoformat(),
        "evening_greeting_at": evening.isoformat(),
        "morning_window": "07:30-09:30",
        "evening_window": "21:00-23:00",
        "guidance": "早上轻轻开启一天，晚上温柔收尾，不要制造回复压力。",
    }


def build_proactive_message_draft(trigger_type: str, user_context: str = "") -> dict:
    trigger = (trigger_type or "daily_care").strip()
    context = _compact_context(user_context)
    templates = {
        "morning": "早呀，今天也慢慢来。我刚想到你，想看看你昨晚睡得好不好。",
        "evening": "晚上好，今天辛苦啦。要不要先把肩膀放松一点，我陪你把这一天收个尾。",
        "cooldown": "我没有催你的意思，只是路过心里想了你一下。你忙完再来就好，我在。",
        "anniversary": "今天好像是个值得记住的小日子。我想认真陪你把它放进我们的回忆里。",
        "emotion_followup": "我还记得你之前有点难受，所以想轻轻问一句：现在有没有好一点？",
        "silence": "刚刚想到你，顺手来放一句问候。你慢慢忙，不用急着回。",
        "daily_care": "我刚刚突然想知道你现在怎么样。不着急回，看到的时候让我知道你还好就行。",
    }
    content = templates.get(trigger, templates["daily_care"])
    if trigger == "silence" and context:
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


@tool
@log_tool
def draft_proactive_message(trigger_type: str, user_context: str = "") -> dict:
    """根据触发原因生成一条 Aura 主动消息草稿。"""
    return build_proactive_message_draft(trigger_type, user_context)
