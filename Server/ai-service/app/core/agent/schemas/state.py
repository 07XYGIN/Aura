"""LangGraph 对话状态定义。"""

from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class AuraState(TypedDict, total=False):
    """在 LangGraph 节点之间传递的对话状态。"""

    messages: Annotated[list, add_messages]
    emotion: dict
    user_id: str
    memory_context: str
    attachment_context: str
    attachments: list[dict[str, Any]]
    city_adcode: str | None
    time_context: dict[str, Any]
    turn_id: str
    request_started_at: str
    last_reply_batch: dict[str, Any]
