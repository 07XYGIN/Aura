from __future__ import annotations

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging_config import http_logger


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started_at = time.perf_counter()
        request_body = await request.body()
        http_logger.info(
            "请求开始 method=%s path=%s query_keys=%s body_bytes=%s",
            request.method,
            request.url.path,
            list(request.query_params.keys()),
            len(request_body),
        )

        async def receive():
            return {"type": "http.request", "body": request_body, "more_body": False}

        request = Request(request.scope, receive)

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            http_logger.exception(
                "请求失败 method=%s path=%s elapsed_ms=%.2f",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            http_logger.info(
                "请求完成 method=%s path=%s status=%s content_type=%s elapsed_ms=%.2f body=<流式响应>",
                request.method,
                request.url.path,
                response.status_code,
                content_type,
                elapsed_ms,
            )
            return response

        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk

        http_logger.info(
            "请求完成 method=%s path=%s status=%s elapsed_ms=%.2f body_bytes=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            len(response_body),
        )

        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )
