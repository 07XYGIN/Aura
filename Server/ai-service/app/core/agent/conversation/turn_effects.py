"""处理聊天回合的审批、记忆和关系副作用。"""

import logging
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.continuity.knowledge import (
    capture_relationship_knowledge_sync,
)
from app.core.continuity.service import (
    capture_relationship_candidates_sync,
)
from app.core.memory.service import save_memory
from app.core.memory.embeddings import MemoryEmbeddingsUnavailable
from ..approval import approval_config, resume_approval, start_approval


from ..graph import agent_runtime


def persist_turn_effects(
    *,
    user_id: str,
    turn_id: str,
    client_message_id: str | None,
    human_prompt: str,
    memory_candidate: dict[str, Any],
    relationship_candidates: Any,
    relationship_item_candidates: Any,
    relationship_chapter_candidate: Any,
    memory_save_tool_called: bool,
) -> None:
    """提交已经无需人工审批的回合级辅助写入。"""

    if not memory_save_tool_called:
        save_memory_candidate_once(user_id, memory_candidate)

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

def queue_turn_approval_if_needed(
    *,
    config: RunnableConfig,
    user_id: str,
    turn_id: str,
    client_message_id: str | None,
    human_prompt: str,
    memory_candidate: dict[str, Any],
    relationship_candidates: Any,
    relationship_item_candidates: Any,
    relationship_chapter_candidate: Any,
    memory_save_tool_called: bool,
    created_at: datetime,
) -> dict[str, Any] | None:
    """为长期记忆和关系定义变更创建可恢复的人工审批。"""

    request = build_turn_approval_request(
        user_id=user_id,
        turn_id=turn_id,
        client_message_id=client_message_id,
        human_prompt=human_prompt,
        memory_candidate=memory_candidate,
        relationship_candidates=relationship_candidates,
        relationship_item_candidates=relationship_item_candidates,
        relationship_chapter_candidate=relationship_chapter_candidate,
        memory_save_tool_called=memory_save_tool_called,
        created_at=created_at,
    )
    if request is None:
        return None

    public = request["public"]
    existing = pending_approvals_from_state(config)
    if any(item.get("id") == public["id"] for item in existing):
        return public

    try:
        started = start_approval(request, approval_config(user_id, public["id"]))
    except Exception:
        logging.exception("Aura 人工审批子图启动失败，回退到原有自动写入")
        return None
    if not started:
        logging.warning("Aura 人工审批子图未进入暂停状态，回退到原有自动写入")
        return None

    try:
        if agent_runtime.graph is None:
            return None
        agent_runtime.graph.update_state(config, {"pending_approvals": [*existing, public]})
    except Exception:
        logging.exception("Aura 待审批状态写入失败，回退到原有自动写入")
        return None
    return public

def build_turn_approval_request(
    *,
    user_id: str,
    turn_id: str,
    client_message_id: str | None,
    human_prompt: str,
    memory_candidate: dict[str, Any],
    relationship_candidates: Any,
    relationship_item_candidates: Any,
    relationship_chapter_candidate: Any,
    memory_save_tool_called: bool,
    created_at: datetime,
) -> dict[str, Any] | None:
    """将内部候选压缩成可展示摘要和不可展示的待执行效果。"""

    if not turn_requires_human_approval(
        memory_candidate,
        relationship_item_candidates,
        relationship_chapter_candidate,
        memory_save_tool_called=memory_save_tool_called,
    ):
        return None

    descriptions = approval_descriptions(
        memory_candidate,
        relationship_item_candidates,
        relationship_chapter_candidate,
        memory_save_tool_called=memory_save_tool_called,
    )
    public = {
        "id": turn_id,
        "kind": "memory_review",
        "title": "要把这件事留下来吗？",
        "summary": "、".join(descriptions) or "保存一条长期关系记录",
        "createdAt": created_at.isoformat(),
    }
    return {
        "user_id": user_id,
        "public": public,
        "effects": {
            "turn_id": turn_id,
            "client_message_id": client_message_id,
            "human_prompt": human_prompt,
            "memory_candidate": memory_candidate,
            "relationship_candidates": relationship_candidates,
            "relationship_item_candidates": relationship_item_candidates,
            "relationship_chapter_candidate": relationship_chapter_candidate,
            "memory_save_tool_called": memory_save_tool_called,
        },
    }

def turn_requires_human_approval(
    memory_candidate: dict[str, Any],
    relationship_item_candidates: Any,
    relationship_chapter_candidate: Any,
    *,
    memory_save_tool_called: bool,
) -> bool:
    """只拦截会改变长期关系模型的内容，避免每轮聊天弹窗。"""

    if (
        not memory_save_tool_called
        and memory_candidate.get("save")
        and memory_candidate.get("memory_scope") == "long"
    ):
        return True
    if isinstance(relationship_chapter_candidate, dict):
        return True
    if not isinstance(relationship_item_candidates, list):
        return False
    sensitive_types = {"nickname", "codeword", "ritual", "interaction_rule", "boundary", "aura_stance"}
    return any(
        isinstance(item, dict) and item.get("item_type") in sensitive_types
        for item in relationship_item_candidates
    )

