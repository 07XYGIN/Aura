"""Aura 主对话图、回复编排和 LangGraph 历史读写。"""

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
from langsmith import traceable

from app.core.attachment_store import format_attachment_context, load_attachments
from app.core.config import llm, structured_reply_llm
from app.core.continuity.context import load_relationship_context_sync
from app.core.continuity.capsules import (
    capture_conditional_candidates_sync,
    trigger_keyword_messages_sync,
)
from app.core.continuity.knowledge import (
    capture_relationship_knowledge_sync,
    mark_relationship_items_used_sync,
)
from app.core.continuity.mind import (
    cancel_pending_second_thoughts_sync,
    consume_relevant_offline_thought_sync,
    format_offline_thought_prompt,
    schedule_second_thought_sync,
)
from app.core.continuity.state import (
    apply_scene_message_sync,
    capture_emotional_afterglow_sync,
    load_continuity_state_context_sync,
)
from app.core.continuity.service import (
    apply_reply_thread_actions_sync,
    capture_relationship_candidates_sync,
)
from app.core.emotion import format_emotion_context
from app.core.reply_timing_state import store_reply_timing_state
from .protocol import (
    assistant_message_event,
    content_event,
    emotion_event,
    memory_reference_event,
    memory_candidate_event,
)
from .prompt import FEW_SHOT_EXAMPLES, STRUCTURED_REPLY_PROMPT, SYSTEM_PROMPT
from .structured_reply import (
    parse_structured_reply,
    try_parse_structured_reply_payload,
)
from .self_changelog import load_self_changelog_context_sync, mark_self_changelog_reacted_sync
from .judges.turn import format_turn_judgement_context, judge_turn, normalize_turn_judgement
from .tools.registry import CHAT_TOOLS
from app.core.memory.service import save_memory
from app.core.pet.context import load_pet_context_sync

SHORT_TERM_MESSAGE_WINDOW = 24
AURA_TIMEZONE = ZoneInfo("Asia/Shanghai")
MIN_REPLY_DELAY_MS = 500
MAX_REPLY_DELAY_MS = 2500
BASE_REPLY_DELAY_MS = 300
DELAY_PER_CHAR_MS = 50


class AuraState(TypedDict, total=False):
    """在 LangGraph 节点之间传递的对话状态。"""

    messages: Annotated[list, add_messages]
    emotion: dict
    user_id: str
    memory_context: str
    attachment_context: str
    attachments: list[dict[str, Any]]
    city_adcode: str | None
    turn_judgement: dict[str, Any]
    time_context: dict[str, Any]
    self_changelog_context: dict[str, Any]
    turn_id: str
    request_started_at: str
    last_reply_batch: dict[str, Any]
    pet_context: str
    relationship_context: str
    relationship_actions: dict[str, Any]
    relationship_item_usages: dict[str, Any]
    continuity_state_context: str


tools = CHAT_TOOLS

llm_with_tools = llm.bind_tools(tools)

tool_node = ToolNode(tools)


@traceable(name="aura_prepare_context")
def prepare_context(state: AuraState) -> AuraState:
    """把附件转换成提示词上下文，并初始化按需记忆检索说明。"""

    attachment_context = format_attachment_context(state.get("attachments", []))
    return {
        "memory_context": (
            "本轮没有预加载历史记忆。"
            "只有当前回复确实需要过去信息时，才调用 search_memory_tool。"
        ),
        "attachment_context": attachment_context,
    }


@traceable(name="aura_turn_judge_node")
def turn_judge(state: AuraState) -> AuraState:
    """规范化预计算的回合判断，向后续节点提供情绪和回复模式。"""

    query = latest_human_text(state.get("messages", []))
    turn_judgement = normalize_turn_judgement(state.get("turn_judgement"), query)
    return {
        "emotion": turn_judgement["emotion"],
        "turn_judgement": turn_judgement,
    }


