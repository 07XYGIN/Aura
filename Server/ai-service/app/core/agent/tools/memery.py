import logging
from datetime import datetime

from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from app.core.agent.tools.term_memory import save_memory
from app.core.config import llm
from app.core.agent.prompt import MEMORY_PROMPT
from app.schemas.momery import Memery


@tool
def save_memory_tool(message:str,config:RunnableConfig):
    """
        分析用户消息，如果包含重要信息则提取摘要保存到记忆库。
        你是一个记忆提取助手，负责分析用户的输入是否包含值得长期记忆的信息。
        值得记忆的信息包括但不限于：
        - 用户的个人信息（名字、生日、职业、城市）
        - 用户的偏好（喜欢/不喜欢的东西）
        - 重要的事件或日期
        - 用户的情绪状态和经历

        不需要记忆的信息包括但不限于：
        - 普通闲聊
        - 问天气、问时间等工具性问题
        - 没有实质内容的短句

        请分析以下用户输入，返回JSON格式：
        - save: 是否需要保存（true/false）
        - title: 记忆标题（简短概括）
        - content: 记忆内容（精炼摘要，不超过100字）
    """
    user_id = config["configurable"].get("user_id")
    prompt = ChatPromptTemplate.from_messages([
        ("system", MEMORY_PROMPT),
        ("user", "{input}")
    ])
    logging.info(f"storage state,userId-->:{user_id}")
    structured_llm = llm.with_structured_output(Memery)
    chain = prompt | structured_llm
    res = chain.invoke({"input": message})
    logging.info(f"save--->{res.save}")
    if not res.save:
        logging.info("不是关键信息，跳过")
        return "不需要记忆"
    save_memory(
        user_id=user_id,
        content=res.content,
        title=res.title,
        create_time=datetime.now().strftime("%Y-%m-%d %H:%M")
    )
    logging.info(f"记忆已保存: {res.title}")
    return "已记住这件事"