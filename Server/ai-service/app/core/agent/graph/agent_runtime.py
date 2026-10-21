"""保存应用生命周期中初始化的共享 LangGraph 实例。"""

from langgraph.graph.state import CompiledStateGraph

graph: CompiledStateGraph | None = None
