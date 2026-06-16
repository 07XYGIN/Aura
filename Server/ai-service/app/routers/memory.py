from fastapi import APIRouter, HTTPException, Query

from app.core.agent.tools.term_memory import (
    clear_memories_by_user,
    delete_memory_by_id,
    list_memories_by_user,
    search_memory,
)
from app.schemas.response import SuccessResponse

router = APIRouter(
    prefix="/api/memory",
    tags=["memory"],
)


@router.get("/list", response_model=SuccessResponse, summary="List memories by user")
async def list_memory(
    userId: str,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
):
    memory_page = list_memories_by_user(user_id=userId, page=page, page_size=pageSize)
    return SuccessResponse(data=memory_page)


@router.get("/getMemory", response_model=SuccessResponse, summary="Search memories by user")
async def get_memory(userId: str, query: str, k: int = 1):
    memory_list = search_memory(user_id=userId, query=query, k=k)
    return SuccessResponse(data=memory_list)


@router.delete("/list", response_model=SuccessResponse, summary="Clear memories by user")
async def clear_memory(userId: str):
    deleted_count = clear_memories_by_user(user_id=userId)
    return SuccessResponse(data={"deletedCount": deleted_count})


@router.delete("/{memoryId}", response_model=SuccessResponse, summary="Delete one memory by user")
async def delete_memory(memoryId: str, userId: str):
    deleted = delete_memory_by_id(user_id=userId, memory_id=memoryId)
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆不存在")

    return SuccessResponse(data={"deleted": True, "memoryId": memoryId})
