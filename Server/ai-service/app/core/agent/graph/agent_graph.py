"""Aura 单回合聊天图的状态、节点和流程组装。"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from app.core.attachment_store import format_attachment_context
from ..schemas.state import AuraState
from .model_node import generate_chat_response


def prepare_context(state: AuraState) -> AuraState:
    """把本轮附件转换成模型可读的文字上下文。"""

    return {"attachment_context": format_attachment_context(state.get("attachments", []))}


def call_model(state: AuraState) -> AuraState:
    """调用聊天模型，并把最终文本转换成可分批发送的 AIMessage。"""

    return generate_chat_response(state)


def build_graph(checkpointer: Checkpointer) -> CompiledStateGraph:
    """构建带持久化短期上下文的聊天图。

    Args:
        checkpointer: 用于持久化每个用户线程状态的 LangGraph checkpointer。

    Returns:
        可通过 LangGraph checkpointer 按用户线程恢复消息历史的图。
    """

    workflow = StateGraph(AuraState)
    workflow.add_node("prepare_context", prepare_context)
    workflow.add_node("chat", call_model)
    workflow.set_entry_point("prepare_context")
    workflow.add_edge("prepare_context", "chat")
    workflow.add_edge("chat", END)
    return workflow.compile(checkpointer=checkpointer)
