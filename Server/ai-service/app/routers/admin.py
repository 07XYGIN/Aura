from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_store import get_current_user_id
from app.core.memory.service import apply_memory_merge, list_memory_merge_candidates
from app.db.models import SelfChangelogEntry
from app.db.schema_guard import ensure_self_changelog_admin_fields_async
from app.db.session import get_db_session
from app.schemas.admin import MemoryMergeConfirmRequest, SelfUpdateCreateRequest, SelfUpdatePatchRequest
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.get("/memory-merge/candidates", response_model=SuccessResponse)
async def list_memory_merge_candidate_rows(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    threshold: float = Query(default=0.85, ge=0.0, le=1.0),
    limit: int = Query(default=20, ge=1, le=50),
    scanLimit: int = Query(default=300, ge=2, le=1000),
):
    """查找当前用户可能重复、适合人工合并的长期记忆组。

    ``threshold`` 控制最低相似度，``scanLimit`` 控制候选扫描范围，``limit``
    控制最终返回组数。
    """
    return SuccessResponse(
        data=list_memory_merge_candidates(
            user_id=current_user_id,
            threshold=threshold,
            limit=limit,
            scan_limit=scanLimit,
        )
    )


@router.post("/memory-merge/confirm", response_model=SuccessResponse)
async def confirm_memory_merge(
    request: MemoryMergeConfirmRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """按管理端确认结果合并当前用户的多条记忆。

    Raises:
        HTTPException: 来源记忆不足、无效或不属于当前用户。
    """
    try:
        result = apply_memory_merge(
            user_id=current_user_id,
            memory_keys=request.memory_keys,
            merged_title=request.merged_title,
            merged_content=request.merged_content,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SuccessResponse(data=result)


@router.post("/self-updates", response_model=SuccessResponse)
async def create_self_update(
    request: SelfUpdateCreateRequest,
    _current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
):
    """创建一条 Aura 自身更新记录并提交数据库。

    Raises:
        HTTPException: 清洗后缺少必填字段，或日期与标题发生唯一性冲突。
    """
    await ensure_self_changelog_admin_fields_async()
    occurred_at = normalize_datetime(request.occurred_at)
    entry = SelfChangelogEntry(
        change_date=occurred_at.date(),
        occurred_at=occurred_at,
        title=clean_required_text(request.title, "title", 160),
        detail=clean_optional_text(request.detail),
        category=clean_category(request.category),
        metadata_json=parse_metadata(request.metadata),
    )
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="相同日期和标题的自我更新已经存在") from exc
    await session.refresh(entry)
    return SuccessResponse(data=self_update_dict(entry))


@router.get("/self-updates", response_model=SuccessResponse)
async def list_self_updates(
    _current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
    reacted: bool | None = Query(default=None),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, ge=1, le=100),
):
    """按回应状态筛选并排序返回 Aura 自身更新记录。

    Returns:
        包含记录列表、匹配总数和本次条数上限的统一响应。
    """
    await ensure_self_changelog_admin_fields_async()
    filters = [SelfChangelogEntry.reacted.is_(reacted)] if reacted is not None else []
    count_result = await session.execute(select(func.count(SelfChangelogEntry.id)).where(*filters))
    total = int(count_result.scalar_one())
    order_column = SelfChangelogEntry.occurred_at.asc() if order == "asc" else SelfChangelogEntry.occurred_at.desc()
    result = await session.execute(
        select(SelfChangelogEntry)
        .where(*filters)
        .order_by(order_column, SelfChangelogEntry.created_at.desc())
        .limit(limit)
    )
    return SuccessResponse(
        data={
            "items": [self_update_dict(entry) for entry in result.scalars().all()],
            "total": total,
            "limit": limit,
        }
    )