@traceable(name="aura_final_response_generation")
def call_model(state: AuraState) -> AuraState:
    """调用带工具的主模型，并把最终文本转换成可分批发送的 AIMessage。"""

    system_prompt = build_runtime_system_prompt(state)
    messages = [SystemMessage(content=system_prompt)] + trim_short_term_messages(state["messages"])
    response = llm_with_tools.invoke(messages)
    tool_calls = getattr(response, "tool_calls", None) or []
    if tool_calls:
        logging.info(
            "Aura 请求调用工具 tools=%s",
            [tool_call.get("name") for tool_call in tool_calls],
        )
    else:
        logging.info("Aura 未调用工具，直接生成回复")

    if tool_calls:
        return {
            "messages": [response],
            "relationship_actions": {
                "turn_id": state.get("turn_id"),
                "items": [],
            },
            "relationship_item_usages": {
                "turn_id": state.get("turn_id"),
                "items": [],
            },
        }

    draft_content = message_content_to_text(getattr(response, "content", ""))
    parsed_payload = try_parse_structured_reply_payload(draft_content)
    if parsed_payload is not None:
        reply_messages, reply_batch = build_reply_messages_from_texts(parsed_payload.messages, response, state)
    else:
        logging.warning("Aura 首次回复不是有效的结构化 JSON，尝试重新整理格式")
        structured_response = build_structured_reply_response(response, messages, state)
        reply_messages, reply_batch = build_reply_messages(structured_response, state)
        parsed_payload = try_parse_structured_reply_payload(
            message_content_to_text(getattr(structured_response, "content", ""))
        )
    relationship_actions = [
        action.model_dump()
        for action in (parsed_payload.thread_actions if parsed_payload is not None else [])
    ]
    relationship_item_usages = [
        usage.model_dump()
        for usage in (parsed_payload.item_usages if parsed_payload is not None else [])
    ]
    return {
        "messages": reply_messages,
        "last_reply_batch": reply_batch,
        "relationship_actions": {
            "turn_id": state.get("turn_id"),
            "items": relationship_actions,
        },
        "relationship_item_usages": {
            "turn_id": state.get("turn_id"),
            "items": relationship_item_usages,
        },
    }


def build_runtime_system_prompt(state: AuraState) -> str:
    """组合静态人设、动态时间/情绪/记忆上下文和最终输出格式要求。"""

    return "\n\n".join(
        part for part in (
            SYSTEM_PROMPT.strip(),
            FEW_SHOT_EXAMPLES.strip(),
            format_time_context(state.get("time_context")),
            format_self_changelog_context(state.get("self_changelog_context")),
            format_location_context(state.get("city_adcode")),
            "【情绪上下文】\n" + format_emotion_context(state.get("emotion")),
            "【本轮判断】\n" + format_turn_judgement_context(state.get("turn_judgement")),
            "【可引用记忆】\n" + (state.get("memory_context") or "没有可引用记忆。"),
            "【本轮附件】\n" + (state.get("attachment_context") or "本轮没有附件。"),
            state.get("relationship_context") or "",
            state.get("pet_context") or "",
            state.get("continuity_state_context") or "",
            STRUCTURED_REPLY_PROMPT.strip(),
        )
        if part
    )


