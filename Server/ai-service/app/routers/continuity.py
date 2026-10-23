"""关系连续性线程的认证 HTTP API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_store import SessionDep, get_current_user_id
from app.core.continuity.service import (
    RelationshipThreadServiceError,
    create_relationship_thread,
    get_relationship_thread,
    list_relationship_threads,
    transition_relationship_thread,
)
from app.schemas.continuity import (
    RelationshipThreadCreateRequest,
    RelationshipThreadTransitionRequest,
    ThreadStatus,
    ThreadType,
    WorldLayer,
)
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/continuity/threads", tags=["关系连续性"])


@router.post("", response_model=SuccessResponse, summary="创建关系连续性线程")
async def create_thread(
    request: RelationshipThreadCreateRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """为当前 JWT 用户幂等创建未完事项、承诺、冲突或项目任务。

    同一个 ``clientRequestId`` 重试只返回首次创建的线程；如果复用该 ID 却改变
    业务参数，服务会返回 409，避免网络重试悄悄创建另一条关系事实。
    """

    try:
        data = await create_relationship_thread(session, current_user_id, request)
    except RelationshipThreadServiceError as exc:
        raise_relationship_thread_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("", response_model=SuccessResponse, summary="查询关系连续性线程")
async def list_threads(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    threadType: ThreadType | None = None,
    status: ThreadStatus | None = None,
    worldLayer: WorldLayer | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """按可选类型、状态和事实层查询当前用户的线程。"""

    data = await list_relationship_threads(
        session,
        current_user_id,
        thread_type=threadType,
        status=status,
        world_layer=worldLayer,
        limit=limit,
    )
    return SuccessResponse(data={"items": data})


@router.get("/{thread_id}", response_model=SuccessResponse, summary="读取关系线程详情")
async def read_thread(
    thread_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """读取当前用户的一条线程及其不可变状态事件。"""

    try:
        data = await get_relationship_thread(session, current_user_id, thread_id)
    except RelationshipThreadServiceError as exc:
        raise_relationship_thread_http_exception(exc)
    return SuccessResponse(data=data)


@router.patch("/{thread_id}", response_model=SuccessResponse, summary="推进关系线程状态")
async def transition_thread(
    thread_id: str,
    request: RelationshipThreadTransitionRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """更新、跟进、解决或放弃当前用户的一条关系线程。"""

    try:
        data = await transition_relationship_thread(
            session,
            current_user_id,
            thread_id,
            request,
        )
    except RelationshipThreadServiceError as exc:
        raise_relationship_thread_http_exception(exc)
    return SuccessResponse(data=data)


def raise_relationship_thread_http_exception(exc: RelationshipThreadServiceError) -> None:
    """把连续性领域错误转换成保留中文详情的 FastAPI 异常。

    Raises:
        HTTPException: 每次调用都会抛出，不会正常返回。
    """

    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
