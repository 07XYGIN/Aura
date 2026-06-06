from pydantic import BaseModel, ConfigDict, Field


class MessageRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    user_id: str = Field(alias="userId")


class RegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_name: str = Field(alias="userName")
    password: str
    code: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_name: str = Field(alias="userName")
    password: str
    code: str