def should_continue(state: AuraState) -> str:
    """根据最后一条 AI 消息是否包含工具调用，决定进入 tools 节点或结束。"""

    messages = state.get("messages") or []
    if not messages:
        return END

    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_graph(checkpointer: Checkpointer) -> CompiledStateGraph:
    """构建并编译 Aura LangGraph。

    Args:
        checkpointer: 用于持久化每个用户线程状态的 LangGraph checkpointer。

    Returns:
        已连接上下文准备、回合判断、聊天和工具节点的可执行图。
    """

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
    """执行一轮 Aura 对话并按顺序产出 SSE 业务事件。

    Args:
        human_prompt: 用户本轮发送的文本；只有附件时可以为空。
        user_id: 同时作为 LangGraph ``thread_id`` 使用的唯一用户标识。
        emotion_state: 上游可选的情绪回退结果。
        client_message_id: 客户端消息 ID；用于幂等和关联回复批次。
        attachment_ids: 本轮需要加载的附件 ID。
        city_adcode: 可选的六位高德城市编码，仅供天气工具使用。

    Yields:
        情绪、记忆候选、记忆引用和最终 Aura 消息等 SSE 事件字典。

    Raises:
        RuntimeError: 对话图尚未在应用生命周期中初始化。
    """

    if aura is None:
        raise RuntimeError("Aura 对话图尚未初始化")

    request_started_at = datetime.now(UTC)
    turn_id = client_message_id or f"turn-{uuid4()}"
    normalized_city_adcode = normalize_city_adcode(city_adcode)
    config: RunnableConfig = {
        "recursion_limit": 8,
        "tags": ["aura", "sse"],
        "metadata": {
            "user_id": user_id,
            "turn_id": turn_id,
            "client_message_id": client_message_id,
            "attachment_count": len(attachment_ids or []),
            "city_adcode": normalized_city_adcode,
        },
        "configurable": {
            "thread_id": user_id,
            "user_id": user_id,
        }
    }
    previous_state = aura.get_state(config)
    previous_messages = previous_state.values.get("messages", []) if previous_state and previous_state.values else []
    time_context = build_time_context(previous_messages, request_started_at)
    cancel_pending_second_thoughts_sync(user_id, now=request_started_at)
    offline_thought = consume_relevant_offline_thought_sync(
        user_id,
        human_prompt,
        now=request_started_at,
    )
    self_changelog_context = load_self_changelog_context_sync()
    relationship_context = load_relationship_context_sync(user_id)
    apply_scene_message_sync(
        user_id,
        human_prompt,
        client_message_id,
        now=request_started_at,
    )
    continuity_state = load_continuity_state_context_sync(user_id, now=request_started_at)
    pet_context = load_pet_context_sync(user_id)

    turn_judgement = judge_turn(
        human_prompt,
        emotion_state,
        recent_messages=previous_messages,
        relationship_context=relationship_context["judge_context"],
    )
    conditional_candidates = turn_judgement["memory_candidate"].get("conditional_messages") or []
    conditional_messages_created: list[dict[str, Any]] = []
    if conditional_candidates and client_message_id:
        conditional_messages_created = capture_conditional_candidates_sync(
            user_id,
            conditional_candidates,
            source_message_id=client_message_id,
            source_turn_id=turn_id,
            now=request_started_at,
        )
    elif conditional_candidates:
        logging.warning(
            "本轮识别到条件消息候选，但缺少稳定 clientMessageId，已跳过持久化 user_id=%s",
            user_id,
        )
    turn_judgement["conditional_messages_created"] = [
        {
            "id": item["id"],
            "messageType": item["messageType"],
            "conditionType": item["conditionType"],
            "title": item["title"],
            "deliverAt": item["deliverAt"],
        }
        for item in conditional_messages_created
    ]
    emotion_state = turn_judgement["emotion"]
    if not turn_judgement["risk_signal"].get("requires_safety_gate"):
        capture_emotional_afterglow_sync(
            user_id,
            emotion_state,
            client_message_id,
            now=request_started_at,
        )
    attachments = load_attachments(user_id, attachment_ids)
    logging.info(
        "Aura 对话开始 user_id=%s message_length=%s attachments=%s",
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
        "city_adcode": normalized_city_adcode,
        "turn_judgement": turn_judgement,
        "time_context": time_context,
        "self_changelog_context": {
            "entry_id": self_changelog_context.entry_id,
            "text": self_changelog_context.text,
        },
        "turn_id": turn_id,
        "request_started_at": request_started_at.isoformat(),
        "pet_context": pet_context,
        "relationship_context": relationship_context["prompt_context"],
        "relationship_actions": {"turn_id": turn_id, "items": []},
        "relationship_item_usages": {"turn_id": turn_id, "items": []},
        "continuity_state_context": "\n\n".join(
            part
            for part in (
                continuity_state["prompt_context"],
                format_offline_thought_prompt(offline_thought),
            )
            if part
        ),
    }

    memory_candidate = turn_judgement["memory_candidate"]

    yield emotion_event(emotion_state)
    yield memory_candidate_event(memory_candidate)

    memory_reference_reported = False
    memory_save_tool_called = False
    raw_chat_parts: list[str] = []

    for chunk, metadata in aura.stream(inputs, config, stream_mode="messages"):
        tool_calls = getattr(chunk, "tool_calls", None) or []
        for tool_call in tool_calls:
            if tool_call.get("name") == "save_memory_tool":
                memory_save_tool_called = True

        if not memory_reference_reported:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name")
                if tool_name == "search_memory_tool":
                    args = tool_call.get("args") or {}
                    query = args.get("query") if isinstance(args, dict) else None
                    memory_reference_reported = True
                    yield memory_reference_event(query if isinstance(query, str) else None)
                    break

        if metadata.get("langgraph_node") == "tools" and getattr(chunk, "name", None) == "save_memory_tool":
            memory_save_tool_called = True

        if (
            not memory_reference_reported
            and metadata.get("langgraph_node") == "tools"
            and getattr(chunk, "name", None) == "search_memory_tool"
        ):
            memory_reference_reported = True
            yield memory_reference_event()

        if chunk.content and metadata.get("langgraph_node") == "chat":
            raw_chat_parts.append(str(chunk.content))

    if not memory_save_tool_called:
        save_memory_candidate_once(user_id, memory_candidate)

    relationship_candidates = memory_candidate.get("relationship_threads")
    if relationship_candidates and client_message_id:
        capture_relationship_candidates_sync(
            user_id,
            relationship_candidates,
            source_text=human_prompt,
            source_message_id=client_message_id,
            source_turn_id=turn_id,
        )
    elif relationship_candidates:
        logging.warning(
            "本轮识别到关系线程候选，但缺少稳定 clientMessageId，已跳过持久化 user_id=%s",
            user_id,
        )

    relationship_item_candidates = memory_candidate.get("relationship_items")
    relationship_chapter_candidate = memory_candidate.get("relationship_chapter")
    if (relationship_item_candidates or relationship_chapter_candidate) and client_message_id:
        capture_relationship_knowledge_sync(
            user_id,
            relationship_item_candidates,
            relationship_chapter_candidate,
            source_message_id=client_message_id,
            source_turn_id=turn_id,
        )
    elif relationship_item_candidates or relationship_chapter_candidate:
        logging.warning(
            "本轮识别到关系知识候选，但缺少稳定 clientMessageId，已跳过持久化 user_id=%s",
            user_id,
        )

    reply_batch = get_latest_reply_batch(config, turn_id)
    relationship_actions = get_latest_relationship_actions(config, turn_id)
    relationship_item_usages = get_latest_relationship_item_usages(config, turn_id)
    if reply_batch and relationship_actions:
        apply_reply_thread_actions_sync(
            user_id,
            relationship_actions,
            relationship_context["items"],
            turn_id=turn_id,
        )
    if reply_batch and relationship_item_usages:
        mark_relationship_items_used_sync(
            user_id,
            relationship_context["knowledge_items"],
            relationship_item_usages,
            source_turn_id=turn_id,
        )
    if reply_batch:
        if client_message_id:
            trigger_keyword_messages_sync(
                user_id,
                human_prompt,
                event_id=f"chat:{client_message_id}",
                now=request_started_at,
            )
        schedule_second_thought_sync(
            user_id,
            human_prompt,
            "\n".join(
                str(message.get("content") or "")
                for message in reply_batch.get("messages", [])
                if isinstance(message, dict)
            ),
            turn_judgement,
            client_message_id,
            turn_id,
            now=request_started_at,
        )
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
        mark_self_changelog_reacted_sync(self_changelog_context.entry_id)
    elif raw_chat_parts:
        for content in parse_structured_reply("".join(raw_chat_parts)):
            yield content_event(content)
        mark_self_changelog_reacted_sync(self_changelog_context.entry_id)

    logging.info("Aura 对话结束 user_id=%s", user_id)


