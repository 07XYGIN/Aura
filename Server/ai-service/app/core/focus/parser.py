"""用确定性规则识别一起专注的高置信度聊天命令。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FocusChatIntent:
    """聊天分流可执行的专注动作及其参数。"""

    action: str
    activity: str | None = None
    duration_minutes: int | None = None
    result_summary: str | None = None
    blocker: str | None = None


START_PATTERNS = (
    re.compile(r"(?:陪我|和我|一起)?(?P<activity>写代码|学习|工作|看书|画画|复习|背单词)\s*(?P<minutes>\d{1,3})\s*(?:分钟|分)"),
    re.compile(r"(?:开始|来|一起|陪我)?\s*专注(?:做|搞|写)?\s*(?P<activity>[^，。！？,.!?\d]{0,24}?)\s*(?P<minutes>\d{1,3})\s*(?:分钟|分)"),
    re.compile(r"(?:开|来)\s*(?P<minutes>\d{1,3})\s*(?:分钟|分)(?:的)?(?:专注|番茄钟)"),
)
STATUS_PATTERN = re.compile(r"(?:专注|番茄钟).{0,10}(?:状态|还剩|多久|几分钟)|(?:还剩|还有).{0,8}(?:分钟|时间)")
PAUSE_PATTERN = re.compile(r"(?:暂停|停一下|先停).{0,8}(?:专注|计时|番茄钟)|(?:专注|计时|番茄钟).{0,8}(?:暂停|停一下)")
RESUME_PATTERN = re.compile(r"(?:继续|恢复).{0,8}(?:专注|计时|番茄钟)|(?:专注|计时|番茄钟).{0,8}(?:继续|恢复)")
CANCEL_PATTERN = re.compile(r"(?:取消|结束|不要了|不专注了).{0,8}(?:专注|计时|番茄钟)|(?:专注|计时|番茄钟).{0,8}(?:取消|结束|不要了)")
REPORT_PATTERN = re.compile(r"(?:做完|写完|完成|搞定|没做完|没完成|进度|卡住|卡在|没进展)")
BLOCKER_PATTERN = re.compile(r"(?:卡在|卡住(?:了)?|问题是|还没解决的是)\s*[：:，,]?\s*(?P<blocker>.+)")
NO_BLOCKER_PATTERN = re.compile(r"(?:没卡点|没有卡点|没卡住|没有问题|挺顺利)")


def parse_focus_chat_intent(message: str, *, current_status: str | None) -> FocusChatIntent | None:
    """解析明确的开始、控制、状态或进度汇报消息。

    普通出现“专注”一词的聊天不会命中。进度汇报只有在服务端确实处于
    ``awaiting_report`` 时才会识别，避免把日常的“代码卡住了”抢走。
    """

    text = str(message or "").strip()
    if not text:
        return None
    for pattern in START_PATTERNS:
        match = pattern.search(text)
        if match:
            minutes = int(match.group("minutes"))
            if not 1 <= minutes <= 240:
                return FocusChatIntent("invalid_duration", duration_minutes=minutes)
            activity = (match.groupdict().get("activity") or "手头的事").strip()
            return FocusChatIntent("start", activity=activity or "手头的事", duration_minutes=minutes)
    if STATUS_PATTERN.search(text):
        return FocusChatIntent("status")
    if PAUSE_PATTERN.search(text):
        return FocusChatIntent("pause")
    if RESUME_PATTERN.search(text):
        return FocusChatIntent("resume")
    if CANCEL_PATTERN.search(text):
        return FocusChatIntent("cancel")
    if current_status == "awaiting_report" and REPORT_PATTERN.search(text):
        blocker = None
        blocker_match = BLOCKER_PATTERN.search(text)
        if blocker_match and not NO_BLOCKER_PATTERN.search(text):
            blocker = blocker_match.group("blocker").strip()[:1200] or None
        return FocusChatIntent(
            "report",
            result_summary=text[:1200],
            blocker=blocker,
        )
    return None


def is_focus_chat_candidate(message: str) -> bool:
    """在查询数据库前粗筛可能的专注命令或汇报。"""

    text = str(message or "")
    return any(
        keyword in text
        for keyword in (
            "专注", "番茄钟", "陪我写代码", "陪我学习", "做完", "写完",
            "完成", "搞定", "没做完", "没完成", "进度", "卡住", "卡在",
        )
    )
