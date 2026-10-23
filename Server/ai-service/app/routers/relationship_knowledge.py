"""查看 Aura 已形成的关系物件和低频关系章节。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_store import SessionDep, get_current_user_id
from app.core.continuity.knowledge import (
    RelationshipKnowledgeServiceError,
    get_relationship_item,
    list_relationship_chapters,
    list_relationship_items,
)
from app.schemas.relationship_knowledge import (
    RelationshipItemStatus,
    RelationshipItemType,
    RelationshipWorldLayer,
)
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/continuity", tags=["关系知识"])


@router.get("/items", response_model=SuccessResponse, summary="查询关系物件")
async def read_relationship_items(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    itemType: RelationshipItemType | None = None,
    status: RelationshipItemStatus | None = "active",
    worldLayer: RelationshipWorldLayer | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """读取当前唯一用户的共同记忆、私人语言、立场、纠偏和边界。

    返回的 ``confidence`` 只表示记录有多少真实对话依据，不是亲密度，也不会
    影响 Aura 是否在乎小乔。默认只返回仍然生效的物件。
    """

    try:
        items = await list_relationship_items(
            session,
            current_user_id,
            item_type=itemType,
            status=status,
            world_layer=worldLayer,
            limit=limit,
        )
    except RelationshipKnowledgeServiceError as exc:
        raise_knowledge_http_exception(exc)
    return SuccessResponse(data={"items": items})


@router.get("/items/{item_id}", response_model=SuccessResponse, summary="读取关系物件详情")
async def read_relationship_item(
    item_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """按 ID 读取一条属于当前 JWT 用户的关系物件。"""

    try:
        item = await get_relationship_item(session, current_user_id, item_id)
    except RelationshipKnowledgeServiceError as exc:
        raise_knowledge_http_exception(exc)
    return SuccessResponse(data=item)


@router.get("/chapters", response_model=SuccessResponse, summary="查询关系章节")
async def read_relationship_chapters(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
):
    """按最新优先返回真实重要事件形成的关系时间线。"""

    try:
        chapters = await list_relationship_chapters(
            session,
            current_user_id,
            limit=limit,
        )
    except RelationshipKnowledgeServiceError as exc:
        raise_knowledge_http_exception(exc)
    return SuccessResponse(data={"items": chapters})


def raise_knowledge_http_exception(exc: RelationshipKnowledgeServiceError) -> None:
    """将服务层中文领域错误转换成保留状态码的 HTTP 异常。"""

    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
