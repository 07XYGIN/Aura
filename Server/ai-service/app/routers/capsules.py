"""时间胶囊、秘密保险箱和条件事件的认证 HTTP API。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_store import SessionDep, get_current_user_id
from app.core.continuity.capsules import (
    ConditionalMessageServiceError,
    cancel_conditional_message,
    create_conditional_message,
    get_conditional_message,
    list_conditional_messages,
    trigger_github_event_messages,
    trigger_project_status_messages,
    unlock_passphrase_message,
)
from app.schemas.capsule import (
    ConditionalMessageCancelRequest,
    ConditionalMessageCreateRequest,
    ConditionalMessageStatus,
    ConditionalMessageType,
    GitHubEventRequest,
    PassphraseUnlockRequest,
    ProjectStatusEventRequest,
)
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/continuity/capsules", tags=["条件消息"])


@router.post("", response_model=SuccessResponse, summary="创建时间胶囊或秘密保险箱")
async def create_capsule(
    request: ConditionalMessageCreateRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """使用 JWT 用户身份显式创建一条密封消息。

    请求模型没有 ``userId``，客户端不能替其他人创建。成功响应在条件成立前只
    返回标题和触发条件，``content`` 为 ``null``，口令摘要从不进入响应。
    """

    try:
        data = await create_conditional_message(session, current_user_id, request)
    except ConditionalMessageServiceError as exc:
        raise_capsule_http_exception(exc)
    return SuccessResponse(data=data)


@router.get("", response_model=SuccessResponse, summary="查询时间胶囊和秘密保险箱")
async def read_capsules(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    status: ConditionalMessageStatus | None = None,
    messageType: ConditionalMessageType | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """按当前 JWT 用户查询条件消息，密封正文不会出现在列表中。"""

    items = await list_conditional_messages(
        session,
        current_user_id,
        status=status,
        message_type=messageType,
        limit=limit,
    )
    return SuccessResponse(data={"items": items})


@router.get("/{message_id}", response_model=SuccessResponse, summary="读取条件消息详情")
async def read_capsule(
    message_id: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """读取一条属于当前用户的记录，其他用户的 ID 统一返回不存在。"""

    try:
        data = await get_conditional_message(session, current_user_id, message_id)
    except ConditionalMessageServiceError as exc:
        raise_capsule_http_exception(exc)
    return SuccessResponse(data=data)


@router.post("/{message_id}/cancel", response_model=SuccessResponse, summary="取消条件消息")
async def cancel_capsule(
    message_id: str,
    request: ConditionalMessageCancelRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """取消未投递记录；已经写入聊天历史的消息不能伪装撤回。"""

    try:
        data = await cancel_conditional_message(
            session,
            current_user_id,
            message_id,
            expected_version=request.expected_version,
            client_action_id=request.client_action_id,
        )
    except ConditionalMessageServiceError as exc:
        raise_capsule_http_exception(exc)
    return SuccessResponse(data=data)


@router.post("/{message_id}/unlock", response_model=SuccessResponse, summary="使用口令解锁保险箱")
async def unlock_capsule(
    message_id: str,
    request: PassphraseUnlockRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """精确校验口令，并把成功解锁的保险箱交给可靠主动消息 outbox。"""

    try:
        data = await unlock_passphrase_message(
            session,
            current_user_id,
            message_id,
            passphrase=request.passphrase,
            event_id=request.event_id,
        )
    except ConditionalMessageServiceError as exc:
        raise_capsule_http_exception(exc)
    return SuccessResponse(data=data)


@router.post("/events/project-status", response_model=SuccessResponse, summary="报告项目状态事件")
async def report_project_status(
    request: ProjectStatusEventRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """由未来的共同项目模块报告规范化状态，重复 eventId 不会重复触发。"""

    try:
        count = await trigger_project_status_messages(
            session,
            current_user_id,
            project_key=request.project_key,
            status=request.status,
            event_id=request.event_id,
            metadata=request.metadata,
        )
    except ConditionalMessageServiceError as exc:
        raise_capsule_http_exception(exc)
    return SuccessResponse(data={"triggeredCount": count})


@router.post("/events/github", response_model=SuccessResponse, summary="报告 GitHub 条件事件")
async def report_github_event(
    request: GitHubEventRequest,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
):
    """接收已规范化的 GitHub 事件，使用 deliveryId 保证重投幂等。

    这里是认证内部入口；后续 GitHub 女友功能会负责校验 Webhook 签名和仓库白名单，
    再调用同一个领域服务，不会让原始 payload 决定用户身份。
    """

    try:
        count = await trigger_github_event_messages(
            session,
            current_user_id,
            repository=request.repository,
            event=request.event,
            delivery_id=request.delivery_id,
            action=request.action,
            conclusion=request.conclusion,
            ref=request.ref,
            metadata=request.metadata,
        )
    except ConditionalMessageServiceError as exc:
        raise_capsule_http_exception(exc)
    return SuccessResponse(data={"triggeredCount": count})


def raise_capsule_http_exception(exc: ConditionalMessageServiceError) -> None:
    """把服务层中文领域错误转换为对应 HTTP 状态码。"""

    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
