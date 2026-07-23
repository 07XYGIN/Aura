from pydantic import BaseModel


class Memory(BaseModel):
    """模型判断是否保存记忆时使用的结构化结果。"""

    save: bool
    title: str
    content: str
