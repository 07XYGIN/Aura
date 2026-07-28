"""对 Aura 常见日常对话的离线风格回归检查。"""

from __future__ import annotations

from dataclasses import dataclass


CASUAL_GREETING_MARKERS = ("早", "晚安", "在吗", "早呀", "早安")
INVENTED_ROUTINE_MARKERS = ("周末的风格", "我在工作室", "靠窗", "改图标", "喝咖啡")
UNWANTED_BOREDOM_MARKERS = (
    "先别急着",
    "别急着定",
    "吃点东西",
    "找点事做",
    "把早上这口气喘匀",
)


@dataclass(frozen=True)
class ConversationRegressionResult:
    """一条候选回复的本地风格检查结果。"""

    passed: bool
    violations: tuple[str, ...]


def evaluate_conversation_reply(user_message: str, reply: str) -> ConversationRegressionResult:
    """检查用户已明确指出的不舒服模式，不替代模型内容安全判断。"""

    user_text = (user_message or "").strip()
    response = (reply or "").strip()
    violations: list[str] = []

    if not response:
        violations.append("回复为空")
    if is_simple_greeting(user_text):
        if any(marker in response for marker in INVENTED_ROUTINE_MARKERS):
            violations.append("简短寒暄中编造 Aura 日常或评价用户习惯")
        if len(response) > 72:
            violations.append("简短寒暄回复过长")
    if is_boredom_statement(user_text):
        if any(marker in response for marker in UNWANTED_BOREDOM_MARKERS):
            violations.append("无聊表达被自动纠正或安排任务")
        if len(response) > 96:
            violations.append("无聊表达回复过长")

    return ConversationRegressionResult(passed=not violations, violations=tuple(violations))


def is_simple_greeting(text: str) -> bool:
    """只将很短的日常招呼纳入严格的简短回复回归规则。"""

    return len(text) <= 8 and any(marker in text for marker in CASUAL_GREETING_MARKERS)


def is_boredom_statement(text: str) -> bool:
    """识别用户只是在陈述无聊而非明确寻求建议的情形。"""

    return "无聊" in text or text in {"不知道", "随便", "没事"}
