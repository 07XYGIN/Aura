from __future__ import annotations

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.memory.service import format_memory_context
from .logging_utils import log_tool


@tool
@log_tool
def search_memory_tool(query: str, config: RunnableConfig) -> str:
    """按当前用户检索与当前问题相关的历史记忆。

    用户询问过去内容、继续以前的计划或当前回复必须依赖历史事实时调用。
    query 应描述要找的具体事件或事实；结果没有出现的内容不能引用或补写。
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return "缺少用户 ID，无法检索记忆。"

    context = format_memory_context(user_id=str(user_id), query=query, k=6)
    return (
        f"记忆检索结果，查询：{query}\n"
        f"{context}\n\n"
        "只能引用上面明确出现的事实；没有出现的偏好、天气、城市、食物或共同经历都不能编造。"
    )
