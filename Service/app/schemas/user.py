from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    username: str = Field(min_length=2, max_length=20, description="用户名")
    email: EmailStr = Field(description="邮箱")
    age: int = Field(ge=0, le=150, description="年龄")
    password: str = Field(min_length=6, description="密码")