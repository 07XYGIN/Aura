from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_store import get_current_user_id
from app.db.models import (
    AuraProfile,
    ChatMessage,
    EmotionSnapshot,
    MemoryItem,
    RelationshipState,
    SelfChangelogEntry,
)
from app.db.session import get_db_session
from app.schemas.admin import SelfUpdateCreateRequest, SelfUpdatePatchRequest
from app.schemas.response import SuccessResponse

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
)


@router.get("/aura/{resource}", response_model=SuccessResponse)
async def list_aura_admin_resource(
    resource: str,
    _admin_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
    userId: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
):
    if resource == "profiles":
        return SuccessResponse(
            data=await list_admin_rows(
                session,
                AuraProfile,
                [AuraProfile.nickname, AuraProfile.persona_summary, AuraProfile.voice_style],
                userId,
                keyword,
                page,
                pageSize,
                aura_profile_dict,
                AuraProfile.updated_at.desc(),
            )
        )
    if resource == "personas":
        return SuccessResponse(
            data=await list_admin_rows(
                session,
                AuraProfile,
                [AuraProfile.nickname, AuraProfile.voice_style, AuraProfile.boundaries, AuraProfile.persona_summary],
                userId,
                keyword,
                page,
                pageSize,
                aura_persona_dict,
                AuraProfile.updated_at.desc(),
            )
        )
    if resource == "relationships":
        return SuccessResponse(
            data=await list_admin_rows(
                session,
                RelationshipState,
                [
                    RelationshipState.relationship_stage,
                    RelationshipState.current_mood,
                    cast(RelationshipState.metadata_json, String),
                ],
                userId,
                keyword,
                page,
                pageSize,
                relationship_state_dict,
                RelationshipState.updated_at.desc(),
            )
        )
    if resource == "messages":
        return SuccessResponse(
            data=await list_admin_rows(
                session,
                ChatMessage,
                [ChatMessage.sender_type, ChatMessage.content, ChatMessage.content_type],
                userId,
                keyword,
                page,
                pageSize,
                chat_message_admin_dict,
                ChatMessage.created_at.desc(),
            )
        )
    if resource == "emotions":
        return SuccessResponse(
            data=await list_admin_rows(
                session,
                EmotionSnapshot,
                [EmotionSnapshot.dominant_emotion, EmotionSnapshot.source, EmotionSnapshot.reason],
                userId,
                keyword,
                page,
                pageSize,
                emotion_snapshot_admin_dict,
                EmotionSnapshot.created_at.desc(),
            )
        )
    if resource == "memories":
        return SuccessResponse(
            data=await list_admin_rows(
                session,
                MemoryItem,
                [MemoryItem.title, MemoryItem.content, MemoryItem.memory_type, cast(MemoryItem.tags, String)],
                userId,
                keyword,
                page,
                pageSize,
                memory_item_admin_dict,
                MemoryItem.created_at.desc(),
            )
        )

    raise HTTPException(status_code=400, detail="resource is not supported")


@router.post("/self-updates", response_model=SuccessResponse)
async def create_self_update(
    request: SelfUpdateCreateRequest,
    _admin_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
):
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
        raise HTTPException(status_code=409, detail="self update already exists for this date and title") from exc
    await session.refresh(entry)
    return SuccessResponse(data=self_update_dict(entry))


@router.get("/self-updates", response_model=SuccessResponse)
async def list_self_updates(
    _admin_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
    reacted: bool | None = Query(default=None),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, ge=1, le=100),
):
    filters = []
    if reacted is not None:
        filters.append(SelfChangelogEntry.reacted.is_(reacted))

    count_result = await session.execute(select(func.count(SelfChangelogEntry.id)).where(*filters))
    total = int(count_result.scalar_one())

    order_column = SelfChangelogEntry.occurred_at.asc() if order == "asc" else SelfChangelogEntry.occurred_at.desc()
    result = await session.execute(
        select(SelfChangelogEntry)
        .where(*filters)
        .order_by(order_column, SelfChangelogEntry.created_at.desc())
        .limit(limit)
    )
    items = [self_update_dict(entry) for entry in result.scalars().all()]
    return SuccessResponse(data={"items": items, "total": total, "limit": limit})


@router.patch("/self-updates/{entry_id}", response_model=SuccessResponse)
async def update_self_update(
    entry_id: str,
    request: SelfUpdatePatchRequest,
    _admin_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
):
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
        raise HTTPException(status_code=409, detail="self update already exists for this date and title") from exc
    await session.refresh(entry)
    return SuccessResponse(data=self_update_dict(entry))


