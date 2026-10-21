"""执行聊天回合、流式处理回复并支持重新生成。"""

import logging
from datetime import UTC, datetime
from typing import Any, Generator
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from app.core.attachment_store import load_attachments
from app.core.continuity.context import load_relationship_context_sync
from app.core.continuity.aura_state import observe_relationship_state_sync, project_without_database
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
)
from .protocol import (
    approval_required_event,
    assistant_message_event,
    conversation_branch_event,
    content_event,
    emotion_event,
    error_event,
    live2d_state_event,
    memory_reference_event,
    memory_candidate_event,
)
from .reply import (
    message_content_to_text,
)
from ..schemas.structured_reply import parse_structured_reply
from ..self_changelog import load_self_changelog_context_sync, mark_self_changelog_reacted_sync
from .time_context import build_time_context

from ..graph import agent_runtime
from .context import normalize_city_adcode
from .history import (
    conversation_config,
    conversation_thread_id,
    create_branch_from_messages,
    normalize_branch_id,
)
from .turn_effects import persist_turn_effects, queue_turn_approval_if_needed


def aura_agent(
    human_prompt: str,
    user_id: str,
    emotion_state: dict | None = None,
    client_message_id: str | None = None,
    attachment_ids: list[str] | None = None,
    city_adcode: str | None = None,
    branch_id: str | None = None,
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

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")

    normalized_branch_id = normalize_branch_id(branch_id)
    if branch_id is not None and normalized_branch_id is None:
        raise ValueError("对话分支 ID 无效")
    is_branch = normalized_branch_id is not None
    thread_id = conversation_thread_id(user_id, normalized_branch_id)
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
            "branch_id": normalized_branch_id,
        },
        "configurable": {
            "thread_id": thread_id,
            "user_id": user_id,
            "allow_persistence": not is_branch,
        }
    }
    previous_state = agent_runtime.graph.get_state(config)
    previous_messages = previous_state.values.get("messages", []) if previous_state and previous_state.values else []
    time_context = build_time_context(previous_messages, request_started_at)
    if not is_branch:
        cancel_pending_second_thoughts_sync(user_id, now=request_started_at)
        offline_thought = consume_relevant_offline_thought_sync(
            user_id,
            human_prompt,
            now=request_started_at,
        )
    else:
        offline_thought = None
    self_changelog_context = load_self_changelog_context_sync()
    relationship_context = load_relationship_context_sync(user_id)
    if not is_branch:
        apply_scene_message_sync(
            user_id,
            human_prompt,
            client_message_id,
            now=request_started_at,
        )
    continuity_state = load_continuity_state_context_sync(user_id, now=request_started_at)
    turn_judgement = {
        "emotion": emotion_state or {},
        "interaction": {},
        "memory_candidate": {},
        "risk_signal": {"requires_safety_gate": False},
        "response_mode": "natural_chat",
    }
    if is_branch:
        relationship_state = project_without_database(
            human_prompt,
            turn_judgement,
            relationship_context,
            now=request_started_at,
        )
    else:
        relationship_state = observe_relationship_state_sync(
            user_id,
            human_prompt,
            turn_judgement,
            relationship_context,
            source_message_id=client_message_id or turn_id,
            now=request_started_at,
        )
    conditional_candidates = turn_judgement["memory_candidate"].get("conditional_messages") or []
    conditional_messages_created: list[dict[str, Any]] = []
    if not is_branch and conditional_candidates and client_message_id:
        conditional_messages_created = capture_conditional_candidates_sync(
            user_id,
            conditional_candidates,
            source_message_id=client_message_id,
            source_turn_id=turn_id,
            now=request_started_at,
        )
    elif not is_branch and conditional_candidates:
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
    if not is_branch and not turn_judgement["risk_signal"].get("requires_safety_gate"):
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
            "entry_ids": list(self_changelog_context.entry_ids),
            "text": self_changelog_context.text,
        },
        "turn_id": turn_id,
        "request_started_at": request_started_at.isoformat(),
        "relationship_context": relationship_context["prompt_context"],
        "relationship_snapshot": relationship_context,
        "relationship_dynamics": relationship_state["relationship_dynamics"],
        "aura_internal_state": relationship_state["aura_internal_state"],
        "aura_impulse": {},
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

    for chunk, metadata in agent_runtime.graph.stream(inputs, config, stream_mode="messages"):
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

        if stream_node_matches(metadata, "tools") and getattr(chunk, "name", None) == "save_memory_tool":
            memory_save_tool_called = True

        if (
            not memory_reference_reported
            and stream_node_matches(metadata, "tools")
            and getattr(chunk, "name", None) == "search_memory_tool"
        ):
            memory_reference_reported = True
            yield memory_reference_event()

        if chunk.content and stream_node_matches(metadata, "chat"):
            raw_chat_parts.append(str(chunk.content))

    relationship_candidates = memory_candidate.get("relationship_threads")
    relationship_item_candidates = memory_candidate.get("relationship_items")
    relationship_chapter_candidate = memory_candidate.get("relationship_chapter")
    pending_approval = None
    if not is_branch:
        pending_approval = queue_turn_approval_if_needed(
            config=config,
            user_id=user_id,
            turn_id=turn_id,
            client_message_id=client_message_id,
            human_prompt=human_prompt,
            memory_candidate=memory_candidate,
            relationship_candidates=relationship_candidates,
            relationship_item_candidates=relationship_item_candidates,
            relationship_chapter_candidate=relationship_chapter_candidate,
            memory_save_tool_called=memory_save_tool_called,
            created_at=request_started_at,
        )
        if pending_approval is None:
            persist_turn_effects(
                user_id=user_id,
                turn_id=turn_id,
                client_message_id=client_message_id,
                human_prompt=human_prompt,
                memory_candidate=memory_candidate,
                relationship_candidates=relationship_candidates,
                relationship_item_candidates=relationship_item_candidates,
                relationship_chapter_candidate=relationship_chapter_candidate,
                memory_save_tool_called=memory_save_tool_called,
            )

    reply_batch = get_latest_reply_batch(config, turn_id)
    relationship_actions = get_latest_relationship_actions(config, turn_id)
    relationship_item_usages = get_latest_relationship_item_usages(config, turn_id)
    if not is_branch and reply_batch and relationship_actions:
        apply_reply_thread_actions_sync(
            user_id,
            relationship_actions,
            relationship_context["items"],
            turn_id=turn_id,
        )
    if not is_branch and reply_batch and relationship_item_usages:
        mark_relationship_items_used_sync(
            user_id,
            relationship_context["knowledge_items"],
            relationship_item_usages,
            source_turn_id=turn_id,
        )
    if reply_batch:
        live2d_state = get_latest_live2d_state(config, turn_id)
        if live2d_state:
            yield live2d_state_event(live2d_state)
        if not is_branch and client_message_id:
            trigger_keyword_messages_sync(
                user_id,
                human_prompt,
                event_id=f"chat:{client_message_id}",
                now=request_started_at,
            )
        if not is_branch:
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
        if pending_approval is not None:
            yield approval_required_event(pending_approval)
        if not is_branch:
            mark_self_changelog_reacted_sync(self_changelog_context.entry_ids)
    elif raw_chat_parts:
        for content in parse_structured_reply("".join(raw_chat_parts)):
            yield content_event(content)
        if not is_branch:
            mark_self_changelog_reacted_sync(self_changelog_context.entry_ids)

    logging.info("Aura 对话结束 user_id=%s", user_id)

