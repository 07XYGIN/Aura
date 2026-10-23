import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_store import get_current_user_id
from app.core.memory.service import (
    clear_memories_by_user,
    delete_memory_by_id,
    get_memory_retention_status,
    list_memories_by_user,
    search_memory,
)
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/memory", tags=["记忆"])


@router.get("/list", response_model=SuccessResponse, summary="分页读取当前用户记忆")
async def list_memory(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    userId: str | None = None,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    scope: str = Query(default="long", pattern="^(long|mid|all)$"),
    includeInactive: bool = Query(default=False),
):
    """分页查询用户的中期、长期或全部记忆。

    Args:
        current_user_id: JWT 中经过校验的唯一用户 ID。
        userId: 仅兼容旧客户端的查询参数，不参与所有权判断。
        page: 从 1 开始的页码。
        pageSize: 每页数量，最大 100。
        scope: 记忆范围，取 ``long``、``mid`` 或 ``all``。
        includeInactive: 是否包含已失效但尚未物理删除的记忆。
    """
    warn_legacy_user_mismatch(userId, current_user_id)
    memory_page = list_memories_by_user(
        user_id=current_user_id,
        page=page,
        page_size=pageSize,
        memory_scope=scope,
        include_inactive=includeInactive,
    )
    return SuccessResponse(data=memory_page)


@router.get("/getMemory", response_model=SuccessResponse, summary="语义检索当前用户记忆")
async def get_memory(
    query: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    userId: str | None = None,
    k: int = Query(default=1, ge=1, le=20),
):
    """按语义查询用户记忆并返回最相关的 ``k`` 条结果。"""
    warn_legacy_user_mismatch(userId, current_user_id)
    memory_list = search_memory(user_id=current_user_id, query=query, k=k)
    return SuccessResponse(data=memory_list)


@router.get("/retention", response_model=SuccessResponse, summary="获取个人记忆保留状态")
async def get_memory_retention(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    userId: str | None = None,
):
    """返回用户记忆数量、保留策略和维护状态。"""
    warn_legacy_user_mismatch(userId, current_user_id)
    return SuccessResponse(data=get_memory_retention_status(user_id=current_user_id))


@router.delete("/list", response_model=SuccessResponse, summary="清空当前用户记忆")
async def clear_memory(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    userId: str | None = None,
    scope: str = Query(default="all", pattern="^(long|mid|all)$"),
):
    """按范围清空用户记忆并返回删除数量。"""
    warn_legacy_user_mismatch(userId, current_user_id)
    deleted_count = clear_memories_by_user(user_id=current_user_id, memory_scope=scope)
    return SuccessResponse(data={"deletedCount": deleted_count})


@router.delete("/{memoryId}", response_model=SuccessResponse, summary="删除当前用户的一条记忆")
async def delete_memory(
    memoryId: str,
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    userId: str | None = None,
):
    """删除属于指定用户的一条记忆。

    Raises:
        HTTPException: 记忆不存在或不属于该用户。
    """
    warn_legacy_user_mismatch(userId, current_user_id)
    deleted = delete_memory_by_id(user_id=current_user_id, memory_id=memoryId)
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆不存在")

    return SuccessResponse(data={"deleted": True, "memoryId": memoryId})


def warn_legacy_user_mismatch(request_user_id: str | None, current_user_id: str) -> None:
    """忽略旧查询参数中的身份，并在不一致时记录中文安全日志。"""

    if request_user_id and request_user_id != current_user_id:
        logging.warning("记忆接口 userId 与 JWT 用户不一致，已使用 JWT 身份")