def build_reply_messages(response: Any, state: AuraState) -> tuple[list[AIMessage], dict[str, Any]]:
    """解析模型回复，并生成 LangGraph 消息及前端发送批次。"""

    raw_content = message_content_to_text(getattr(response, "content", ""))
    reply_texts = parse_structured_reply(raw_content)
    return build_reply_messages_from_texts(reply_texts, response, state)


def build_reply_messages_from_texts(
    reply_texts: list[str],
    response: Any,
    state: AuraState,
) -> tuple[list[AIMessage], dict[str, Any]]:
    """为每个回复气泡生成 ID、模拟延迟、发送时间和批次元数据。

    Returns:
        ``(AIMessage 列表, reply_batch 字典)``；批次同时写入临时发送状态。
    """

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

    reply_batch = {
        "turn_id": turn_id,
        "batch_id": batch_id,
        "messages": batch_messages,
    }
    store_reply_timing_state(state.get("user_id"), reply_batch)
    return ai_messages, reply_batch


def build_structured_reply_response(draft_response: Any, messages: list, state: AuraState) -> Any:
    """当主模型未返回合法 JSON 时，用低温模型整理格式；失败则保留原草稿。"""

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
        logging.exception("Aura 结构化回复整理失败，回退到原始草稿")

    return draft_response


