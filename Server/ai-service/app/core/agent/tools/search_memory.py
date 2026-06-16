from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.agent.tools.term_memory import search_memory


@tool
def search_memory_tool(query: str, config: RunnableConfig) -> str:
    """
    根据关键词检索当前用户的历史长期记忆。
    当用户询问过去说过的事、个人偏好、重要日期或关系经历时使用。
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        return "缺少用户 ID，无法检索记忆"

    results = search_memory(user_id=user_id, query=query, k=10)

    if not results:
        return "没有找到相关记忆"

    memory_text = "\n".join([
        f"- {doc.metadata.get('title', '未命名记忆')}：{doc.page_content}"
        for doc in results
    ])
    return f"找到以下记忆：\n{memory_text}"
