"""共同宠物的认证 HTTP API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_store import SessionDep, get_current_user_id
from app.core.pet.service import (
    PetServiceError,
    adopt_pet,
    get_pet_snapshot,
    list_pet_events,
    perform_pet_action,
    rename_pet,
)
from app.schemas.pet import PetActionRequest, PetAdoptRequest, PetRenameRequest
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/pet", tags=["共同宠物"])


@router.post("/adopt", response_model=SuccessResponse, summary="领养共同宠物")
async def adopt_companion_pet(
    request: PetAdoptRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """为当前 JWT 用户领养唯一的共同宠物。

    Args:
        request: 名字、物种、性格和领养幂等请求 ID。
        current_user_id: 从 Bearer JWT 解析的用户 ID，不接受客户端指定所有者。
        session: FastAPI 注入的异步数据库会话。

    Raises:
        HTTPException: 用户不存在、已经领养宠物或并发领养发生冲突。
    """

    try:
        data = await adopt_pet(session, current_user_id, request)
    except PetServiceError as exc:
        raise_pet_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("", response_model=SuccessResponse, summary="查看共同宠物")
async def read_companion_pet(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """惰性结算并返回当前 JWT 用户的宠物；尚未领养时 ``data`` 为 ``None``。"""

    try:
        data = await get_pet_snapshot(session, current_user_id)
    except PetServiceError as exc:
        raise_pet_http_exception(exc)
    return SuccessResponse(data=data)


@router.post("/actions", response_model=SuccessResponse, summary="照顾共同宠物")
async def care_for_companion_pet(
    request: PetActionRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """原子执行喂食、玩耍、梳毛、洗澡、抚摸或睡觉动作。

    相同 ``clientActionId`` 只重放第一次结果；可选 ``expectedVersion`` 过期时
    返回 409，不会覆盖已经发生的状态变化。
    """

    try:
        data = await perform_pet_action(session, current_user_id, request)
    except PetServiceError as exc:
        raise_pet_http_exception(exc)
    return SuccessResponse(data=data)


@router.patch("/name", response_model=SuccessResponse, summary="修改共同宠物名字")
async def rename_companion_pet(
    request: PetRenameRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """幂等修改当前用户宠物名字，不改变照顾数值和心情。"""

    try:
        data = await rename_pet(session, current_user_id, request)
    except PetServiceError as exc:
        raise_pet_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("/events", response_model=SuccessResponse, summary="读取共同宠物事件")
async def read_companion_pet_events(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
):
    """按时间倒序返回领养、照顾、改名和成长事实，最多 200 条。"""

    try:
        items = await list_pet_events(session, current_user_id, limit=limit)
    except PetServiceError as exc:
        raise_pet_http_exception(exc)
    return SuccessResponse(data={"items": items})


def raise_pet_http_exception(exc: PetServiceError) -> None:
    """把宠物领域异常转换为保留中文详情和状态码的 FastAPI 异常。

    Raises:
        HTTPException: 每次调用都会抛出，不会正常返回。
    """

    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
