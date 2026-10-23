"""查看 Aura 今日生活、情绪余温和当前共同场景。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.core.auth_store import get_current_user_id
from app.core.continuity.state import load_continuity_state_context_sync
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/api/continuity/state", tags=["连续状态"])


@router.get("/current", response_model=SuccessResponse, summary="读取当前连续状态")
async def read_current_continuity_state(
    current_user_id: Annotated[str, Depends(get_current_user_id)],
):
    """读取当前 JWT 用户的今日生活、有效情绪余温和活动场景。

    同步 LangGraph 使用的状态服务会访问同步数据库，因此 HTTP 路由把它放进线程
    池执行，避免阻塞 FastAPI 事件循环。返回值不包含系统提示词正文。
    """

    state = await run_in_threadpool(load_continuity_state_context_sync, current_user_id)
    return SuccessResponse(
        data={
            "dailyState": state["daily_state"],
            "emotionalAfterglow": state["emotional_afterglow"],
            "activeScene": state["active_scene"],
        }
    )