def build_structured_formatter_prompt(draft_content: str) -> str:
    """生成只允许整理消息边界、不得改写事实的格式化提示词。"""

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
    """按文本长度估算单个气泡延迟，并限制在 0.5 到 2.5 秒。"""

    delay_ms = BASE_REPLY_DELAY_MS + len(content.strip()) * DELAY_PER_CHAR_MS
    return max(MIN_REPLY_DELAY_MS, min(MAX_REPLY_DELAY_MS, delay_ms))


def message_content_to_text(content: Any) -> str:
    """把 LangChain 的字符串或多段内容统一转换为纯文本。"""

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
    """读取当前图状态中属于指定回合的最新回复批次。"""

    if aura is None:
        return None
    state = aura.get_state(config)
    values = state.values if state and state.values else {}
    batch = values.get("last_reply_batch")
    if isinstance(batch, dict) and batch.get("turn_id") == turn_id:
        return batch
    return None


def get_latest_relationship_actions(config: RunnableConfig, turn_id: str) -> list[dict[str, Any]]:
    """读取当前回合主回复返回的、已通过结构化白名单校验的线程动作。"""

    if aura is None:
        return []
    state = aura.get_state(config)
    values = state.values if state and state.values else {}
    action_batch = values.get("relationship_actions")
    if not isinstance(action_batch, dict) or action_batch.get("turn_id") != turn_id:
        return []
    items = action_batch.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def get_latest_relationship_item_usages(
    config: RunnableConfig,
    turn_id: str,
) -> list[dict[str, Any]]:
    """读取当前回合主回复中通过白名单校验的关系物件使用回执。"""

    if aura is None:
        return []
    state = aura.get_state(config)
    values = state.values if state and state.values else {}
    usage_batch = values.get("relationship_item_usages")
    if not isinstance(usage_batch, dict) or usage_batch.get("turn_id") != turn_id:
        return []
    items = usage_batch.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def build_time_context(messages: list, current_time: datetime) -> dict[str, Any]:
    """根据当前时间和最近消息时间生成对话间隔上下文。"""

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
    """从后向前查找最近一条带 ``sent_at`` 元数据的消息时间。"""

    for msg in reversed(messages):
        additional_kwargs = getattr(msg, "additional_kwargs", {}) or {}
        sent_at = parse_iso_datetime(additional_kwargs.get("sent_at"))
        if sent_at:
            return sent_at
    return None


def parse_iso_datetime(value: Any) -> datetime | None:
    """解析 ISO 时间字符串并统一转换为 UTC；无效输入返回 ``None``。"""

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
    """把时间上下文转换成模型可直接使用的中文提示段。"""

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