@router.patch("/self-updates/{entry_id}", response_model=SuccessResponse)
async def update_self_update(
    entry_id: str,
    request: SelfUpdatePatchRequest,
    _current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
):
    """只更新请求中显式提供的自更新记录字段。

    ``reacted`` 变为真时同时记录回应时间，改回假时清空回应时间。
    """
    await ensure_self_changelog_admin_fields_async()
    entry = await get_self_update_or_404(session, entry_id)
    fields = request.model_fields_set
    if "occurred_at" in fields:
        occurred_at = normalize_datetime(request.occurred_at)
        entry.occurred_at = occurred_at
        entry.change_date = occurred_at.date()
    if "title" in fields:
        entry.title = clean_required_text(request.title, "title", 160)
    if "detail" in fields:
        entry.detail = clean_optional_text(request.detail)
    if "category" in fields:
        entry.category = clean_category(request.category or "infra")
    if "metadata" in fields:
        entry.metadata_json = parse_metadata(request.metadata)
    if "reacted" in fields and request.reacted is not None:
        entry.reacted = request.reacted
        entry.reacted_at = datetime.now(UTC) if request.reacted else None
    entry.updated_at = datetime.now(UTC)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="相同日期和标题的自我更新已经存在") from exc
    await session.refresh(entry)
    return SuccessResponse(data=self_update_dict(entry))


@router.delete("/self-updates/{entry_id}", response_model=SuccessResponse)
async def delete_self_update(
    entry_id: str,
    _current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
):
    """按 UUID 删除一条 Aura 自身更新记录并提交事务。

    Raises:
        HTTPException: ID 格式无效或记录不存在。
    """
    await ensure_self_changelog_admin_fields_async()
    result = await session.execute(delete(SelfChangelogEntry).where(SelfChangelogEntry.id == parse_uuid(entry_id)))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="没有找到这条自我更新")
    await session.commit()
    return SuccessResponse(data={"deleted": True, "id": entry_id})


async def get_self_update_or_404(session: AsyncSession, entry_id: str) -> SelfChangelogEntry:
    """按 UUID 获取自更新 ORM 记录，未找到时抛出 HTTP 404。"""
    entry = await session.get(SelfChangelogEntry, parse_uuid(entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="没有找到这条自我更新")
    return entry


def parse_uuid(value: str) -> UUID:
    """解析 UUID 字符串，格式无效时转换为 HTTP 400。"""
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ID 必须是有效的 UUID") from exc


def normalize_datetime(value: datetime | None) -> datetime:
    """补齐可选时间：空值取当前 UTC，无时区值按 UTC 解释。"""
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def clean_required_text(value: str | None, field_name: str, max_length: int) -> str:
    """清理必填文本并截断到字段上限，空值时抛出 HTTP 400。"""
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=400, detail=f"缺少必填字段：{field_name}")
    return value.strip()[:max_length]


def clean_optional_text(value: str | None) -> str | None:
    """清理可选文本，将空字符串统一为 ``None``。"""
    if value is None:
        return None
    return value.strip() or None


def clean_category(value: str) -> str:
    """将更新分类规范为小写非空文本，并限制为 64 个字符。"""
    return (value or "infra").strip().lower()[:64] or "infra"


def parse_metadata(value: Any) -> dict[str, Any]:
    """只接受字典形式的元数据，其他类型降级为空字典。"""
    return value if isinstance(value, dict) else {}


def datetime_iso(value: datetime | None) -> str | None:
    """将可选日期时间转换为 ISO 8601 字符串。"""
    return value.isoformat() if value else None


def self_update_dict(entry: SelfChangelogEntry) -> dict[str, Any]:
    """将自更新 ORM 实体转换为 API 可序列化字典。"""
    return {
        "id": str(entry.id),
        "occurred_at": datetime_iso(entry.occurred_at),
        "change_date": entry.change_date.isoformat(),
        "title": entry.title,
        "detail": entry.detail,
        "category": entry.category,
        "reacted": entry.reacted,
        "reacted_at": datetime_iso(entry.reacted_at),
        "metadata": entry.metadata_json or {},
        "created_at": datetime_iso(entry.created_at),
        "updated_at": datetime_iso(entry.updated_at),
    }
