import logging
from typing import Annotated
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, add_messages, END
from ..config import llm
from .prompt import SYSTEM_PROMPT
from .tools.weather import get_weather

class AuraState(TypedDict):
    messages: Annotated[list, add_messages]

tools = [get_weather]

llm_with_tools = llm.bind_tools(tools)
tool_node = ToolNode(tools)

def call_model(state: AuraState) -> AuraState:
    logging.info("进入call_model")
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def should_continue(state: AuraState):
    logging.info("进入should_continue")
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

def build_graph():
    workflow = StateGraph(AuraState)
    workflow.add_node("chat", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("chat")
    workflow.add_conditional_edges("chat", should_continue)
    workflow.add_edge("tools", "chat")
    return workflow.compile()


aura = build_graph()


def aura_agent(human_prompt: str) -> str:
    result = aura.invoke({
        "messages": [HumanMessage(content=human_prompt)]
    })
    return result["messages"][-1].content