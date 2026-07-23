from pydantic import BaseModel, ConfigDict, Field


class MessageRequest(BaseModel):
    """发送一轮聊天消息所需的文本、用户、附件和位置上下文。"""

    model_config = ConfigDict(populate_by_name=True)

    message: str
    user_id: str = Field(alias="userId")
    client_message_id: str | None = Field(default=None, alias="clientMessageId")
    attachment_ids: list[str] = Field(default_factory=list, alias="attachmentIds")
    city_adcode: str | None = Field(default=None, alias="cityAdcode")
