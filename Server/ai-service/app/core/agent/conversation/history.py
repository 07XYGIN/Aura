"""读取和更新 LangGraph 聊天历史及分支。"""

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from .reply import build_reply_messages_from_texts

BRANCH_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


from ..graph import agent_runtime


def normalize_branch_id(branch_id: str | None) -> str | None:
    """校验前端提供的逻辑分支标识，避免它参与任意 checkpointer 键。"""

    if branch_id is None:
        return None
    normalized = str(branch_id).strip()
    return normalized if BRANCH_ID_PATTERN.fullmatch(normalized) else None

def conversation_thread_id(user_id: str, branch_id: str | None = None) -> str:
    """主会话沿用历史线程 ID；分支使用隔离且可追溯的线程 ID。"""

    return user_id if branch_id is None else f"{user_id}:branch:{branch_id}"

def conversation_config(user_id: str, branch_id: str | None = None) -> RunnableConfig:
    """生成读取、分叉和删改对话历史共用的 checkpointer 配置。"""

    normalized_branch_id = normalize_branch_id(branch_id)
    if branch_id is not None and normalized_branch_id is None:
        raise ValueError("对话分支 ID 无效")
    return {
        "configurable": {
            "thread_id": conversation_thread_id(user_id, normalized_branch_id),
            "user_id": user_id,
            "allow_persistence": normalized_branch_id is None,
        }
    }

def create_history_branch(
    user_id: str,
    source_message_id: str,
    source_branch_id: str | None = None,
) -> str | None:
    """从一条已有消息截取历史，生成不影响主会话的 LangGraph 分支。"""

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")
    source_id = str(source_message_id or "").strip()
    if not source_id:
        return None
    source_config = conversation_config(user_id, source_branch_id)
    state = agent_runtime.graph.get_state(source_config)
    messages = state.values.get("messages", []) if state and state.values else []
    source_index = next(
        (index for index, message in enumerate(messages) if getattr(message, "id", None) == source_id),
        None,
    )
    if source_index is None:
        return None
    return create_branch_from_messages(user_id, list(messages[: source_index + 1]))

def create_branch_from_messages(user_id: str, messages: list) -> str | None:
    """向一个全新分支 checkpointer 线程写入已截取的聊天前缀。"""

    if agent_runtime.graph is None:
        return None
    branch_id = f"b-{uuid4().hex[:12]}"
    if not messages:
        return branch_id
    try:
        agent_runtime.graph.update_state(
            conversation_config(user_id, branch_id),
            {
                "messages": messages,
                "user_id": user_id,
                "pending_approvals": [],
            },
        )
    except Exception:
        logging.exception("Aura 对话分支创建失败 user_id=%s", user_id)
        return None
    return branch_id

def get_history(user_id: str, branch_id: str | None = None) -> list:
    """从 LangGraph 状态导出供 API 使用的去重聊天历史。

    Args:
        user_id: 当前用户 ID。
        branch_id: 可选对话分支；缺失时读取历史主会话。

    Returns:
        由用户和 Aura 公共消息字典组成的时间顺序列表。

    Raises:
        RuntimeError: 对话图尚未初始化。
    """

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")

    config = conversation_config(user_id, branch_id)
    state = agent_runtime.graph.get_state(config)
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

    if agent_runtime.graph is None:
        logging.warning("Aura 对话图尚未初始化，跳过主动消息历史写入")
        return False

    normalized_user_id = str(user_id or "").strip()
    normalized_content = str(content or "").strip()
    normalized_message_id = str(message_id or "").strip()
    if not normalized_user_id or not normalized_content or not normalized_message_id:
        return False

    # 可靠发件箱在进程崩溃窗口内可能使用同一消息 ID 重试。
    # 更新 checkpoint 前先检查公开历史，确保首次已成功但数据库尚未标记发送时，
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
        agent_runtime.graph.update_state(
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
        source: 消息来源标识；用于历史审计和后续过滤。
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

    if agent_runtime.graph is None:
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
        agent_runtime.graph.update_state(
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

def delete_history_message(user_id: str, message_id: str, branch_id: str | None = None) -> bool:
    """向 LangGraph 写入单条 RemoveMessage；目标不存在时返回 ``False``。"""

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")

    normalized_message_id = message_id.strip()
    if not normalized_message_id:
        return False

    config = conversation_config(user_id, branch_id)
    state = agent_runtime.graph.get_state(config)
    messages = state.values.get("messages", []) if state and state.values else []

    if not any(getattr(msg, "id", None) == normalized_message_id for msg in messages):
        return False

    agent_runtime.graph.update_state(
        config,
        {
            "messages": [
                RemoveMessage(id=normalized_message_id, content=""),
            ]
        },
    )
    return True

def clear_history(user_id: str, branch_id: str | None = None) -> int:
    """逻辑清空用户当前消息状态，并返回清理前的消息数量。"""

    if agent_runtime.graph is None:
        raise RuntimeError("Aura 对话图尚未初始化")

    config = conversation_config(user_id, branch_id)
    state = agent_runtime.graph.get_state(config)
    messages = state.values.get("messages", []) if state and state.values else []
    removable_count = len(messages)

    if removable_count == 0:
        return 0

    agent_runtime.graph.update_state(
        config,
        {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES, content=""),
            ]
        },
    )
    return removable_count

def public_history_attachments(value: Any) -> list[dict[str, Any]]:
    """从内部附件元数据中筛选可安全渲染图片预览的公开字段。"""

    if not isinstance(value, list):
        return []
    attachments: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("fileName"), str):
            continue
        attachments.append(
            {
                "id": item.get("id"),
                "fileName": item["fileName"],
                "contentType": item.get("contentType"),
                "size": item.get("size"),
            }
        )
    return attachments
