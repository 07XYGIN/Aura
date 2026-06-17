from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import tool

from .logging_utils import log_tool


WEEKDAY_NAMES = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


@tool
@log_tool
def get_current_datetime(timezone: str = "Asia/Shanghai") -> dict[str, str]:
    """获取指定时区的当前日期、时间和星期。"""
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("Asia/Shanghai")
        timezone = "Asia/Shanghai"

    now = datetime.now(tz)
    return {
        "timezone": timezone,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": WEEKDAY_NAMES[now.weekday()],
        "iso": now.isoformat(timespec="seconds"),
    }