@router.delete("/self-updates/{entry_id}", response_model=SuccessResponse)
async def delete_self_update(
    entry_id: str,
    _admin_user_id: Annotated[str, Depends(get_current_user_id)],
    session: AsyncSession = Depends(get_db_session),
):
    parsed_id = parse_uuid(entry_id)
    result = await session.execute(delete(SelfChangelogEntry).where(SelfChangelogEntry.id == parsed_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="self update not found")
    await session.commit()
    return SuccessResponse(data={"deleted": True, "id": entry_id})


async def get_self_update_or_404(session: AsyncSession, entry_id: str) -> SelfChangelogEntry:
    entry = await session.get(SelfChangelogEntry, parse_uuid(entry_id))
    if entry is None:
        raise HTTPException(status_code=404, detail="self update not found")
    return entry


async def list_admin_rows(
    session: AsyncSession,
    model,
    keyword_columns: list[Any],
    user_id: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
    mapper,
    *order_by,
) -> dict[str, Any]:
    filters = []
    parsed_user_id = parse_optional_uuid(user_id)
    if parsed_user_id is not None:
        filters.append(model.user_id == parsed_user_id)

    cleaned_keyword = clean_optional_text(keyword)
    if cleaned_keyword:
        pattern = f"%{cleaned_keyword}%"
        filters.append(or_(*[column.ilike(pattern) for column in keyword_columns]))

    count_result = await session.execute(select(func.count(model.id)).where(*filters))
    total = int(count_result.scalar_one())
    offset = (page - 1) * page_size
    result = await session.execute(
        select(model)
        .where(*filters)
        .order_by(*order_by)
        .offset(offset)
        .limit(page_size)
    )
    return {
        "items": [mapper(item) for item in result.scalars().all()],
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def parse_optional_uuid(value: str | None) -> UUID | None:
    if value is None or not value.strip():
        return None
    return parse_uuid(value)


def aura_profile_dict(profile: AuraProfile) -> dict[str, Any]:
    return {
        "id": str(profile.id),
        "userId": str(profile.user_id),
        "nickname": profile.nickname,
        "gender": None,
        "age": None,
        "locale": "zh-CN",
        "timezone": "Asia/Shanghai",
        "updatedAt": datetime_iso(profile.updated_at),
    }


def aura_persona_dict(profile: AuraProfile) -> dict[str, Any]:
    return {
        "id": str(profile.id),
        "userId": str(profile.user_id),
        "name": profile.nickname,
        "tone": profile.voice_style or profile.greeting_style,
        "boundary": profile.boundaries,
        "version": profile.greeting_style,
        "updatedAt": datetime_iso(profile.updated_at),
    }


def relationship_state_dict(state: RelationshipState) -> dict[str, Any]:
    return {
        "id": str(state.id),
        "userId": str(state.user_id),
        "stage": state.relationship_stage,
        "affinityScore": state.intimacy_level,
        "trustScore": state.trust_level,
        "lastInteractionAt": datetime_iso(state.last_interaction_at),
        "updatedAt": datetime_iso(state.updated_at),
    }


def chat_message_admin_dict(message: ChatMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "sessionId": str(message.session_id),
        "userId": str(message.user_id),
        "role": message.sender_type,
        "content": message.content,
        "createdAt": datetime_iso(message.created_at),
    }


def emotion_snapshot_admin_dict(snapshot: EmotionSnapshot) -> dict[str, Any]:
    scores = snapshot.emotion_scores or {}
    confidence = scores.get("confidence") if isinstance(scores, dict) else None
    return {
        "id": str(snapshot.id),
        "userId": str(snapshot.user_id),
        "sessionId": str(snapshot.session_id) if snapshot.session_id else None,
        "userEmotion": snapshot.dominant_emotion,
        "auraMood": snapshot.source,
        "confidence": decimal_to_float(confidence),
        "createdAt": datetime_iso(snapshot.created_at),
    }


def memory_item_admin_dict(memory: MemoryItem) -> dict[str, Any]:
    return {
        "id": str(memory.id),
        "userId": str(memory.user_id),
        "title": memory.title,
        "content": memory.content,
        "tags": memory.tags or [],
        "source": memory.memory_type,
        "createdAt": datetime_iso(memory.created_at),
    }


def parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="id must be a valid UUID") from exc


def decimal_to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def clean_required_text(value: str | None, field_name: str, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return value.strip()[:max_length]


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def clean_category(value: str) -> str:
    cleaned = (value or "infra").strip().lower()[:64]
    return cleaned or "infra"


def parse_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def datetime_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def self_update_dict(entry: SelfChangelogEntry) -> dict[str, Any]:
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
