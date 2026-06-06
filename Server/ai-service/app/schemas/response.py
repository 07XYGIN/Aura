from typing import Any, Literal

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    code: int = 200
    data: Any = None
    msg: Literal["成功"] = "成功"
