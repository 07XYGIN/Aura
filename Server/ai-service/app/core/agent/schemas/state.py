"""LangGraph 对话状态定义。"""

from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages


class AuraState(TypedDict, total=False):
    """在 LangGraph 节点之间传递的对话状态。"""

    messages: Annotated[list, add_messages]
    user_id: str
    attachment_context: str
    attachments: list[dict[str, Any]]
    turn_id: str
