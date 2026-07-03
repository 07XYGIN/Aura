import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Generator, TypedDict
from uuid import uuid4
from zoneinfo import ZoneInfo

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph, add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Checkpointer

from app.core.attachment_store import format_attachment_context, load_attachments
from app.core.config import ensure_deepseek_api_key, llm, structured_reply_llm
from app.core.emotion import format_emotion_context
from .protocol import (
    assistant_message_event,
    content_event,
    emotion_event,
    memory_reference_event,
    memory_candidate_event,
    relationship_delta_event,
)
from .prompt import FEW_SHOT_EXAMPLES, STRUCTURED_REPLY_PROMPT, SYSTEM_PROMPT
from .structured_reply import parse_structured_reply, try_parse_structured_reply
from .turn_judge import format_turn_judgement_context, judge_turn, normalize_turn_judgement
from .tools.datetime_tools import get_current_datetime
from .tools.emotional_support import get_emotional_support_advice
from .tools.term_memory import format_memory_context, save_memory
from .tools.proactive import draft_proactive_message, plan_daily_greetings
from .tools.relationship import get_relationship_status
from .tools.search_memory import search_memory_tool
from .tools.weather import get_weather

SHORT_TERM_MESSAGE_WINDOW = 24
AURA_TIMEZONE = ZoneInfo("Asia/Shanghai")
MIN_REPLY_DELAY_MS = 500
MAX_REPLY_DELAY_MS = 2500
BASE_REPLY_DELAY_MS = 300
DELAY_PER_CHAR_MS = 50


class AuraState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    emotion: dict
    user_id: str
    memory_context: str
    attachment_context: str
    attachments: list[dict[str, Any]]
    city_adcode: str | None
    turn_judgement: dict[str, Any]
    time_context: dict[str, Any]
    turn_id: str
    request_started_at: str
    last_reply_batch: dict[str, Any]


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


