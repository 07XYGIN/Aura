from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageRequest(BaseModel):
    """发送一轮聊天消息所需的文本、用户、附件和位置上下文。"""

    model_config = ConfigDict(populate_by_name=True)

    message: str
    user_id: str = Field(alias="userId")
    client_message_id: str | None = Field(
        default=None,
        alias="clientMessageId",
        min_length=1,
        max_length=128,
    )
    attachment_ids: list[str] = Field(default_factory=list, alias="attachmentIds")
    city_adcode: str | None = Field(default=None, alias="cityAdcode")
    branch_id: str | None = Field(default=None, alias="branchId", max_length=64)
    retry_message_id: str | None = Field(default=None, alias="retryMessageId", min_length=1, max_length=128)

    @field_validator("client_message_id")
    @classmethod
    def normalize_client_message_id(cls, value: str | None) -> str | None:
        """规范可选聊天幂等键，提供时不能只包含空白。"""

        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("clientMessageId 不能为空")
        return normalized
