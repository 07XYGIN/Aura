import logging
from typing import Annotated, Any, Generator
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Checkpointer
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, add_messages, END
from .prompt import SYSTEM_PROMPT
from .tools.weather import get_weather
from .tools.memery import save_memory_tool
from .tools.search_memery import search_memory_tool
from app.core.config import llm
class AuraState(TypedDict):
    messages: Annotated[list, add_messages]

tools = [get_weather,save_memory_tool,search_memory_tool]

llm_with_tools = llm.bind_tools(tools)

# tool
tool_node = ToolNode(tools)

# node 1 : main -> ordinary node
def call_model(state: AuraState) -> AuraState:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# node2 : tool -> condition node
def should_continue(state: AuraState):
    logging.info(f"last_message: {state["messages"][-1]}")
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

def build_graph(checkpointers:Checkpointer):
    workflow = StateGraph(AuraState)
    workflow.add_node("chat", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("chat")
    workflow.add_conditional_edges("chat", should_continue)
    workflow.add_edge("tools", "chat")
    return workflow.compile(checkpointer=checkpointers)

aura: CompiledStateGraph = None

def aura_agent(human_prompt: str,userId:str) -> Generator[Any, Any, None]:
    config:RunnableConfig = {
        "configurable": {
            "thread_id": userId,
            "user_id":userId
        }
    }
    inputs = {"messages": [HumanMessage(content=human_prompt)]}

    for chunk, metadata in aura.stream(inputs, config, stream_mode="messages"):
        if chunk.content and metadata["langgraph_node"] == "chat":
            logging.info(f"Chunk: {chunk}")
            yield chunk.content

def get_history(user_id: str) -> list:
    """
        根据userid获取聊天记录
        :param user_id:str userId
        :return:list
    """
    config:RunnableConfig = {
        "configurable": {
            "thread_id": user_id,
        }
    }
    state = aura.get_state(config)
    if not state or not state.values:
        return []

    messages = state.values.get("messages", [])

    history = []
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