def turn_judge(state: AuraState) -> AuraState:
    query = latest_human_text(state.get("messages", []))
    turn_judgement = normalize_turn_judgement(state.get("turn_judgement"), query)
    return {
        "emotion": turn_judgement["emotion"],
        "turn_judgement": turn_judgement,
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

    if tool_calls:
        return {"messages": [response]}

    draft_content = message_content_to_text(getattr(response, "content", ""))
    parsed_reply = try_parse_structured_reply(draft_content)
    if parsed_reply is not None:
        reply_messages, reply_batch = build_reply_messages_from_texts(parsed_reply, response, state)
    else:
        logging.warning("Aura first response was not valid structured JSON, falling back to reformatting call")
        structured_response = build_structured_reply_response(response, messages, state)
        reply_messages, reply_batch = build_reply_messages(structured_response, state)
    return {
        "messages": reply_messages,
        "last_reply_batch": reply_batch,
    }


def build_runtime_system_prompt(state: AuraState) -> str:
    return "\n\n".join(
        part for part in (
            SYSTEM_PROMPT.strip(),
            STRUCTURED_REPLY_PROMPT.strip(),
            FEW_SHOT_EXAMPLES.strip(),
            format_time_context(state.get("time_context")),
            format_location_context(state.get("city_adcode")),
            "【情绪上下文】\n" + format_emotion_context(state.get("emotion")),
            "【本轮判断】\n" + format_turn_judgement_context(state.get("turn_judgement")),
            "【可引用记忆】\n" + (state.get("memory_context") or "没有可引用记忆。"),
            "【本轮附件】\n" + (state.get("attachment_context") or "本轮没有附件。"),
        )
        if part
    )


def should_continue(state: AuraState) -> str:
    messages = state.get("messages") or []
    if not messages:
        return END

    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_graph(checkpointer: Checkpointer) -> CompiledStateGraph:
    workflow = StateGraph(AuraState)
    workflow.add_node("prepare_context", prepare_context)
    workflow.add_node("turn_judge", turn_judge)
    workflow.add_node("chat", call_model)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("prepare_context")
    workflow.add_edge("prepare_context", "turn_judge")
    workflow.add_edge("turn_judge", "chat")
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

    request_started_at = datetime.now(UTC)
    turn_id = client_message_id or f"turn-{uuid4()}"
    config: RunnableConfig = {
        "recursion_limit": 8,
        "configurable": {
            "thread_id": user_id,
            "user_id": user_id,
        }
    }
    previous_state = aura.get_state(config)
    time_context = build_time_context(previous_state.values.get("messages", []) if previous_state and previous_state.values else [], request_started_at)

    turn_judgement = judge_turn(human_prompt, emotion_state)
    emotion_state = turn_judgement["emotion"]
    attachments = load_attachments(user_id, attachment_ids)
    logging.info(
        "Aura agent start user_id=%s message_length=%s attachments=%s",
        user_id,
        len(human_prompt),
        len(attachments),
    )

    human_content = human_prompt.strip() or "（用户发送了附件）"
    inputs = {
        "messages": [
            HumanMessage(
                content=human_content,
                additional_kwargs={
                    **({"client_message_id": client_message_id} if client_message_id else {}),
                    **({"attachments": attachments} if attachments else {}),
                    "turn_id": turn_id,
                    "sent_at": request_started_at.isoformat(),
                },
            ),
        ],
        "emotion": emotion_state,
        "user_id": user_id,
        "attachments": attachments,
        "city_adcode": normalize_city_adcode(city_adcode),
        "turn_judgement": turn_judgement,
        "time_context": time_context,
        "turn_id": turn_id,
        "request_started_at": request_started_at.isoformat(),
    }

    memory_candidate = turn_judgement["memory_candidate"]

    yield emotion_event(emotion_state)
    yield memory_candidate_event(memory_candidate)
    yield relationship_delta_event(turn_judgement["relationship_delta"])

    save_memory_candidate_once(user_id, memory_candidate)

    memory_reference_reported = False
    raw_chat_parts: list[str] = []

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
            raw_chat_parts.append(str(chunk.content))

    reply_batch = get_latest_reply_batch(config, turn_id)
    if reply_batch:
        for message in reply_batch.get("messages", []):
            yield assistant_message_event(
                content=message["content"],
                message_id=message["message_id"],
                batch_id=message["batch_id"],
                batch_index=message["batch_index"],
                batch_total=message["batch_total"],
                delay_ms=message["delay_ms"],
                sent_at=message["sent_at"],
            )
    elif raw_chat_parts:
        for content in parse_structured_reply("".join(raw_chat_parts)):
            yield content_event(content)

    logging.info("Aura agent end user_id=%s", user_id)


def build_reply_messages(response: Any, state: AuraState) -> tuple[list[AIMessage], dict[str, Any]]:
    raw_content = message_content_to_text(getattr(response, "content", ""))
    reply_texts = parse_structured_reply(raw_content)
    return build_reply_messages_from_texts(reply_texts, response, state)


def build_reply_messages_from_texts(
    reply_texts: list[str],
    response: Any,
    state: AuraState,
) -> tuple[list[AIMessage], dict[str, Any]]:
    turn_id = state.get("turn_id") or f"turn-{uuid4()}"
    batch_id = str(uuid4())
    started_at = parse_iso_datetime(state.get("request_started_at")) or datetime.now(UTC)
    cumulative_delay_ms = 0
    total = len(reply_texts)
    ai_messages: list[AIMessage] = []
    batch_messages: list[dict[str, Any]] = []

    for index, content in enumerate(reply_texts):
        delay_ms = estimate_message_delay_ms(content)
        cumulative_delay_ms += delay_ms
        sent_at = started_at + timedelta(milliseconds=cumulative_delay_ms)
        message_id = f"ai-{turn_id}-{index}-{uuid4().hex[:8]}"
        metadata = {
            "turn_id": turn_id,
            "reply_batch_id": batch_id,
            "batch_id": batch_id,
            "batch_index": index,
            "batch_total": total,
            "delay_ms": delay_ms,
            "sent_at": sent_at.isoformat(),
            "raw_response_id": getattr(response, "id", None),
        }
        ai_messages.append(
            AIMessage(
                id=message_id,
                content=content,
                additional_kwargs=metadata,
                response_metadata=getattr(response, "response_metadata", {}) if index == 0 else {},
            )
        )
        batch_messages.append(
            {
                "message_id": message_id,
                "content": content,
                "batch_id": batch_id,
                "batch_index": index,
                "batch_total": total,
                "delay_ms": delay_ms,
                "sent_at": sent_at.isoformat(),
            }
        )

    return ai_messages, {
        "turn_id": turn_id,
        "batch_id": batch_id,
        "messages": batch_messages,
    }


def build_structured_reply_response(draft_response: Any, messages: list, state: AuraState) -> Any:
    draft_content = message_content_to_text(getattr(draft_response, "content", ""))

    if not draft_content.strip():
        return draft_response

    try:
        response = structured_reply_llm.invoke([
            SystemMessage(content=build_structured_formatter_prompt(draft_content)),
        ])
        if message_content_to_text(getattr(response, "content", "")).strip():
            return response
    except Exception:
        logging.exception("Aura structured reply formatting failed; falling back to draft response")

    return draft_response


def build_structured_formatter_prompt(draft_content: str) -> str:
    return "\n\n".join(
        part for part in (
            STRUCTURED_REPLY_PROMPT.strip(),
            (
                "【内部候选回复】\n"
                "下面是上一阶段根据当前对话、工具结果和 Aura 人设生成的候选回复。"
                "请只做结构化整理：保留原意和事实边界，按自然的念头/情绪单元拆成 1-4 条 messages。"
                "先判断自然应该发几条；默认 1 条，只有候选回复里确实有独立的短反应、停顿后的补充或转折时才拆成多条。"
                "解释后的追问、日常报备后的顺手提醒、记忆不确定时的补充说明，通常合并成 1 条。"
                "不要为了体现多气泡而固定拆成两条。不要新增候选回复里没有依据的事实，不要解释整理过程。\n"
                f"{draft_content.strip()}"
            ),
        )
        if part
    )


def estimate_message_delay_ms(content: str) -> int:
    delay_ms = BASE_REPLY_DELAY_MS + len(content.strip()) * DELAY_PER_CHAR_MS
    return max(MIN_REPLY_DELAY_MS, min(MAX_REPLY_DELAY_MS, delay_ms))


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if value:
                    parts.append(str(value))
        return "".join(parts)
    return str(content or "")


def get_latest_reply_batch(config: RunnableConfig, turn_id: str) -> dict[str, Any] | None:
    if aura is None:
        return None
    state = aura.get_state(config)
    values = state.values if state and state.values else {}
    batch = values.get("last_reply_batch")
    if isinstance(batch, dict) and batch.get("turn_id") == turn_id:
        return batch
    return None


def build_time_context(messages: list, current_time: datetime) -> dict[str, Any]:
    latest_sent_at = latest_message_sent_at(messages)
    local_time = current_time.astimezone(AURA_TIMEZONE)
    context: dict[str, Any] = {
        "current_time": current_time.isoformat(),
        "current_time_local": local_time.isoformat(),
        "current_time_text": format_chinese_datetime(local_time),
        "has_previous_message": latest_sent_at is not None,
    }

    if latest_sent_at is None:
        return context

    elapsed = current_time - latest_sent_at
    elapsed_seconds = max(0, int(elapsed.total_seconds()))
    context.update(
        {
            "previous_message_time": latest_sent_at.isoformat(),
            "elapsed_seconds": elapsed_seconds,
            "elapsed_text": format_elapsed(elapsed_seconds),
            "elapsed_level": elapsed_level(elapsed_seconds),
        }
    )
    return context


def latest_message_sent_at(messages: list) -> datetime | None:
    for msg in reversed(messages):
        additional_kwargs = getattr(msg, "additional_kwargs", {}) or {}
        sent_at = parse_iso_datetime(additional_kwargs.get("sent_at"))
        if sent_at:
            return sent_at
    return None


def parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_time_context(context: dict[str, Any] | None) -> str:
    if not context:
        return ""

    current_time_text = context.get("current_time_text") or "当前时间未知"
    if not context.get("has_previous_message"):
        return (
            "【时间上下文】\n"
            f"当前时间：{current_time_text}。\n"
            "当前可见历史里没有可靠的上一条消息时间。正常开启对话，不要假装记得刚刚才聊过。"
        )

    elapsed_text = context.get("elapsed_text") or "未知"
    level = context.get("elapsed_level")
    if level == "short":
        guidance = "这是短间隔，正常衔接即可，不要特意提时间。"
    elif level == "medium":
        guidance = "这是中等间隔，可以轻轻感知到对方隔了一阵子回来，但不要模板化提时间。"
    else:
        guidance = "这是长间隔，要自然体现时间流逝或重逢感，但不要每次都固定说“好久不见”。"

    return (
        "【时间上下文】\n"
        f"当前时间：{current_time_text}，距离上次对话已过去 {elapsed_text}。\n"
        f"{guidance}"
    )


def format_chinese_datetime(value: datetime) -> str:
    weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    return f"{value.year}年{value.month}月{value.day}日 {weekdays[value.weekday()]} {value:%H:%M}"


def format_elapsed(seconds: int) -> str:
    if seconds < 60:
        return "不到 1 分钟"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        return f"{hours} 小时 {remaining_minutes} 分钟" if remaining_minutes else f"{hours} 小时"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days} 天 {remaining_hours} 小时" if remaining_hours else f"{days} 天"


def elapsed_level(seconds: int) -> str:
    if seconds < 60 * 60:
        return "short"
    if seconds < 24 * 60 * 60:
        return "medium"
    return "long"


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
                "createdAt": additional_kwargs.get("sent_at"),
                "turnId": additional_kwargs.get("turn_id"),
            })
            last_role = "user"
            last_content = content
        elif msg.type == "ai" and msg.content:
            additional_kwargs = getattr(msg, "additional_kwargs", {}) or {}
            content = msg.content
            if (
                last_role == "aura"
                and last_content == content
                and not additional_kwargs.get("reply_batch_id")
            ):
                continue

            history.append({
                "id": getattr(msg, "id", None) or f"ai-{len(history)}",
                "role": "aura",
                "content": content,
                "createdAt": additional_kwargs.get("sent_at"),
                "turnId": additional_kwargs.get("turn_id"),
                "batchId": additional_kwargs.get("reply_batch_id") or additional_kwargs.get("batch_id"),
                "batchIndex": additional_kwargs.get("batch_index"),
                "batchTotal": additional_kwargs.get("batch_total"),
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
