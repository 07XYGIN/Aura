"""关系知识、私人语言与关系章节的 PostgreSQL 服务层。

这个模块只负责已经由上游规范化的候选如何安全落库，不负责调用模型或从自然
语言中抽取候选。聊天链路使用同步入口，并把数据库故障降级为日志和零变更；供
HTTP 路由复用的异步读取函数则使用独立领域异常，二者不会互相泄漏错误语义。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RelationshipChapter, RelationshipItem, Users
from app.db.session import SyncSessionLocal

ITEM_OPERATIONS = {"create", "upsert", "update", "deactivate"}
ITEM_TYPES = {
    "shared_memory",
    "nickname",
    "running_joke",
    "codeword",
    "ritual",
    "shared_object",
    "action_style",
    "aura_stance",
    "interaction_rule",
    "boundary",
}
PERSPECTIVES = {"user", "aura", "shared"}
WORLD_LAYERS = {"reality", "shared_history", "imagined", "wish", "promise"}
ITEM_STATUSES = {"active", "inactive", "superseded"}
MAX_ITEM_CANDIDATES = 12
MAX_USAGE_REFS = 12
MAX_CAPTURE_SOURCE_IDS = 32
MAX_USAGE_TURN_IDS = 32
INTERNAL_METADATA_KEYS = {"capture_source_ids", "usage_turn_ids", "source_turn_id"}


class RelationshipKnowledgeServiceError(RuntimeError):
    """供 HTTP 接口转换成中文响应的关系知识领域异常。

    聊天链路的两个同步入口不会把这个异常抛给主 Agent。它们对无效模型候选做
    丢弃，对数据库故障记录中文日志并返回零，确保补充性记忆能力不会阻断回复。
    """

    def __init__(self, message: str, status_code: int = 400) -> None:
        """保存可直接展示的中文说明和建议 HTTP 状态码。"""

        super().__init__(message)
        self.status_code = status_code


def capture_relationship_knowledge_sync(
    user_id: str,
    item_candidates: Any,
    chapter_candidate: Any,
    source_message_id: str,
    source_turn_id: str | None,
    *,
    now: datetime | None = None,
) -> int:
    """在同步聊天执行线程中持久化关系物件与可选关系章节。

    Args:
        user_id: 当前唯一用户的 UUID 字符串。服务仍按用户过滤和加锁，不能信任
            模型候选中可能出现的用户 ID。
        item_candidates: 上游已规范化的物件候选列表。支持 ``create``、
            ``upsert``、``update`` 和 ``deactivate``；本函数仍会检查枚举、长度、
            数值范围及目标标识，非法候选会被忽略。
        chapter_candidate: 可选章节字典。标题和摘要必须非空；没有 ``source_key``
            时按用户与来源消息生成稳定键，因此模型重试即使文案漂移也不会重复
            开启章节。
        source_message_id: 客户端稳定消息 ID。它既是幂等依据，也会写入来源字段；
            缺失或超长时整个批次被拒绝，避免 SSE 重连制造重复知识。
        source_turn_id: 可选回合 ID，写入内部元数据供审计，不参与模型语义。
        now: 可注入的发生时间，默认当前 UTC 时间，主要供测试和后台重放使用。

    Returns:
        本事务中新建、发生语义更新、停用或新开章节的记录数。完全相同的重放、
        无效候选、目标不存在以及数据库不可用都返回零。

    Concurrency:
        事务级 PostgreSQL advisory lock 以用户为粒度串行化物件 upsert 与章节换章。
        每个物件还持久化一个有界 ``capture_source_ids`` 列表；即使后续更新覆盖了
        ``source_message_id``，旧消息重放也不会再次递增版本。章节另外依赖数据库
        的 ``(user_id, source_key)`` 唯一约束。

    Failure Mode:
        本函数是聊天的辅助写入。任何数据库异常都只记录日志并返回零，绝不阻断
        Aura 的主回复；需要显式 HTTP 错误的管理接口应使用下方异步函数。
    """

    parsed_user_id = try_parse_uuid(user_id)
    normalized_source_id = bounded_text(source_message_id, 128)
    normalized_turn_id = optional_bounded_text(source_turn_id, 128)
    if parsed_user_id is None or normalized_source_id is None:
        logging.warning("关系知识候选缺少合法用户或来源消息 ID，已跳过")
        return 0
    if source_turn_id is not None and normalized_turn_id is None:
        logging.warning("关系知识候选来源回合 ID 超过限制，已忽略回合 ID")

    validated_items = validate_item_candidates(item_candidates)
    validated_chapter = validate_chapter_candidate(
        chapter_candidate,
        user_id=parsed_user_id,
        source_message_id=normalized_source_id,
    )
    if not validated_items and validated_chapter is None:
        return 0

    occurred_at = normalize_utc(now or datetime.now(UTC))
    changed = 0
    try:
        with SyncSessionLocal.begin() as session:
            acquire_user_knowledge_lock(session, parsed_user_id)
            user_exists = session.execute(
                select(Users.id).where(Users.id == parsed_user_id)
            ).scalar_one_or_none()
            if user_exists is None:
                return 0

            for candidate in validated_items:
                changed += capture_item_candidate(
                    session,
                    parsed_user_id,
                    candidate,
                    source_message_id=normalized_source_id,
                    source_turn_id=normalized_turn_id,
                    occurred_at=occurred_at,
                )
            if validated_chapter is not None:
                changed += capture_chapter_candidate(
                    session,
                    parsed_user_id,
                    validated_chapter,
                    source_message_id=normalized_source_id,
                    source_turn_id=normalized_turn_id,
                    occurred_at=occurred_at,
                )
    except Exception:
        logging.exception(
            "关系知识保存失败，聊天继续 user_id=%s source_message_id=%s",
            parsed_user_id,
            normalized_source_id,
        )
        return 0
    return changed


def mark_relationship_items_used_sync(
    user_id: str,
    context_items: Any,
    usage_refs: Any,
    *,
    source_turn_id: str | None = None,
    now: datetime | None = None,
) -> int:
    """根据本轮已加载短引用记录 Aura 实际使用过的关系物件。

    Args:
        user_id: 当前用户 UUID；查询时再次限定所有权。
        context_items: 构建提示词时实际载入的物件列表，每项至少包含 ``ref`` 和
            ``id``。只有这里出现的引用才可能被更新。
        usage_refs: 主回复结构化字段 ``itemUsages``。兼容 ``["K1"]`` 以及包含
            ``item_ref``、``itemRef`` 或 ``ref`` 的字典列表；未知引用被忽略。
        source_turn_id: 推荐传入稳定回合 ID。服务把最近回合保存在有界列表中，
            同一结构化回复因重试再次执行时不会重复增加 ``use_count``。
        now: 实际使用时间，默认当前 UTC 时间。

    Returns:
        成功更新的不同物件数量。伪造引用、非活跃物件、重复回合、非法参数和
        数据库故障均不计数。

    Security:
        模型只看到 ``K1`` 之类短引用，不能借此提交任意 UUID。服务先将显式引用
        与本轮上下文相交，再以 ``user_id`` 查询并加行锁，形成双重所有权校验。
    """

    parsed_user_id = try_parse_uuid(user_id)
    if parsed_user_id is None:
        return 0
    normalized_turn_id = optional_bounded_text(source_turn_id, 128)
    if source_turn_id is not None and normalized_turn_id is None:
        return 0
    target_ids = resolve_usage_target_ids(context_items, usage_refs)
    if not target_ids:
        return 0

    used_at = normalize_utc(now or datetime.now(UTC))
    changed = 0
    try:
        with SyncSessionLocal.begin() as session:
            for target_id in target_ids:
                item = session.execute(
                    select(RelationshipItem)
                    .where(
                        RelationshipItem.id == target_id,
                        RelationshipItem.user_id == parsed_user_id,
                    )
                    .with_for_update()
                ).scalar_one_or_none()
                if item is None or item.status != "active":
                    continue
                if mark_item_used(
                    item,
                    used_at=used_at,
                    source_turn_id=normalized_turn_id,
                ):
                    changed += 1
    except Exception:
        logging.exception("关系物件使用记录失败，聊天继续 user_id=%s", parsed_user_id)
        return 0
    return changed


def validate_item_candidates(raw_candidates: Any) -> list[dict[str, Any]]:
    """防御性校验上游已经规范化的物件候选，并按目标去重。

    该函数不猜测自然语言含义、不补写标题，也不会把未知枚举强行纠正成默认值。
    ``create/upsert`` 需要完整快照；``update`` 只保留明确出现的可变字段；
    ``deactivate`` 只要求 ``target_id`` 或 ``item_key``。同一批次若多次指向同一
    物件，只接受第一个候选，避免一个来源 ID 在同一物件上表达相互冲突的操作。
    """

    if not isinstance(raw_candidates, list):
        return []
    result: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for raw in raw_candidates[:MAX_ITEM_CANDIDATES]:
        candidate = validate_item_candidate(raw)
        if candidate is None:
            continue
        identity = candidate_identity(candidate)
        if identity in seen_targets:
            continue
        seen_targets.add(identity)
        result.append(candidate)
    return result


def validate_item_candidate(raw: Any) -> dict[str, Any] | None:
    """校验一条关系物件候选，返回字段受限的新字典或 ``None``。"""

    if not isinstance(raw, dict):
        return None
    operation = raw.get("operation")
    if operation not in ITEM_OPERATIONS:
        return None

    item_key = optional_bounded_text(raw.get("item_key"), 160)
    target_id = try_parse_uuid(raw.get("target_id") or raw.get("id"))
    if operation in {"create", "upsert"} and item_key is None:
        return None
    if operation in {"update", "deactivate"} and target_id is None and item_key is None:
        return None

    candidate: dict[str, Any] = {
        "operation": operation,
        "item_key": item_key,
        "target_id": target_id,
    }
    full_snapshot = operation in {"create", "upsert"}

    item_type = raw.get("item_type")
    perspective = raw.get("perspective")
    world_layer = raw.get("world_layer")
    title = optional_bounded_text(raw.get("title"), 160)
    content = optional_bounded_text(raw.get("content"), 8000)
    if full_snapshot:
        if (
            item_type not in ITEM_TYPES
            or perspective not in PERSPECTIVES
            or world_layer not in WORLD_LAYERS
            or title is None
            or content is None
        ):
            return None
        candidate.update(
            item_type=item_type,
            perspective=perspective,
            world_layer=world_layer,
            title=title,
            content=content,
        )
    else:
        for field_name, value, allowed in (
            ("item_type", item_type, ITEM_TYPES),
            ("perspective", perspective, PERSPECTIVES),
            ("world_layer", world_layer, WORLD_LAYERS),
        ):
            if field_name in raw:
                if value not in allowed:
                    return None
                candidate[field_name] = value
        if "title" in raw:
            if title is None:
                return None
            candidate["title"] = title
        if "content" in raw:
            if content is None:
                return None
            candidate["content"] = content

    if "usage_condition" in raw:
        usage_condition = optional_bounded_text(raw.get("usage_condition"), 2000)
        if raw.get("usage_condition") is not None and usage_condition is None:
            return None
        candidate["usage_condition"] = usage_condition
    elif full_snapshot:
        candidate["usage_condition"] = None

    if "confidence" in raw:
        confidence = finite_number(raw.get("confidence"), minimum=0, maximum=1)
        if confidence is None:
            return None
        candidate["confidence"] = confidence
    elif full_snapshot:
        candidate["confidence"] = 1.0

    if "can_change" in raw:
        if not isinstance(raw.get("can_change"), bool):
            return None
        candidate["can_change"] = raw["can_change"]
    elif full_snapshot:
        candidate["can_change"] = True

    if "cooldown_days" in raw:
        cooldown_days = raw.get("cooldown_days")
        if (
            isinstance(cooldown_days, bool)
            or not isinstance(cooldown_days, int)
            or not 0 <= cooldown_days <= 3650
        ):
            return None
        candidate["cooldown_days"] = cooldown_days
    elif full_snapshot:
        candidate["cooldown_days"] = 14

    if "metadata" in raw:
        if not isinstance(raw.get("metadata"), dict):
            return None
        candidate["metadata"] = sanitize_metadata(raw["metadata"])
    elif full_snapshot:
        candidate["metadata"] = {}

    if operation == "update" and not set(candidate).intersection(
        {
            "item_type",
            "perspective",
            "world_layer",
            "title",
            "content",
            "usage_condition",
            "confidence",
            "can_change",
            "cooldown_days",
            "metadata",
        }
    ):
        return None
    return candidate


def validate_chapter_candidate(
    raw: Any,
    *,
    user_id: UUID,
    source_message_id: str,
) -> dict[str, Any] | None:
    """校验章节候选，并在缺少来源键时生成与模型文案无关的稳定键。"""

    if raw is None:
        return None
    if not isinstance(raw, dict) or raw.get("operation") not in {None, "create", "open"}:
        return None
    title = optional_bounded_text(raw.get("title"), 160)
    summary = optional_bounded_text(raw.get("summary"), 8000)
    if title is None or summary is None:
        return None
    source_key = optional_bounded_text(raw.get("source_key"), 160)
    if raw.get("source_key") is not None and source_key is None:
        return None
    if source_key is None:
        source_key = build_chapter_source_key(user_id, source_message_id)
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        return None
    return {
        "source_key": source_key,
        "title": title,
        "summary": summary,
        "metadata": sanitize_metadata(metadata),
    }


def capture_item_candidate(
    session: Any,
    user_id: UUID,
    candidate: dict[str, Any],
    *,
    source_message_id: str,
    source_turn_id: str | None,
    occurred_at: datetime,
) -> int:
    """在已持有用户锁的同步事务内应用一个校验后的物件候选。"""

    operation = candidate["operation"]
    statement = select(RelationshipItem).where(RelationshipItem.user_id == user_id)
    has_explicit_target = candidate.get("target_id") is not None
    if has_explicit_target and operation in {"upsert", "update", "deactivate"}:
        statement = statement.where(RelationshipItem.id == candidate["target_id"])
    else:
        statement = statement.where(RelationshipItem.item_key == candidate.get("item_key"))
    existing = session.execute(statement.with_for_update()).scalar_one_or_none()

    if existing is None:
        # upsert 携带 target_id 时语义是“更新这个已加载对象”。目标已经不存在时
        # 不能退化成按新标题建一条记录，否则一次改名会留下两个关系物件。
        if operation not in {"create", "upsert"} or (operation == "upsert" and has_explicit_target):
            return 0
        metadata = with_capture_source(
            candidate.get("metadata", {}),
            source_message_id=source_message_id,
            source_turn_id=source_turn_id,
        )
        session.add(
            RelationshipItem(
                user_id=user_id,
                item_type=candidate["item_type"],
                perspective=candidate["perspective"],
                world_layer=candidate["world_layer"],
                item_key=candidate["item_key"],
                title=candidate["title"],
                content=candidate["content"],
                usage_condition=candidate["usage_condition"],
                confidence=candidate["confidence"],
                can_change=candidate["can_change"],
                status="active",
                cooldown_days=candidate["cooldown_days"],
                last_used_at=None,
                use_count=0,
                source_message_id=source_message_id,
                version=1,
                metadata_json=metadata,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
        )
        return 1

    if operation == "create" or source_already_applied(existing, source_message_id):
        return 0
    changed = apply_item_candidate(
        existing,
        candidate,
        source_message_id=source_message_id,
        source_turn_id=source_turn_id,
        occurred_at=occurred_at,
    )
    return int(changed)


def apply_item_candidate(
    item: Any,
    candidate: dict[str, Any],
    *,
    source_message_id: str,
    source_turn_id: str | None,
    occurred_at: datetime,
) -> bool:
    """原地修改一个 ORM/轻量物件，并返回是否发生领域状态变化。

    来源标记即使在语义完全相同时也会保存，以便以后重放仍然是幂等的；只有标题、
    内容、分类、使用条件、偏好参数或状态真正变化时才递增 ``version`` 并返回
    ``True``。这个划分避免模型重复输出相同 upsert 时制造虚假的版本变化。
    """

    if source_already_applied(item, source_message_id):
        return False
    operation = candidate["operation"]
    semantic_changed = False
    if operation == "deactivate":
        if item.status != "inactive":
            item.status = "inactive"
            semantic_changed = True
    else:
        mutable_fields = (
            "item_type",
            "perspective",
            "world_layer",
            "title",
            "content",
            "usage_condition",
            "confidence",
            "can_change",
            "cooldown_days",
        )
        for field_name in mutable_fields:
            if field_name not in candidate:
                continue
            new_value = candidate[field_name]
            if values_differ(getattr(item, field_name, None), new_value):
                setattr(item, field_name, new_value)
                semantic_changed = True
        if operation == "upsert" and item.status != "active":
            item.status = "active"
            semantic_changed = True

    existing_metadata = dict(getattr(item, "metadata_json", None) or {})
    candidate_metadata = candidate.get("metadata")
    if candidate_metadata:
        merged_metadata = {**existing_metadata, **candidate_metadata}
        if merged_metadata != existing_metadata:
            semantic_changed = True
        existing_metadata = merged_metadata
    item.metadata_json = with_capture_source(
        existing_metadata,
        source_message_id=source_message_id,
        source_turn_id=source_turn_id,
    )
    if semantic_changed:
        item.source_message_id = source_message_id
        item.version = max(1, int(getattr(item, "version", 1) or 1)) + 1
        item.updated_at = occurred_at
    return semantic_changed


def capture_chapter_candidate(
    session: Any,
    user_id: UUID,
    candidate: dict[str, Any],
    *,
    source_message_id: str,
    source_turn_id: str | None,
    occurred_at: datetime,
) -> int:
    """幂等关闭当前章节并按递增序号开启一个新章节。"""

    existing = session.execute(
        select(RelationshipChapter.id).where(
            RelationshipChapter.user_id == user_id,
            RelationshipChapter.source_key == candidate["source_key"],
        )
    ).scalar_one_or_none()
    if existing is not None:
        return 0

    current = session.execute(
        select(RelationshipChapter)
        .where(
            RelationshipChapter.user_id == user_id,
            RelationshipChapter.status == "current",
        )
        .with_for_update()
    ).scalar_one_or_none()
    if current is not None:
        close_current_chapter(current, occurred_at)

    maximum = session.execute(
        select(func.max(RelationshipChapter.sequence_no)).where(
            RelationshipChapter.user_id == user_id
        )
    ).scalar_one_or_none()
    sequence_no = next_chapter_sequence(maximum)
    metadata = dict(candidate.get("metadata") or {})
    if source_turn_id:
        metadata["source_turn_id"] = source_turn_id
    session.add(
        RelationshipChapter(
            user_id=user_id,
            sequence_no=sequence_no,
            source_key=candidate["source_key"],
            title=candidate["title"],
            summary=candidate["summary"],
            status="current",
            started_at=occurred_at,
            ended_at=None,
            representative_message_id=source_message_id,
            metadata_json=metadata,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
    )
    return 1


def resolve_usage_target_ids(context_items: Any, usage_refs: Any) -> list[UUID]:
    """把主回复的短引用与本轮上下文相交，返回去重后的可信物件 ID。"""

    if not isinstance(context_items, list) or not isinstance(usage_refs, list):
        return []
    ref_map: dict[str, UUID] = {}
    for item in context_items[:MAX_USAGE_REFS]:
        if not isinstance(item, dict):
            continue
        ref = optional_bounded_text(item.get("ref"), 16)
        item_id = try_parse_uuid(item.get("id"))
        if ref is not None and item_id is not None:
            ref_map[ref] = item_id

    requested: list[str] = []
    for raw in usage_refs[:MAX_USAGE_REFS]:
        if isinstance(raw, str):
            ref = optional_bounded_text(raw, 16)
        elif isinstance(raw, dict):
            ref = optional_bounded_text(
                raw.get("item_ref") or raw.get("itemRef") or raw.get("ref"),
                16,
            )
        else:
            ref = None
        if ref is not None:
            requested.append(ref)

    result: list[UUID] = []
    seen: set[UUID] = set()
    for ref in requested:
        item_id = ref_map.get(ref)
        if item_id is not None and item_id not in seen:
            seen.add(item_id)
            result.append(item_id)
    return result


def mark_item_used(
    item: Any,
    *,
    used_at: datetime,
    source_turn_id: str | None,
) -> bool:
    """原地递增一次物件使用统计；提供回合 ID 时保证重放幂等。"""

    metadata = dict(getattr(item, "metadata_json", None) or {})
    turn_ids = bounded_string_history(metadata.get("usage_turn_ids"), MAX_USAGE_TURN_IDS)
    if source_turn_id and source_turn_id in turn_ids:
        return False
    if source_turn_id:
        turn_ids = append_bounded(turn_ids, source_turn_id, MAX_USAGE_TURN_IDS)
        metadata["usage_turn_ids"] = turn_ids
    item.metadata_json = metadata
    item.last_used_at = normalize_utc(used_at)
    item.use_count = max(0, int(getattr(item, "use_count", 0) or 0)) + 1
    item.updated_at = normalize_utc(used_at)
    return True


def source_already_applied(item: Any, source_message_id: str) -> bool:
    """判断来源消息是否已经作用于物件，包括较早但仍在有界历史中的来源。"""

    if getattr(item, "source_message_id", None) == source_message_id:
        return True
    metadata = getattr(item, "metadata_json", None) or {}
    if not isinstance(metadata, dict):
        return False
    return source_message_id in bounded_string_history(
        metadata.get("capture_source_ids"),
        MAX_CAPTURE_SOURCE_IDS,
    )


def with_capture_source(
    metadata: Any,
    *,
    source_message_id: str,
    source_turn_id: str | None,
) -> dict[str, Any]:
    """返回带有界来源历史的新元数据字典，不原地修改调用方对象。"""

    result = dict(metadata) if isinstance(metadata, dict) else {}
    source_ids = bounded_string_history(
        result.get("capture_source_ids"),
        MAX_CAPTURE_SOURCE_IDS,
    )
    result["capture_source_ids"] = append_bounded(
        source_ids,
        source_message_id,
        MAX_CAPTURE_SOURCE_IDS,
    )
    if source_turn_id:
        result["source_turn_id"] = source_turn_id
    return result


def build_chapter_source_key(user_id: UUID | str, source_message_id: str) -> str:
    """由可信用户与客户端消息 ID 生成不受模型文案漂移影响的章节来源键。"""

    parsed_user_id = UUID(str(user_id))
    normalized_source_id = bounded_text(source_message_id, 128)
    if normalized_source_id is None:
        raise ValueError("章节来源消息 ID 不能为空")
    digest = hashlib.sha256(
        f"{parsed_user_id}:{normalized_source_id}".encode("utf-8")
    ).hexdigest()
    return f"chapter:{digest}"


def next_chapter_sequence(current_maximum: Any) -> int:
    """把数据库最大章节序号安全转换成下一个从一开始的正整数。"""

    try:
        maximum = int(current_maximum or 0)
    except (TypeError, ValueError):
        maximum = 0
    return max(0, maximum) + 1


def close_current_chapter(chapter: Any, ended_at: datetime) -> None:
    """原地关闭当前章节并同步结束、更新时间，供 ORM 和轻量测试对象复用。"""

    normalized = normalize_utc(ended_at)
    chapter.status = "closed"
    chapter.ended_at = normalized
    chapter.updated_at = normalized


def acquire_user_knowledge_lock(session: Any, user_id: UUID) -> None:
    """获取用户级事务 advisory lock，串行化该用户的关系知识投影写入。"""

    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"aura_relationship_knowledge:{user_id}"},
    )


async def list_relationship_items(
    session: AsyncSession,
    user_id: str,
    *,
    item_type: str | None = None,
    status: str | None = "active",
    world_layer: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """为 HTTP 管理接口读取当前用户的关系物件列表。

    与聊天入口不同，本函数会把无效过滤条件和数据库故障转换成
    :class:`RelationshipKnowledgeServiceError`，便于路由统一返回中文错误。
    """

    parsed_user_id = parse_http_uuid(user_id, "用户 ID")
    if item_type is not None and item_type not in ITEM_TYPES:
        raise RelationshipKnowledgeServiceError("关系物件类型无效")
    if status is not None and status not in ITEM_STATUSES:
        raise RelationshipKnowledgeServiceError("关系物件状态无效")
    if world_layer is not None and world_layer not in WORLD_LAYERS:
        raise RelationshipKnowledgeServiceError("关系物件事实层无效")

    statement = select(RelationshipItem).where(RelationshipItem.user_id == parsed_user_id)
    if item_type is not None:
        statement = statement.where(RelationshipItem.item_type == item_type)
    if status is not None:
        statement = statement.where(RelationshipItem.status == status)
    if world_layer is not None:
        statement = statement.where(RelationshipItem.world_layer == world_layer)
    statement = statement.order_by(RelationshipItem.updated_at.desc()).limit(
        max(1, min(int(limit), 200))
    )
    try:
        result = await session.execute(statement)
    except SQLAlchemyError as exc:
        raise RelationshipKnowledgeServiceError(
            "关系物件读取失败，请稍后重试",
            status_code=503,
        ) from exc
    return [relationship_item_dict(item) for item in result.scalars().all()]


async def get_relationship_item(
    session: AsyncSession,
    user_id: str,
    item_id: str,
) -> dict[str, Any]:
    """读取一条属于当前用户的关系物件，不向其他用户泄露存在性。"""

    parsed_user_id = parse_http_uuid(user_id, "用户 ID")
    parsed_item_id = parse_http_uuid(item_id, "关系物件 ID")
    try:
        result = await session.execute(
            select(RelationshipItem).where(
                RelationshipItem.id == parsed_item_id,
                RelationshipItem.user_id == parsed_user_id,
            )
        )
    except SQLAlchemyError as exc:
        raise RelationshipKnowledgeServiceError(
            "关系物件读取失败，请稍后重试",
            status_code=503,
        ) from exc
    item = result.scalar_one_or_none()
    if item is None:
        raise RelationshipKnowledgeServiceError("关系物件不存在", status_code=404)
    return relationship_item_dict(item)


async def list_relationship_chapters(
    session: AsyncSession,
    user_id: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """按时间线倒序读取当前用户的关系章节。"""

    parsed_user_id = parse_http_uuid(user_id, "用户 ID")
    try:
        result = await session.execute(
            select(RelationshipChapter)
            .where(RelationshipChapter.user_id == parsed_user_id)
            .order_by(RelationshipChapter.sequence_no.desc())
            .limit(max(1, min(int(limit), 200)))
        )
    except SQLAlchemyError as exc:
        raise RelationshipKnowledgeServiceError(
            "关系章节读取失败，请稍后重试",
            status_code=503,
        ) from exc
    return [relationship_chapter_dict(chapter) for chapter in result.scalars().all()]


def relationship_item_dict(item: Any) -> dict[str, Any]:
    """把 ORM 关系物件转换成适合 HTTP JSON 序列化的字典。"""

    return {
        "id": str(item.id),
        "itemType": item.item_type,
        "perspective": item.perspective,
        "worldLayer": item.world_layer,
        "itemKey": item.item_key,
        "title": item.title,
        "content": item.content,
        "usageCondition": item.usage_condition,
        "confidence": float(item.confidence),
        "canChange": bool(item.can_change),
        "status": item.status,
        "cooldownDays": item.cooldown_days,
        "lastUsedAt": iso_or_none(item.last_used_at),
        "useCount": item.use_count,
        "sourceMessageId": item.source_message_id,
        "version": item.version,
        "metadata": dict(item.metadata_json or {}),
        "createdAt": iso_or_none(item.created_at),
        "updatedAt": iso_or_none(item.updated_at),
    }


def relationship_chapter_dict(chapter: Any) -> dict[str, Any]:
    """把 ORM 关系章节转换成适合 HTTP JSON 序列化的字典。"""

    return {
        "id": str(chapter.id),
        "sequenceNo": chapter.sequence_no,
        "sourceKey": chapter.source_key,
        "title": chapter.title,
        "summary": chapter.summary,
        "status": chapter.status,
        "startedAt": iso_or_none(chapter.started_at),
        "endedAt": iso_or_none(chapter.ended_at),
        "representativeMessageId": chapter.representative_message_id,
        "metadata": dict(chapter.metadata_json or {}),
        "createdAt": iso_or_none(chapter.created_at),
        "updatedAt": iso_or_none(chapter.updated_at),
    }


def parse_http_uuid(value: Any, label: str) -> UUID:
    """解析 HTTP 路径或身份中的 UUID，并抛出中文领域错误。"""

    parsed = try_parse_uuid(value)
    if parsed is None:
        raise RelationshipKnowledgeServiceError(f"{label}无效")
    return parsed


def try_parse_uuid(value: Any) -> UUID | None:
    """尽力解析 UUID；模型候选路径使用 ``None`` 表示无效而不抛异常。"""

    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def bounded_text(value: Any, maximum_length: int) -> str | None:
    """只接受非空且不超过上限的字符串，不截断可能具有身份含义的字段。"""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > maximum_length:
        return None
    return normalized


def optional_bounded_text(value: Any, maximum_length: int) -> str | None:
    """校验可选文本；``None`` 和空白都统一为 ``None``。"""

    if value is None:
        return None
    return bounded_text(value, maximum_length)


def finite_number(value: Any, *, minimum: float, maximum: float) -> float | None:
    """把非布尔有限数值限制到闭区间内，非法值返回 ``None``。"""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        return None
    return number


def sanitize_metadata(value: dict[str, Any]) -> dict[str, Any]:
    """复制小型 JSON 元数据并移除服务保留键；不可序列化内容整体丢弃。"""

    cleaned = {
        str(key)[:80]: item
        for key, item in list(value.items())[:32]
        if str(key) not in INTERNAL_METADATA_KEYS
    }
    try:
        encoded = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError, OverflowError):
        return {}
    if len(encoded) > 8000:
        return {}
    return json.loads(encoded)


def candidate_identity(candidate: dict[str, Any]) -> str:
    """生成批次内去重身份；优先使用明确 UUID，否则使用稳定 item_key。"""

    target_id = candidate.get("target_id")
    if target_id is not None:
        return f"id:{target_id}"
    return f"key:{candidate.get('item_key')}"


def bounded_string_history(value: Any, limit: int) -> list[str]:
    """从持久化元数据中恢复去重后的有界非空字符串历史。"""

    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value[-limit:]:
        if isinstance(item, str) and item and item not in result:
            result.append(item)
    return result[-limit:]


def append_bounded(items: list[str], value: str, limit: int) -> list[str]:
    """把值追加到去重历史末尾，并仅保留最近 ``limit`` 项。"""

    result = [item for item in items if item != value]
    result.append(value)
    return result[-limit:]


def values_differ(current: Any, candidate: Any) -> bool:
    """比较 ORM Numeric 等值与普通候选值，避免 Decimal/float 误判版本变化。"""

    if isinstance(candidate, float) and isinstance(current, (int, float)):
        return float(current) != candidate
    try:
        if isinstance(candidate, float) and current is not None:
            return float(current) != candidate
    except (TypeError, ValueError):
        pass
    return current != candidate


def normalize_utc(value: datetime) -> datetime:
    """把无时区时间按 UTC 解释，并统一转换成 UTC。"""

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso_or_none(value: datetime | None) -> str | None:
    """将可选数据库时间转换成 UTC ISO 字符串。"""

    return normalize_utc(value).isoformat() if value is not None else None