def format_self_changelog_context(context: dict[str, Any] | None) -> str:
    """从自我更新上下文中提取非空提示文本。"""

    if not context:
        return ""
    text = context.get("text")
    return text if isinstance(text, str) and text.strip() else ""


def format_chinese_datetime(value: datetime) -> str:
    """把 datetime 格式化为包含中文星期的本地时间文本。"""

    weekdays = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    return f"{value.year}年{value.month}月{value.day}日 {weekdays[value.weekday()]} {value:%H:%M}"


def format_elapsed(seconds: int) -> str:
    """把秒数转换为易读的分钟、小时或天数。"""

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
    """把对话间隔划分为 ``short``、``medium`` 或 ``long``。"""

    if seconds < 60 * 60:
        return "short"
    if seconds < 24 * 60 * 60:
        return "medium"
    return "long"


def save_memory_candidate_once(user_id: str, candidate: dict[str, Any]) -> None:
    """保存 judge 认可但本轮未通过 Tool 保存的记忆候选。

    只处理 long/mid 记忆；失败仅记录日志，不中断聊天回复。
    """

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
            extra_metadata={
                "perspective": candidate.get("perspective") or "user",
                "world_layer": candidate.get("world_layer") or "reality",
            },
        )
        logging.info("记忆候选保存完成 scope=%s user_id=%s title=%s", memory_scope, user_id, title)
    except Exception:
        logging.exception("记忆候选保存失败 user_id=%s", user_id)


def get_history(user_id: str) -> list:
    """从 LangGraph 状态导出供 API 使用的去重聊天历史。

    Args:
        user_id: 要读取的 LangGraph 线程 ID。

    Returns:
        由用户和 Aura 公共消息字典组成的时间顺序列表。

    Raises:
        RuntimeError: 对话图尚未初始化。
    """

    if aura is None:
        raise RuntimeError("Aura 对话图尚未初始化")

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
                "isProactive": additional_kwargs.get("is_proactive"),
            })
            last_role = "aura"
            last_content = content
    return history


def append_proactive_history_message(
    user_id: str,
    content: str,
    message_id: str,
    sent_at: datetime,
    trigger_type: str = "silence",
) -> bool:
    """把已发送的主动消息追加到用户的 LangGraph 对话历史。

    Returns:
        写入成功返回 ``True``；参数无效、图未初始化或持久化失败返回 ``False``。
    """

    if aura is None:
        logging.warning("Aura 对话图尚未初始化，跳过主动消息历史写入")
        return False

    normalized_user_id = str(user_id or "").strip()
    normalized_content = str(content or "").strip()
    normalized_message_id = str(message_id or "").strip()
    if not normalized_user_id or not normalized_content or not normalized_message_id:
        return False

    # reliable outbox 在进程崩溃窗口内可能使用同一 delivery_message_id 重试。
    # checkpoint 更新前先检查公开历史，确保首次已成功但数据库尚未标 sent 时，
    # 重试只确认已有消息，不会追加第二条相同主动消息。
    try:
        if any(
            item.get("isProactive")
            and item.get("id") == f"ai-proactive-{normalized_message_id}"
            for item in get_history(normalized_user_id)
        ):
            return True
    except Exception:
        logging.exception("主动消息写入前的幂等历史检查失败 user_id=%s", normalized_user_id)
        return False

    turn_id = f"proactive-{normalized_message_id}"
    config: RunnableConfig = {
        "configurable": {
            "thread_id": normalized_user_id,
            "user_id": normalized_user_id,
        }
    }
    try:
        aura.update_state(
            config,
            {
                "messages": [
                    AIMessage(
                        id=f"ai-{turn_id}",
                        content=normalized_content,
                        additional_kwargs={
                            "turn_id": turn_id,
                            "sent_at": sent_at.isoformat(),
                            "is_proactive": True,
                            "proactive_message_id": normalized_message_id,
                            "trigger_type": trigger_type,
                        },
                    )
                ],
                "user_id": normalized_user_id,
            },
        )
    except Exception:
        logging.exception("主动消息写入 Aura 历史失败 user_id=%s", normalized_user_id)
        return False
    return True


