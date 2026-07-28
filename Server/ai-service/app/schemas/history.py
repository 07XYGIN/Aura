"""聊天历史分支接口的请求模型。"""

from pydantic import BaseModel, ConfigDict, Field


class ConversationBranchRequest(BaseModel):
    """从某条消息后的状态创建一个独立对话分支。"""

    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(alias="messageId", min_length=1, max_length=128)
    branch_id: str | None = Field(default=None, alias="branchId", max_length=64)
