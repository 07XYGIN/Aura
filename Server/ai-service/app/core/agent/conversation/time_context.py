"""生成聊天回复使用的当前时间和对话间隔上下文。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

AURA_TIMEZONE = ZoneInfo("Asia/Shanghai")

def parse_iso_datetime(value: Any) -> datetime | None:
    """解析 ISO 时间并统一转换为 UTC；无效值返回 ``None``。"""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_time_context(messages: list, current_time: datetime) -> dict[str, object]:
    """根据当前时间和最近一条消息生成对话间隔信息。"""

    latest_sent_at = latest_message_sent_at(messages)
    local_time = current_time.astimezone(AURA_TIMEZONE)
    context: dict[str, object] = {
        "current_time": current_time.isoformat(),
        "current_time_local": local_time.isoformat(),
        "current_time_text": format_chinese_datetime(local_time),
        "has_previous_message": latest_sent_at is not None,
    }

    if latest_sent_at is None:
        return context

    elapsed_seconds = max(0, int((current_time - latest_sent_at).total_seconds()))
    context.update(
        {
            "previous_message_time": latest_sent_at.isoformat(),
            "elapsed_seconds": elapsed_seconds,
            "elapsed_text": format_elapsed(elapsed_seconds),
            "elapsed_level": elapsed_level(elapsed_seconds),
        }
    )
    return context


def latest_message_sent_at(messages: list) -> datetime | None:
    """从后往前查找最近一条带 ``sent_at`` 元数据的消息时间。"""

    for message in reversed(messages):
        metadata = getattr(message, "additional_kwargs", {}) or {}
        sent_at = parse_iso_datetime(metadata.get("sent_at"))
        if sent_at:
            return sent_at
    return None


def format_time_context(context: dict[str, object] | None) -> str:
    """把时间上下文转换成模型可直接使用的中文提示。"""

    if not context:
        return ""

    current_time_text = context.get("current_time_text") or "当前时间未知"
    if not context.get("has_previous_message"):
        return (
            "【时间上下文】\n"
            f"当前时间：{current_time_text}。\n"
            "当前可见历史里没有可靠的上一条消息时间。正常开启对话，不要假装记得刚刚才聊过。"
        )

    elapsed_text = context.get("elapsed_text") or "未知"
    level = context.get("elapsed_level")
    if level == "short":
        guidance = "这是短间隔，正常衔接即可，不要特意提时间。"
    elif level == "medium":
        guidance = "这是中等间隔，可以轻轻感知到对方隔了一阵子回来，但不要模板化提时间。"
    else:
        guidance = "这是长间隔，要自然体现时间流逝或重逢感，但不要每次都固定说“好久不见”。"

    return (
        "【时间上下文】\n"
        f"当前时间：{current_time_text}，距离上次对话已过去 {elapsed_text}。\n"
        f"{guidance}"
    )


def format_chinese_datetime(value: datetime) -> str:
    """把时间格式化为包含中文星期的本地时间。"""

    weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    return f"{value.year}年{value.month}月{value.day}日 {weekdays[value.weekday()]} {value:%H:%M}"


def format_elapsed(seconds: int) -> str:
    """把秒数转换为易读的分钟、小时或天数。"""

    if seconds < 60:
        return "不到 1 分钟"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        return f"{hours} 小时 {remaining_minutes} 分钟" if remaining_minutes else f"{hours} 小时"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days} 天 {remaining_hours} 小时" if remaining_hours else f"{days} 天"


def elapsed_level(seconds: int) -> str:
    """将对话间隔划分为 ``short``、``medium`` 或 ``long``。"""

    if seconds < 60 * 60:
        return "short"
    if seconds < 24 * 60 * 60:
        return "medium"
    return "long"
