"""组装传给聊天模型的运行时系统提示词。"""

from __future__ import annotations

from typing import Any

from app.core.emotion import format_emotion_context

from ..conversation.time_context import format_time_context
from ..prompt import SYSTEM_PROMPT


def build_runtime_system_prompt(state: dict[str, Any]) -> str:
    """组合人设、时间、情绪和本轮附件上下文。"""

    return "\n\n".join(
        part
        for part in (
            SYSTEM_PROMPT.strip(),
            format_time_context(state.get("time_context")),
            "【情绪上下文】\n" + format_emotion_context(state.get("emotion")),
            "【本轮附件】\n" + (state.get("attachment_context") or "本轮没有附件。"),
        )
        if part
    )
