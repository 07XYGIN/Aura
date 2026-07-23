"""一起专注的认证 HTTP API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth_store import SessionDep, get_current_user_id
from app.core.focus.service import (
    FocusServiceError,
    apply_focus_action,
    get_current_focus_snapshot,
    report_focus_progress,
    start_focus_session,
)
from app.schemas.focus import FocusActionRequest, FocusProgressRequest, FocusStartRequest
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/focus", tags=["一起专注"])


@router.post("", response_model=SuccessResponse, summary="开始一起专注")
async def create_focus(
    request: FocusStartRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """为当前 JWT 用户开始幂等计时，不接受请求体指定其他用户。"""

    try:
        data = await start_focus_session(session, current_user_id, request)
    except FocusServiceError as exc:
        raise_focus_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("/current", response_model=SuccessResponse, summary="读取当前专注")
async def current_focus(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """读取当前计时、暂停或等待汇报的专注会话。"""

    try:
        data = await get_current_focus_snapshot(session, current_user_id)
    except FocusServiceError as exc:
        raise_focus_http_exception(exc)
    return SuccessResponse(data=data)


@router.post("/{focus_id}/actions", response_model=SuccessResponse, summary="控制专注状态")
async def change_focus(
    focus_id: str,
    request: FocusActionRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """暂停、恢复或取消当前用户的一次专注。"""

    try:
        data = await apply_focus_action(session, current_user_id, focus_id, request)
    except FocusServiceError as exc:
        raise_focus_http_exception(exc)
    return SuccessResponse(data=data)


@router.post("/{focus_id}/progress", response_model=SuccessResponse, summary="汇报专注进度")
async def submit_focus_progress(
    focus_id: str,
    request: FocusProgressRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """在结束问询后保存结果；明确卡点会成为待续项目线程。"""

    try:
        data = await report_focus_progress(session, current_user_id, focus_id, request)
    except FocusServiceError as exc:
        raise_focus_http_exception(exc)
    return SuccessResponse(data=data)


def raise_focus_http_exception(exc: FocusServiceError) -> None:
    """把专注领域错误转换成保留中文详情的 HTTP 异常。"""

    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
