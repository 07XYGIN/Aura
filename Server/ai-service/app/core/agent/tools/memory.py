import logging
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.core.agent.prompt import MEMORY_PROMPT
from app.core.agent.tools.term_memory import save_memory
from app.core.config import llm
from app.schemas.memory import Memory


@tool
def save_memory_tool(message: str, config: RunnableConfig) -> str:
    """
    分析用户消息，如果包含重要信息则提取摘要保存到记忆库。
    """
    user_id = config["configurable"].get("user_id")
    if not user_id:
        logging.warning("缺少 user_id，跳过记忆保存")
        return "缺少用户 ID，无法保存记忆"

    prompt = ChatPromptTemplate.from_messages([
        ("system", MEMORY_PROMPT),
        ("user", "{input}"),
    ])
    logging.info("storage state, user_id: %s", user_id)
    structured_llm = llm.with_structured_output(Memory)
    chain = prompt | structured_llm
    res = chain.invoke({"input": message})
    logging.info("memory save decision: %s", res.save)
    if not res.save:
        logging.info("不是关键信息，跳过")
        return "不需要记忆"

    save_memory(
        user_id=user_id,
        content=res.content,
        title=res.title,
        create_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    logging.info("记忆已保存: %s", res.title)
    return "已记住这件事"
