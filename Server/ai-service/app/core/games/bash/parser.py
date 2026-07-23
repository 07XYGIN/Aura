"""巴什博弈聊天命令的高置信度解析器。"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHINESE_NUMBERS = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
START_PATTERNS = (
    "巴什博弈",
    "巴什游戏",
    "拿石子游戏",
    "取石子游戏",
)
RESIGN_PATTERNS = ("认输", "我输了", "退出游戏", "不玩了", "结束游戏")
STATUS_PATTERNS = ("还剩多少", "剩几颗", "轮到谁", "看看棋局", "当前局面")
REMATCH_PATTERNS = ("再来一局", "再玩一局", "重新来一局", "重开一局")
RULE_PATTERNS = ("规则", "怎么玩", "玩法")
MOVE_PATTERN = re.compile(
    r"^(?:我\s*)?(?:拿|取|拿走|取走)\s*([一二两三四五六七八九十]|\d{1,2})"
    r"\s*(?:颗|个)?\s*(?:石子)?\s*[。！!~～]*$"
)
BARE_MOVE_PATTERN = re.compile(
    r"^([一二两三四五六七八九十]|\d{1,2})\s*(?:颗|个)?\s*[。！!~～]*$"
)


@dataclass(frozen=True)
class BashChatIntent:
    """从用户自然语言中解析出的确定性游戏意图。

    Attributes:
        action: ``start``、``move``、``status``、``resign`` 或 ``rules``。
        take_count: ``move`` 意图对应的取子数，其余动作为空。
    """

    action: str
    take_count: int | None = None


def parse_bash_chat_intent(message: str, *, has_active_game: bool) -> BashChatIntent | None:
    """只解析不会与普通聊天明显冲突的巴什博弈命令。

    Args:
        message: 用户本轮原始文本。
        has_active_game: 当前用户是否有进行中的棋局。只有为真时，裸数字或
            “我拿两个”才会解释成游戏行动。

    Returns:
        高置信度游戏意图；普通聊天或含糊表达返回 ``None``，继续交给主模型。

    Notes:
        “我拿三个方案比较”不会匹配落子正则；“拿四颗”会保留为明确游戏动作，
        再由规则服务返回超出上限的中文错误。
    """

    text = " ".join(str(message or "").strip().split())
    if not text:
        return None

    mentions_bash = any(pattern in text for pattern in START_PATTERNS)
    if mentions_bash and any(pattern in text for pattern in RULE_PATTERNS):
        return BashChatIntent("rules")
    if text in REMATCH_PATTERNS:
        return BashChatIntent("start")
    if mentions_bash:
        return BashChatIntent("start")
    if not has_active_game:
        return None
    if any(pattern in text for pattern in RESIGN_PATTERNS):
        return BashChatIntent("resign")
    if any(pattern in text for pattern in STATUS_PATTERNS):
        return BashChatIntent("status")

    match = MOVE_PATTERN.fullmatch(text) or BARE_MOVE_PATTERN.fullmatch(text)
    if match:
        return BashChatIntent("move", parse_take_count(match.group(1)))
    return None


def parse_take_count(value: str) -> int:
    """把阿拉伯数字或一到十的中文数字转换为整数。

    Raises:
        ValueError: 输入不在解析器支持的数字形式中。
    """

    if value in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[value]
    return int(value)
