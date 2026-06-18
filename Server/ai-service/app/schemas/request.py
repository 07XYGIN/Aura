from pydantic import BaseModel, ConfigDict, Field


class MessageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    user_id: str = Field(alias="userId")
    client_message_id: str | None = Field(default=None, alias="clientMessageId")
