from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    """注册账号所需的凭据和基础资料。"""

    model_config = ConfigDict(populate_by_name=True)

    username: str
    password: str
    email: str | None = None
    age: int | None = None
    sex: int


class UserLoginRequest(BaseModel):
    """用户名密码登录请求。"""

    username: str
    password: str


class UserUpdateRequest(BaseModel):
    """当前用户可部分更新的基础资料字段。"""

    username: str | None = None
    email: str | None = None
    age: int | None = None
    sex: int | None = None
