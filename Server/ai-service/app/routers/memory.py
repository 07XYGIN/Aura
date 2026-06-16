import logging

from fastapi import APIRouter, Query

from app.core.agent.tools.term_memory import list_memories_by_user, search_memory
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
    logging.info(memory_list)
    return SuccessResponse(data=memory_list)