def append_external_history_turn(
    user_id: str,
    human_content: str,
    aura_contents: list[str],
    *,
    source: str,
    turn_id: str | None = None,
    client_message_id: str | None = None,
    source_metadata: dict[str, Any] | None = None,
    sent_at: datetime | None = None,
) -> dict[str, Any] | None:
    """把确定性领域功能的一轮问答追加到 LangGraph 历史。

    Args:
        user_id: LangGraph 线程 ID。
        human_content: 用户触发领域动作的原始文本。
        aura_contents: 已由领域规则确认、需要展示的 Aura 消息列表。
        source: 消息来源标识，例如 ``bash_game``；用于历史审计和后续过滤。
        turn_id: 可选回合 ID；未提供时生成带来源前缀的新 ID。
        client_message_id: 客户端消息 ID，用于历史去重和请求关联。
        source_metadata: 需要附加到双方消息的只读领域元数据。
        sent_at: 回合开始时间，默认当前 UTC 时间。

    Returns:
        与普通 Agent 回复相同结构的 ``reply_batch``；图未初始化、参数无效或
        历史写入失败时返回 ``None``。

    Side Effects:
        向现有 LangGraph checkpoint 追加一条 HumanMessage 和一到多条 AIMessage，
        并写入临时回复时序状态。领域数据库已经提交的事实不会因历史失败回滚。
    """

    if aura is None:
        logging.warning("Aura 对话图尚未初始化，跳过外部功能历史写入 source=%s", source)
        return None

    normalized_user_id = str(user_id or "").strip()
    normalized_human_content = str(human_content or "").strip()
    normalized_source = str(source or "").strip()
    normalized_aura_contents = [
        str(content).strip()
        for content in aura_contents
        if isinstance(content, str) and content.strip()
    ]
    if not normalized_user_id or not normalized_human_content or not normalized_source or not normalized_aura_contents:
        return None

    started_at = sent_at or datetime.now(UTC)
    normalized_turn_id = str(turn_id or client_message_id or f"{normalized_source}-{uuid4()}")
    metadata = dict(source_metadata or {})
    state: AuraState = {
        "user_id": normalized_user_id,
        "turn_id": normalized_turn_id,
        "request_started_at": started_at.isoformat(),
    }
    ai_messages, reply_batch = build_reply_messages_from_texts(
        normalized_aura_contents,
        AIMessage(content=""),
        state,
    )
    for message in ai_messages:
        message.additional_kwargs.update(
            {
                "source": normalized_source,
                **metadata,
            }
        )
    human_message = HumanMessage(
        id=f"human-{normalized_turn_id}",
        content=normalized_human_content,
        additional_kwargs={
            "turn_id": normalized_turn_id,
            "sent_at": started_at.isoformat(),
            "source": normalized_source,
            **({"client_message_id": client_message_id} if client_message_id else {}),
            **metadata,
        },
    )
    config: RunnableConfig = {
        "configurable": {
            "thread_id": normalized_user_id,
            "user_id": normalized_user_id,
        }
    }
    try:
        aura.update_state(
            config,
            {
                "messages": [human_message, *ai_messages],
                "user_id": normalized_user_id,
                "last_reply_batch": reply_batch,
            },
        )
    except Exception:
        logging.exception(
            "外部功能消息写入 Aura 历史失败 source=%s user_id=%s",
            normalized_source,
            normalized_user_id,
        )
        return None
    return reply_batch


def delete_history_message(user_id: str, message_id: str) -> bool:
    """向 LangGraph 写入单条 RemoveMessage；目标不存在时返回 ``False``。"""

    if aura is None:
        raise RuntimeError("Aura 对话图尚未初始化")

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
    """逻辑清空用户当前消息状态，并返回清理前的消息数量。"""

    if aura is None:
        raise RuntimeError("Aura 对话图尚未初始化")

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
    """保留最近的完整消息块，且不截断 assistant/tool 调用组合。"""

    blocks = build_valid_message_blocks(messages)
    selected: list = []
    selected_count = 0
    for block in reversed(blocks):
        if selected and selected_count + len(block) > SHORT_TERM_MESSAGE_WINDOW:
            break
        selected[0:0] = block
        selected_count += len(block)
    return selected


