"""查看 Aura 离线思绪候选和睡前整理记录。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth_store import SessionDep, get_current_user_id
from app.core.continuity.mind import (
    OfflineMindServiceError,
    list_sleep_cycles_async,
    list_thought_seeds_async,
)
from app.schemas.offline_mind import ThoughtSeedStatus
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/continuity/mind", tags=["离线心智"])


@router.get("/thoughts", response_model=SuccessResponse, summary="查询 Aura 思绪种子")
async def read_thought_seeds(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    status: ThoughtSeedStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """查看思绪为什么产生、是否被取消、排队或真正使用。"""

    try:
        items = await list_thought_seeds_async(
            session,
            current_user_id,
            status=status,
            limit=limit,
        )
    except OfflineMindServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return SuccessResponse(data={"items": items})


@router.get("/sleep-cycles", response_model=SuccessResponse, summary="查询 Aura 睡前整理")
async def read_sleep_cycles(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
    session: SessionDep,
    limit: int = Query(default=30, ge=1, le=200),
):
    """查看每天一次的开放线索、互动边界和记忆去重结果。"""

    try:
        items = await list_sleep_cycles_async(session, current_user_id, limit=limit)
    except OfflineMindServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return SuccessResponse(data={"items": items})
