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

from app.core.attachment_store import format_attachment_context, load_attachments
from app.core.config import ensure_deepseek_api_key, llm
from app.core.emotion import derive_emotion_state, format_emotion_context
from .memory_judge import judge_memory_candidate
from .protocol import (
    content_event,
    derive_relationship_delta,
    emotion_event,
    memory_reference_event,
    memory_candidate_event,
    relationship_delta_event,
)
from .prompt import SYSTEM_PROMPT
from .tools.datetime_tools import get_current_datetime
from .tools.emotional_support import get_emotional_support_advice
from .tools.term_memory import format_memory_context, save_memory
from .tools.proactive import draft_proactive_message, plan_daily_greetings
from .tools.relationship import get_relationship_status
from .tools.search_memory import search_memory_tool
from .tools.weather import get_weather

SHORT_TERM_MESSAGE_WINDOW = 24


class AuraState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    emotion: dict
    user_id: str
    memory_context: str
    attachment_context: str
    attachments: list[dict[str, Any]]
    city_adcode: str | None


tools = [
    search_memory_tool,
    get_current_datetime,
    get_relationship_status,
    get_emotional_support_advice,
    get_weather,
    plan_daily_greetings,
    draft_proactive_message,
]

llm_with_tools = llm.bind_tools(tools)

tool_node = ToolNode(tools)


def prepare_context(state: AuraState) -> AuraState:
    user_id = state.get("user_id") or ""
    query = latest_human_text(state.get("messages", []))
    memory_context = format_memory_context(user_id=user_id, query=query, k=5) if user_id else ""
    attachment_context = format_attachment_context(state.get("attachments", []))
    return {
        "memory_context": memory_context,
        "attachment_context": attachment_context,
    }


def call_model(state: AuraState) -> AuraState:
    ensure_deepseek_api_key()
    system_prompt = build_runtime_system_prompt(state)
    messages = [SystemMessage(content=system_prompt)] + trim_short_term_messages(state["messages"])
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


def build_runtime_system_prompt(state: AuraState) -> str:
    return "\n\n".join(
        part for part in (
            SYSTEM_PROMPT.strip(),
            format_location_context(state.get("city_adcode")),
            "【情绪上下文】\n" + format_emotion_context(state.get("emotion")),
            "【可引用记忆】\n" + (state.get("memory_context") or "没有可引用记忆。"),
            "【本轮附件】\n" + (state.get("attachment_context") or "本轮没有附件。"),
        )
        if part
    )