def build_valid_message_blocks(messages: list) -> list[list]:
    """把历史拆成普通消息或完整工具调用块，并丢弃孤立工具消息。"""

    blocks: list[list] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if is_tool_message(message):
            logging.warning("短期上下文中发现孤立工具消息，已丢弃")
            index += 1
            continue

        if has_tool_calls(message):
            block, next_index = build_complete_tool_block(messages, index)
            if block:
                blocks.append(block)
            else:
                logging.warning("短期上下文中发现不完整工具调用块，已丢弃")
            index = next_index
            continue

        blocks.append([message])
        index += 1
    return blocks


def build_complete_tool_block(messages: list, index: int) -> tuple[list | None, int]:
    """从 AI 工具调用开始收集对应 ToolMessage，并返回块及下一索引。"""

    assistant_message = messages[index]
    expected_ids = set(tool_call_ids(assistant_message))
    block = [assistant_message]
    seen_ids: set[str] = set()
    next_index = index + 1

    while next_index < len(messages) and is_tool_message(messages[next_index]):
        tool_message = messages[next_index]
        block.append(tool_message)
        tool_call_id = tool_message_id(tool_message)
        if tool_call_id:
            seen_ids.add(tool_call_id)
        next_index += 1

    if expected_ids:
        return (block, next_index) if expected_ids.issubset(seen_ids) else (None, next_index)
    return (block, next_index) if len(block) > 1 else (None, next_index)


def is_tool_message(message: Any) -> bool:
    """判断消息是否为 LangChain ToolMessage。"""

    return getattr(message, "type", None) == "tool"


def has_tool_calls(message: Any) -> bool:
    """判断 AI 消息正文或 additional_kwargs 中是否声明了工具调用。"""

    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    return bool(getattr(message, "tool_calls", None) or additional_kwargs.get("tool_calls"))


def tool_call_ids(message: Any) -> list[str]:
    """提取 AI 消息内所有非空工具调用 ID。"""

    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    raw_tool_calls = getattr(message, "tool_calls", None) or additional_kwargs.get("tool_calls") or []
    ids: list[str] = []
    for tool_call in raw_tool_calls:
        if isinstance(tool_call, dict):
            tool_call_id = tool_call.get("id") or tool_call.get("tool_call_id")
            if isinstance(tool_call_id, str) and tool_call_id:
                ids.append(tool_call_id)
    return ids


def tool_message_id(message: Any) -> str | None:
    """从 ToolMessage 属性或附加元数据中读取关联的工具调用 ID。"""

    tool_call_id = getattr(message, "tool_call_id", None)
    if isinstance(tool_call_id, str) and tool_call_id:
        return tool_call_id
    additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
    tool_call_id = additional_kwargs.get("tool_call_id")
    return tool_call_id if isinstance(tool_call_id, str) and tool_call_id else None


def latest_human_text(messages: list) -> str:
    """返回最近一条用户消息文本；不存在时返回空字符串。"""

    for msg in reversed(messages):
        if getattr(msg, "type", None) == "human":
            content = getattr(msg, "content", "")
            return content if isinstance(content, str) else str(content)
    return ""


def normalize_city_adcode(value: str | None) -> str | None:
    """校验并规范化六位数字城市 adcode。"""

    if not isinstance(value, str):
        return None

    value = value.strip()
    return value if len(value) == 6 and value.isdigit() else None


def format_location_context(city_adcode: str | None) -> str:
    """生成天气工具可用的位置提示，并禁止模型猜测城市。"""

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
    """从内部附件元数据中提取可对外返回的文件名列表。"""

    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("fileName"), str):
            names.append(item["fileName"])
    return names
