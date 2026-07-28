"""基于 LangGraph interrupt 的持久化人工审批子图。"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer, Command, interrupt


class ApprovalState(TypedDict, total=False):
    """审批子图只保存待审批效果、公开提示和最终决定。"""

    request: dict[str, Any]
    decision: dict[str, Any]


approval_graph: CompiledStateGraph | None = None


def build_approval_subgraph(checkpointer: Checkpointer) -> CompiledStateGraph:
    """构建在用户输入前暂停、并能由 ``Command`` 恢复的审批子图。"""

    workflow = StateGraph(ApprovalState)
    workflow.add_node("await_human_approval", await_human_approval)
    workflow.add_edge(START, "await_human_approval")
    workflow.add_edge("await_human_approval", END)
    return workflow.compile(checkpointer=checkpointer)


def configure_approval_subgraph(checkpointer: Checkpointer) -> None:
    """在 FastAPI 生命周期内绑定与主图相同的持久化 checkpointer。"""

    global approval_graph
    approval_graph = build_approval_subgraph(checkpointer)


def await_human_approval(state: ApprovalState) -> ApprovalState:
    """暴露公开审批摘要，并在恢复时接受批准或拒绝。"""

    request = state.get("request") if isinstance(state.get("request"), dict) else {}
    public_payload = request.get("public") if isinstance(request.get("public"), dict) else {}
    decision = interrupt(public_payload)
    return {"decision": normalize_decision(decision)}


def start_approval(request: dict[str, Any], config: dict[str, Any]) -> bool:
    """创建审批检查点；返回是否成功进入等待用户输入的状态。"""

    if approval_graph is None:
        return False
    result = approval_graph.invoke({"request": request}, config)
    return bool(isinstance(result, dict) and result.get("__interrupt__"))


def resume_approval(
    approval_id: str,
    user_id: str,
    approved: bool,
) -> dict[str, Any] | None:
    """恢复指定审批并返回受信任的内部请求与标准化结果。"""

    if approval_graph is None:
        return None
    config = approval_config(user_id, approval_id)
    state = approval_graph.get_state(config)
    values = state.values if state and state.values else {}
    request = values.get("request") if isinstance(values.get("request"), dict) else None
    if request is None or values.get("decision"):
        return None
    owner = request.get("user_id")
    if owner != user_id:
        return None

    approval_graph.invoke(Command(resume={"approved": approved}), config)
    resolved = approval_graph.get_state(config)
    resolved_values = resolved.values if resolved and resolved.values else {}
    decision = resolved_values.get("decision")
    if not isinstance(decision, dict):
        return None
    return {"request": request, "decision": decision}


def approval_config(user_id: str, approval_id: str) -> dict[str, Any]:
    """为每条审批生成独立而可重放的 LangGraph 线程。"""

    return {
        "configurable": {
            "thread_id": f"approval:{user_id}:{approval_id}",
            "user_id": user_id,
        }
    }


def normalize_decision(value: Any) -> dict[str, Any]:
    """把前端恢复值归一化为明确布尔决定。"""

    if isinstance(value, dict):
        approved = value.get("approved") is True
    else:
        approved = value is True
    return {"approved": approved}
