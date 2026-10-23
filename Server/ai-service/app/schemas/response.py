from typing import Any, Literal

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    """项目 HTTP 接口统一使用的成功响应结构。"""

    code: int = 200
    data: Any = None
    msg: Literal["成功"] = "成功"
    message: Literal["成功"] = "成功"
