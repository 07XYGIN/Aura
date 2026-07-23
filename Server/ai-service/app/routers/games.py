"""互动游戏的认证 HTTP API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_store import SessionDep, get_current_user_id
from app.core.games.bash.service import (
    BashGameServiceError,
    get_bash_game_snapshot,
    get_current_bash_game_snapshot,
    list_bash_game_moves,
    perform_user_move,
    resign_bash_game,
    start_bash_game,
)
from app.schemas.game import BashGameMoveRequest, BashGameResignRequest, BashGameStartRequest
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/games/bash", tags=["巴什博弈"])


@router.post("", response_model=SuccessResponse, summary="开始一局巴什博弈")
async def create_bash_game(
    request: BashGameStartRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """为当前 JWT 用户创建一局幂等的巴什博弈。

    Args:
        request: 棋局规则、难度、先手选项和客户端开始请求 ID。
        current_user_id: 从 Bearer JWT 解析出的用户 ID，不接受客户端指定他人。
        session: FastAPI 注入的异步数据库会话。

    Returns:
        包含棋局状态、本次新行动和最近行动的统一成功响应。

    Raises:
        HTTPException: 规则无效或当前用户已有另一局活动游戏。
    """

    try:
        data = await start_bash_game(session, current_user_id, request)
    except BashGameServiceError as exc:
        raise_bash_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("/current", response_model=SuccessResponse, summary="读取当前巴什棋局")
async def current_bash_game(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """返回当前 JWT 用户唯一的活动棋局；没有活动棋局时 ``data`` 为 ``None``。"""

    try:
        data = await get_current_bash_game_snapshot(session, current_user_id)
    except BashGameServiceError as exc:
        raise_bash_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("/{session_id}", response_model=SuccessResponse, summary="读取指定巴什棋局")
async def read_bash_game(
    session_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """按 UUID 返回属于当前 JWT 用户的一局游戏，其他用户的棋局按 404 处理。"""

    try:
        data = await get_bash_game_snapshot(session, current_user_id, session_id)
    except BashGameServiceError as exc:
        raise_bash_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("/{session_id}/moves", response_model=SuccessResponse, summary="读取巴什棋局行动")
async def read_bash_game_moves(
    session_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
):
    """按回合顺序返回指定棋局的不可变行动日志。

    ``session_id`` 同时用于所有权校验，``limit`` 限制单次最多返回 500 步。
    """

    try:
        data = await list_bash_game_moves(
            session,
            current_user_id,
            session_id,
            limit=limit,
        )
    except BashGameServiceError as exc:
        raise_bash_http_exception(exc)
    return SuccessResponse(data={"items": data})


@router.post("/{session_id}/moves", response_model=SuccessResponse, summary="执行巴什取子行动")
async def move_bash_game(
    session_id: str,
    request: BashGameMoveRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """为当前用户原子执行一次取子和 Aura 的回应行动。

    Raises:
        HTTPException: 取子不合法时为 400；版本、轮次或并发冲突时为 409；
            棋局不存在或不属于当前用户时为 404。
    """

    try:
        data = await perform_user_move(session, current_user_id, session_id, request)
    except BashGameServiceError as exc:
        raise_bash_http_exception(exc)
    return SuccessResponse(data=data)


@router.post("/{session_id}/resign", response_model=SuccessResponse, summary="认输并结束巴什棋局")
async def resign_current_bash_game(
    session_id: str,
    request: BashGameResignRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """按乐观版本结束当前用户的活动棋局，并将 Aura 记为胜者。"""

    try:
        data = await resign_bash_game(
            session,
            current_user_id,
            session_id,
            request.expected_version,
        )
    except BashGameServiceError as exc:
        raise_bash_http_exception(exc)
    return SuccessResponse(data=data)


def raise_bash_http_exception(exc: BashGameServiceError) -> None:
    """把领域服务异常转换为保留中文消息和状态码的 FastAPI 异常。

    Raises:
        HTTPException: 每次调用都会抛出，不会正常返回。
    """

    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
