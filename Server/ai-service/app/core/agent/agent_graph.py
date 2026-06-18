import logging
from datetime import datetime
from typing import Annotated, Any, Generator, TypedDict

from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph, add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Checkpointer

from app.core.config import llm
from app.core.emotion import derive_emotion_state, format_emotion_context
from .protocol import (
    content_event,
    derive_memory_candidate,
    derive_relationship_delta,
    emotion_event,
    memory_candidate_event,
    relationship_delta_event,
)
from .prompt import SYSTEM_PROMPT
from .tools.datetime_tools import get_current_datetime
from .tools.emotional_support import get_emotional_support_advice
from .tools.term_memory import save_memory
from .tools.proactive import draft_proactive_message, plan_daily_greetings
from .tools.relationship import get_relationship_status
from .tools.search_memory import search_memory_tool
from .tools.weather import get_weather


class AuraState(TypedDict):
    messages: Annotated[list, add_messages]
    emotion: dict


tools = [
    get_weather,
    search_memory_tool,
    get_current_datetime,
    get_relationship_status,
    get_emotional_support_advice,
    plan_daily_greetings,
    draft_proactive_message,
]

llm_with_tools = llm.bind_tools(tools)

tool_node = ToolNode(tools)


def call_model(state: AuraState) -> AuraState:
    system_prompt = SYSTEM_PROMPT + format_emotion_context(state.get("emotion"))
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        logging.info(
            "Aura model requested tools=%s",
            [tool_call.get("name") for tool_call in tool_calls],
        )
    else:
        logging.info("Aura model responded without tool call")
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


def aura_agent(
    human_prompt: str,
    user_id: str,
    emotion_state: dict | None = None,
    client_message_id: str | None = None,
) -> Generator[Any, None, None]:
    if aura is None:
        raise RuntimeError("Aura graph has not been initialized.")

    if emotion_state is None:
        emotion_state = derive_emotion_state(human_prompt).to_dict()
    logging.info("Aura agent start user_id=%s message_length=%s", user_id, len(human_prompt))

    config: RunnableConfig = {
        "recursion_limit": 6,
        "configurable": {
            "thread_id": user_id,
            "user_id": user_id,
        }
    }
    inputs = {
        "messages": [
            HumanMessage(
                content=human_prompt,
                additional_kwargs={
                    "client_message_id": client_message_id,
                } if client_message_id else {},
            ),
        ],
        "emotion": emotion_state,
    }

    memory_candidate = derive_memory_candidate(human_prompt, emotion_state)

    yield emotion_event(emotion_state)
    yield memory_candidate_event(memory_candidate)
    yield relationship_delta_event(derive_relationship_delta(human_prompt, emotion_state))

    save_memory_candidate_once(user_id, memory_candidate)

    for chunk, metadata in aura.stream(inputs, config, stream_mode="messages"):
        if chunk.content and metadata.get("langgraph_node") == "chat":
            yield content_event(str(chunk.content))
    logging.info("Aura agent end user_id=%s", user_id)


def save_memory_candidate_once(user_id: str, candidate: dict[str, Any]) -> None:
    if not candidate.get("save"):
        return

    content = candidate.get("content")
    if not isinstance(content, str) or not content.strip():
        return

    title = candidate.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "对话记忆"

    try:
        save_memory(
            user_id=user_id,
            content=content.strip(),
            title=title.strip(),
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        logging.info("Saved memory candidate once user_id=%s title=%s", user_id, title)
    except Exception:
        logging.exception("Failed to save memory candidate user_id=%s", user_id)


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
    seen_client_message_ids: set[str] = set()
    last_role: str | None = None
    last_content: str | None = None

    for msg in messages:
        if msg.type == "human":
            client_message_id = getattr(msg, "additional_kwargs", {}).get("client_message_id")
            content = msg.content
            if isinstance(client_message_id, str) and client_message_id:
                if client_message_id in seen_client_message_ids:
                    continue
                seen_client_message_ids.add(client_message_id)
            elif last_role == "user" and last_content == content:
                continue

            history.append({
                "id": getattr(msg, "id", None) or f"human-{len(history)}",
                "role": "user",
                "content": content
            })
            last_role = "user"
            last_content = content
        elif msg.type == "ai" and msg.content:
            content = msg.content
            if last_role == "aura" and last_content == content:
                continue

            history.append({
                "id": getattr(msg, "id", None) or f"ai-{len(history)}",
                "role": "aura",
                "content": content
            })
            last_role = "aura"
            last_content = content
    return history


def delete_history_message(user_id: str, message_id: str) -> bool:
    if aura is None:
        raise RuntimeError("Aura graph has not been initialized.")

    normalized_message_id = message_id.strip()
    if not normalized_message_id:
        return False

    config: RunnableConfig = {
        "configurable": {
            "thread_id": user_id,
        }
    }
    state = aura.get_state(config)
    messages = state.values.get("messages", []) if state and state.values else []

    if not any(getattr(msg, "id", None) == normalized_message_id for msg in messages):
        return False

    aura.update_state(
        config,
        {
            "messages": [
                RemoveMessage(id=normalized_message_id, content=""),
            ]
        },
    )
    return True


def clear_history(user_id: str) -> int:
    if aura is None:
        raise RuntimeError("Aura graph has not been initialized.")

    config: RunnableConfig = {
        "configurable": {
            "thread_id": user_id,
        }
    }
    state = aura.get_state(config)
    messages = state.values.get("messages", []) if state and state.values else []
    removable_count = len(messages)

    if removable_count == 0:
        return 0

    aura.update_state(
        config,
        {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES, content=""),
            ]
        },
    )
    return removable_count
