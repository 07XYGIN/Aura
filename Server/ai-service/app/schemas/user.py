from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    username: str
    password: str
    email: str | None = None
    age: int | None = None
    sex: int
    invite_code: str | None = Field(default=None, alias="inviteCode")


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    age: int | None = None
    sex: int | None = None
