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
    turn_judgement: dict[str, Any]
    time_context: dict[str, Any]
    self_changelog_context: dict[str, Any]
    turn_id: str
    request_started_at: str
    last_reply_batch: dict[str, Any]
    relationship_context: str
    relationship_snapshot: dict[str, Any]
    relationship_dynamics: dict[str, Any]
    aura_internal_state: dict[str, Any]
    aura_impulse: dict[str, Any]
    relationship_actions: dict[str, Any]
    relationship_item_usages: dict[str, Any]
    continuity_state_context: str
    reply_presence: dict[str, Any]
    live2d_state: dict[str, Any]
    pending_approvals: list[dict[str, Any]]