def should_continue(state: AuraState) -> str:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_graph(checkpointer: Checkpointer) -> CompiledStateGraph:
    workflow = StateGraph(AuraState)
    workflow.add_node("prepare_context", prepare_context)
    workflow.add_node("chat", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("prepare_context")
    workflow.add_edge("prepare_context", "chat")
    workflow.add_conditional_edges("chat", should_continue)
    workflow.add_edge("tools", "chat")
    return workflow.compile(checkpointer=checkpointer)


aura: CompiledStateGraph | None = None


def aura_agent(
    human_prompt: str,
    user_id: str,
    emotion_state: dict | None = None,
    client_message_id: str | None = None,
    attachment_ids: list[str] | None = None,
    city_adcode: str | None = None,
) -> Generator[Any, None, None]:
    if aura is None:
        raise RuntimeError("Aura graph has not been initialized.")

    if emotion_state is None:
        emotion_state = derive_emotion_state(human_prompt).to_dict()
    attachments = load_attachments(user_id, attachment_ids)
    logging.info(
        "Aura agent start user_id=%s message_length=%s attachments=%s",
        user_id,
        len(human_prompt),
        len(attachments),
    )

    config: RunnableConfig = {
        "recursion_limit": 6,
        "configurable": {
            "thread_id": user_id,
            "user_id": user_id,
        }
    }
    human_content = human_prompt.strip() or "（用户发送了附件）"
    inputs = {
        "messages": [
            HumanMessage(
                content=human_content,
                additional_kwargs={
                    **({"client_message_id": client_message_id} if client_message_id else {}),
                    **({"attachments": attachments} if attachments else {}),
                },
            ),
        ],
        "emotion": emotion_state,
        "user_id": user_id,
        "attachments": attachments,
        "city_adcode": normalize_city_adcode(city_adcode),
    }

    memory_candidate = judge_memory_candidate(human_prompt, emotion_state)

    yield emotion_event(emotion_state)
    yield memory_candidate_event(memory_candidate)
    yield relationship_delta_event(derive_relationship_delta(human_prompt, emotion_state))

    save_memory_candidate_once(user_id, memory_candidate)

    memory_reference_reported = False

    for chunk, metadata in aura.stream(inputs, config, stream_mode="messages"):
        if not memory_reference_reported:
            tool_calls = getattr(chunk, "tool_calls", None) or []
            for tool_call in tool_calls:
                if tool_call.get("name") == "search_memory_tool":
                    args = tool_call.get("args") or {}
                    query = args.get("query") if isinstance(args, dict) else None
                    memory_reference_reported = True
                    yield memory_reference_event(query if isinstance(query, str) else None)
                    break

        if (
            not memory_reference_reported
            and metadata.get("langgraph_node") == "tools"
            and getattr(chunk, "name", None) == "search_memory_tool"
        ):
            memory_reference_reported = True
            yield memory_reference_event()

        if chunk.content and metadata.get("langgraph_node") == "chat":
            yield content_event(str(chunk.content))
    logging.info("Aura agent end user_id=%s", user_id)


def save_memory_candidate_once(user_id: str, candidate: dict[str, Any]) -> None:
    if not candidate.get("save"):
        return

    memory_scope = candidate.get("memory_scope")
    if memory_scope not in {"long", "mid"}:
        return

    content = candidate.get("content")
    if not isinstance(content, str) or not content.strip():
        return

    title = candidate.get("title")
    if not isinstance(title, str) or not title.strip():
        title = "对话记忆" if memory_scope == "long" else "近期线索"

    try:
        save_memory(
            user_id=user_id,
            content=content.strip(),
            title=title.strip(),
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            memory_scope=memory_scope,
            confidence=candidate.get("confidence") if isinstance(candidate.get("confidence"), (float, int)) else None,
            signals=candidate.get("signals") if isinstance(candidate.get("signals"), list) else None,
        )
        logging.info("Saved %s memory candidate user_id=%s title=%s", memory_scope, user_id, title)
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

    history: list[dict[str, Any]] = []
    seen_client_message_ids: set[str] = set()
    last_role: str | None = None
    last_content: str | None = None

    for msg in messages:
        if msg.type == "human":
            additional_kwargs = getattr(msg, "additional_kwargs", {})
            client_message_id = additional_kwargs.get("client_message_id")
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
                "content": content,
                "attachments": public_history_attachments(additional_kwargs.get("attachments")),
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


def trim_short_term_messages(messages: list) -> list:
    if len(messages) <= SHORT_TERM_MESSAGE_WINDOW:
        return messages
    return messages[-SHORT_TERM_MESSAGE_WINDOW:]


def latest_human_text(messages: list) -> str:
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            content = getattr(msg, "content", "")
            return content if isinstance(content, str) else str(content)
    return ""


def normalize_city_adcode(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()
    return value if len(value) == 6 and value.isdigit() else None


def format_location_context(city_adcode: str | None) -> str:
    normalized = normalize_city_adcode(city_adcode)
    if normalized:
        return (
            "【位置上下文】\n"
            f"本轮已获得用户城市 adcode：{normalized}。"
            "只有用户主动询问天气或明确要求根据天气安排时，才可调用 get_weather(city_adcode=该 adcode)。"
        )

    return (
        "【位置上下文】\n"
        "本轮没有可靠城市 adcode。用户询问天气时，不要猜城市或默认北京；先自然确认城市。"
    )


def public_history_attachments(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("fileName"), str):
            names.append(item["fileName"])
    return names
