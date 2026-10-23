"""组装传给聊天模型的运行时系统提示词。"""

from __future__ import annotations

from typing import Any

from ..prompt import SYSTEM_PROMPT


def build_runtime_system_prompt(state: dict[str, Any]) -> str:
    """组合基础人设和本轮附件上下文。"""

    return "\n\n".join(
        part
        for part in (
            SYSTEM_PROMPT.strip(),
            "【本轮附件】\n" + (state.get("attachment_context") or "本轮没有附件。"),
        )
        if part
    )
