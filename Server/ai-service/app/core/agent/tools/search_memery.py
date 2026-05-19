import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.agent.tools.term_memory import search_memory


@tool
def search_memory_tool(query: str, config: RunnableConfig):
    """
    根据关键词检索用户的历史记忆。
    当用户问起之前说过的事情时使用。
    """
    user_id = config["configurable"].get("user_id")
    results = search_memory(user_id=user_id, query=query,k=10)

    if not results:
        return "没有找到相关记忆"

    memory_text = "\n".join([
        f"- {doc.metadata['title']}：{doc.page_content}"
        for doc in results
    ])
    return f"找到以下记忆：\n{memory_text}"