def approval_descriptions(
    memory_candidate: dict[str, Any],
    relationship_item_candidates: Any,
    relationship_chapter_candidate: Any,
    *,
    memory_save_tool_called: bool,
) -> list[str]:
    """生成不泄露内部候选字段的简短审批文案。"""

    descriptions: list[str] = []
    if (
        not memory_save_tool_called
        and memory_candidate.get("save")
        and memory_candidate.get("memory_scope") == "long"
    ):
        title = str(memory_candidate.get("title") or "未命名").strip()[:80]
        descriptions.append(f"长期记忆《{title or '未命名'}》")
    if isinstance(relationship_chapter_candidate, dict):
        title = str(relationship_chapter_candidate.get("title") or "未命名").strip()[:80]
        descriptions.append(f"关系章节《{title or '未命名'}》")
    if isinstance(relationship_item_candidates, list):
        count = sum(
            1
            for item in relationship_item_candidates
            if isinstance(item, dict)
            and item.get("item_type") in {"nickname", "codeword", "ritual", "interaction_rule", "boundary", "aura_stance"}
        )
        if count:
            descriptions.append(f"{count} 条互动或关系规则")
    return descriptions

def pending_approvals_from_state(config: RunnableConfig) -> list[dict[str, Any]]:
    """读取主对话图中仍未决的公开审批摘要。"""

    if agent_runtime.graph is None:
        return []
    state = agent_runtime.graph.get_state(config)
    values = state.values if state and state.values else {}
    raw = values.get("pending_approvals")
    return [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []

def list_pending_approvals(user_id: str) -> list[dict[str, Any]]:
    """供前端重连后重新加载未决审批。"""

    return pending_approvals_from_state(
        {"configurable": {"thread_id": user_id, "user_id": user_id}}
    )

def resolve_pending_approval(user_id: str, approval_id: str, approved: bool) -> dict[str, Any] | None:
    """恢复审批子图，并在批准后提交先前冻结的副作用。"""

    if agent_runtime.graph is None:
        return None
    normalized_id = str(approval_id or "").strip()
    if not normalized_id or len(normalized_id) > 128:
        return None
    try:
        resolved = resume_approval(normalized_id, user_id, approved)
    except Exception:
        logging.exception("Aura 人工审批恢复失败 approval_id=%s", normalized_id)
        return None
    if resolved is None:
        return None

    request = resolved.get("request") if isinstance(resolved.get("request"), dict) else {}
    decision = resolved.get("decision") if isinstance(resolved.get("decision"), dict) else {}
    effects = request.get("effects") if isinstance(request.get("effects"), dict) else {}
    public = request.get("public") if isinstance(request.get("public"), dict) else {"id": normalized_id}
    was_approved = decision.get("approved") is True
    if was_approved:
        persist_turn_effects(
            user_id=user_id,
            turn_id=str(effects.get("turn_id") or normalized_id),
            client_message_id=effects.get("client_message_id") if isinstance(effects.get("client_message_id"), str) else None,
            human_prompt=str(effects.get("human_prompt") or ""),
            memory_candidate=effects.get("memory_candidate") if isinstance(effects.get("memory_candidate"), dict) else {},
            relationship_candidates=effects.get("relationship_candidates"),
            relationship_item_candidates=effects.get("relationship_item_candidates"),
            relationship_chapter_candidate=effects.get("relationship_chapter_candidate"),
            memory_save_tool_called=effects.get("memory_save_tool_called") is True,
        )

    config: RunnableConfig = {"configurable": {"thread_id": user_id, "user_id": user_id}}
    pending = [
        item
        for item in pending_approvals_from_state(config)
        if item.get("id") != normalized_id
    ]
    try:
        agent_runtime.graph.update_state(config, {"pending_approvals": pending})
    except Exception:
        logging.exception("Aura 待审批状态清理失败 approval_id=%s", normalized_id)
    return {"approval": public, "approved": was_approved}

def format_self_changelog_context(context: dict[str, Any] | None) -> str:
    """从自我更新上下文中提取非空提示文本。"""

    if not context:
        return ""
    text = context.get("text")
    return text if isinstance(text, str) and text.strip() else ""

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
    except MemoryEmbeddingsUnavailable:
        logging.info("记忆向量服务暂未接入，跳过候选写入 user_id=%s", user_id)
    except Exception:
        logging.exception("记忆候选保存失败 user_id=%s", user_id)