def stream_node_matches(metadata: dict[str, Any], node_name: str) -> bool:
    """兼容父图包裹子图后 LangGraph 的节点命名。"""

    current = str(metadata.get("langgraph_node") or "")
    return current == node_name or current.endswith(f":{node_name}")

def get_latest_live2d_state(config: RunnableConfig, turn_id: str) -> dict[str, Any]:
    """读取当前回合体验导演生成的受限 Live2D 状态。"""

    if agent_runtime.graph is None:
        return {}
    state = agent_runtime.graph.get_state(config)
    values = state.values if state and state.values else {}
    if values.get("turn_id") != turn_id:
        return {}
    presence = values.get("live2d_state")
    return dict(presence) if isinstance(presence, dict) else {}

def retry_aura_agent(
    user_id: str,
    assistant_message_id: str,
    source_branch_id: str | None = None,
) -> Generator[Any, None, None]:
    """从目标回复前的用户消息分叉，并在新分支重新生成回复。"""

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")
    try:
        source_config = conversation_config(user_id, source_branch_id)
    except ValueError:
        yield error_event("对话分支无效，无法重新生成。")
        return
    state = agent_runtime.graph.get_state(source_config)
    messages = state.values.get("messages", []) if state and state.values else []
    target_index = next(
        (
            index
            for index, message in enumerate(messages)
            if getattr(message, "id", None) == assistant_message_id and getattr(message, "type", None) == "ai"
        ),
        None,
    )
    if target_index is None:
        yield error_event("找不到要重新生成的回复。")
        return

    human_index = next(
        (
            index
            for index in range(target_index - 1, -1, -1)
            if getattr(messages[index], "type", None) == "human"
        ),
        None,
    )
    if human_index is None:
        yield error_event("这条回复没有可重放的用户消息。")
        return

    human_message = messages[human_index]
    branch_id = create_branch_from_messages(user_id, list(messages[:human_index]))
    if branch_id is None:
        yield error_event("新的对话分支没有创建成功。")
        return
    metadata = getattr(human_message, "additional_kwargs", {}) or {}
    attachment_ids = [
        str(item.get("id"))
        for item in metadata.get("attachments", [])
        if isinstance(item, dict) and item.get("id")
    ]
    retry_message_id = f"retry-{uuid4().hex[:20]}"
    yield conversation_branch_event(branch_id, assistant_message_id)
    yield from aura_agent(
        message_content_to_text(getattr(human_message, "content", "")),
        user_id,
        client_message_id=retry_message_id,
        attachment_ids=attachment_ids,
        branch_id=branch_id,
    )

def get_latest_reply_batch(config: RunnableConfig, turn_id: str) -> dict[str, Any] | None:
    """读取当前图状态中属于指定回合的最新回复批次。"""

    if agent_runtime.graph is None:
        return None
    state = agent_runtime.graph.get_state(config)
    values = state.values if state and state.values else {}
    batch = values.get("last_reply_batch")
    if isinstance(batch, dict) and batch.get("turn_id") == turn_id:
        return batch
    return None

def get_latest_relationship_actions(config: RunnableConfig, turn_id: str) -> list[dict[str, Any]]:
    """读取当前回合主回复返回的、已通过结构化白名单校验的线程动作。"""

    if agent_runtime.graph is None:
        return []
    state = agent_runtime.graph.get_state(config)
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

    if agent_runtime.graph is None:
        return []
    state = agent_runtime.graph.get_state(config)
    values = state.values if state and state.values else {}
    usage_batch = values.get("relationship_item_usages")
    if not isinstance(usage_batch, dict) or usage_batch.get("turn_id") != turn_id:
        return []
    items = usage_batch.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
