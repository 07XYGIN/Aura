from typing import Annotated, Any, Generator, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph, add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Checkpointer

from app.core.config import llm
from .prompt import SYSTEM_PROMPT
from .tools.memory import save_memory_tool
from .tools.search_memory import search_memory_tool
from .tools.weather import get_weather


class AuraState(TypedDict):
    messages: Annotated[list, add_messages]


tools = [get_weather, save_memory_tool, search_memory_tool]

llm_with_tools = llm.bind_tools(tools)

tool_node = ToolNode(tools)


def call_model(state: AuraState) -> AuraState:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AuraState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_graph(checkpointer: Checkpointer) -> CompiledStateGraph:
    workflow = StateGraph(AuraState)
    workflow.add_node("chat", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("chat")
    workflow.add_conditional_edges("chat", should_continue)
    workflow.add_edge("tools", "chat")
    return workflow.compile(checkpointer=checkpointer)


aura: CompiledStateGraph | None = None


def aura_agent(human_prompt: str, user_id: str) -> Generator[Any, None, None]:
    if aura is None:
        raise RuntimeError("Aura graph has not been initialized.")

    config: RunnableConfig = {
        "configurable": {
            "thread_id": user_id,
            "user_id": user_id,
        }
    }
    inputs = {"messages": [HumanMessage(content=human_prompt)]}

    for chunk, metadata in aura.stream(inputs, config, stream_mode="messages"):
        if chunk.content and metadata.get("langgraph_node") == "chat":
            yield chunk.content


def get_history(user_id: str) -> list:
    if aura is None:
        raise RuntimeError("Aura graph has not been initialized.")

    config: RunnableConfig = {
        "configurable": {
            "thread_id": user_id,
        }
    }
    state = aura.get_state(config)
    if not state or not state.values:
        return []

    messages = state.values.get("messages", [])

    history: list[dict[str, str]] = []
    for msg in messages:
        if msg.type == "human":
            history.append({
                "role": "user",
                "content": msg.content
            })
        elif msg.type == "ai" and msg.content:
            history.append({
                "role": "aura",
                "content": msg.content
            })
    return history
