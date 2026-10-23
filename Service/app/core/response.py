from typing import Any, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: T | None = None

    @classmethod
    def ok(cls, data: T | None = None, message: str = "success") -> "Result[T]":
        return cls(code=200, message=message, data=data)

    @classmethod
    def fail(cls, code: int = 500, message: str = "fail") -> "Result[Any]":
        return cls(code=code, message=message, data=None)