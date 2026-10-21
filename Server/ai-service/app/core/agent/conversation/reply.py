"""把模型回复整理为聊天消息和 SSE 批次。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage, SystemMessage

from app.core.config import structured_reply_llm
from app.core.reply_timing_state import store_reply_timing_state

from .message_utils import message_content_to_text as _message_content_to_text
from .time_context import parse_iso_datetime
from ..prompt import STRUCTURED_REPLY_PROMPT
from ..schemas.structured_reply import parse_structured_reply

MIN_REPLY_DELAY_MS = 500
MAX_REPLY_DELAY_MS = 2500
BASE_REPLY_DELAY_MS = 300
DELAY_PER_CHAR_MS = 50


class ReplyState(TypedDict, total=False):
    """构造回复批次所需的最小回合状态。"""

    user_id: str
    turn_id: str
    request_started_at: str


def build_reply_messages(response: Any, state: ReplyState) -> tuple[list[AIMessage], dict[str, Any]]:
    """解析模型回复，并生成图消息和客户端批次。"""

    raw_content = message_content_to_text(getattr(response, "content", ""))
    return build_reply_messages_from_texts(parse_structured_reply(raw_content), response, state)


def build_reply_messages_from_texts(
    reply_texts: list[str],
    response: Any,
    state: ReplyState,
) -> tuple[list[AIMessage], dict[str, Any]]:
    """为回复气泡添加 ID、发送延迟、时间戳和批次元数据。"""

    turn_id = state.get("turn_id") or f"turn-{uuid4()}"
    batch_id = str(uuid4())
    started_at = parse_iso_datetime(state.get("request_started_at")) or datetime.now(UTC)
    cumulative_delay_ms = 0
    total = len(reply_texts)
    ai_messages: list[AIMessage] = []
    batch_messages: list[dict[str, Any]] = []

    for index, content in enumerate(reply_texts):
        delay_ms = estimate_message_delay_ms(content)
        cumulative_delay_ms += delay_ms
        sent_at = started_at + timedelta(milliseconds=cumulative_delay_ms)
        message_id = f"ai-{turn_id}-{index}-{uuid4().hex[:8]}"
        metadata = {
            "turn_id": turn_id,
            "reply_batch_id": batch_id,
            "batch_id": batch_id,
            "batch_index": index,
            "batch_total": total,
            "delay_ms": delay_ms,
            "sent_at": sent_at.isoformat(),
            "raw_response_id": getattr(response, "id", None),
        }
        ai_messages.append(
            AIMessage(
                id=message_id,
                content=content,
                additional_kwargs=metadata,
                response_metadata=getattr(response, "response_metadata", {}) if index == 0 else {},
            )
        )
        batch_messages.append(
            {
                "message_id": message_id,
                "content": content,
                "batch_id": batch_id,
                "batch_index": index,
                "batch_total": total,
                "delay_ms": delay_ms,
                "sent_at": sent_at.isoformat(),
            }
        )

    reply_batch = {"turn_id": turn_id, "batch_id": batch_id, "messages": batch_messages}
    store_reply_timing_state(state.get("user_id"), reply_batch)
    return ai_messages, reply_batch


def build_structured_reply_response(draft_response: Any, messages: list, state: ReplyState) -> Any:
    """修复格式不正确的结构化回复；失败时保留原始草稿。"""

    draft_content = message_content_to_text(getattr(draft_response, "content", ""))
    if not draft_content.strip():
        return draft_response

    try:
        response = structured_reply_llm.invoke(
            [SystemMessage(content=build_structured_formatter_prompt(draft_content))]
        )
        if message_content_to_text(getattr(response, "content", "")).strip():
            return response
    except Exception:
        logging.exception("Aura 结构化回复整理失败，回退到原始草稿")
    return draft_response


def build_structured_formatter_prompt(draft_content: str) -> str:
    """生成只整理消息边界、不改变原意和事实的格式化提示词。"""

    return "\n\n".join(
        part
        for part in (
            STRUCTURED_REPLY_PROMPT.strip(),
            (
                "【内部候选回复】\n"
                "下面是上一阶段根据当前对话、工具结果和 Aura 人设生成的候选回复。"
                "请只做结构化整理：保留原意和事实边界，按自然的念头/情绪单元拆成 1-4 条 messages。"
                "先判断自然应该发几条；默认 1 条，只有候选回复里确实有独立的短反应、停顿后的补充或转折时才拆成多条。"
                "解释后的追问、日常报备后的顺手提醒、记忆不确定时的补充说明，通常合并成 1 条。"
                "不要为了体现多气泡而固定拆成两条。不要新增候选回复里没有依据的事实，不要解释整理过程。\n"
                f"{draft_content.strip()}"
            ),
        )
        if part
    )


def estimate_message_delay_ms(content: str) -> int:
    """按文本长度估算气泡延迟，并限制在 0.5 到 2.5 秒。"""

    delay_ms = BASE_REPLY_DELAY_MS + len(content.strip()) * DELAY_PER_CHAR_MS
    return max(MIN_REPLY_DELAY_MS, min(MAX_REPLY_DELAY_MS, delay_ms))


def message_content_to_text(content: Any) -> str:
    """按回复链路原有规则连接 LangChain 消息内容块。"""

    return _message_content_to_text(content, separator="", strip=False)
