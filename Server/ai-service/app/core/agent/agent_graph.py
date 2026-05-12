from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, add_messages, END
from ..config import llm
from .prompt import SYSTEM_PROMPT


class AuraState(TypedDict):
    messages: Annotated[list, add_messages]


def call_model(state: AuraState) -> AuraState:
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    print(messages)
    response = llm.invoke(messages)
    return {"messages": [response]}


def build_graph():
    workflow = StateGraph(AuraState)
    workflow.add_node("chat", call_model)
    workflow.set_entry_point("chat")
    workflow.add_edge("chat", END)
    return workflow.compile()


aura = build_graph()


def aura_agent(human_prompt: str) -> str:
    result = aura.invoke({
        "messages": [HumanMessage(content=human_prompt)]
    })
    return result["messages"][-1].content