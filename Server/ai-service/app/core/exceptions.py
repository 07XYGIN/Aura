from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def validation_exception_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "参数不合法",
            "msg": "参数不合法",
            "data": None,
        },
    )


async def http_exception_handler(_request: Request, exc: HTTPException):
    message = str(exc.detail or "请求处理失败")
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={
            "code": exc.status_code,
            "message": message,
            "msg": message,
            "data": None,
        },
    )
