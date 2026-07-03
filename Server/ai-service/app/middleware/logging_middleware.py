from __future__ import annotations

import json
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging_config import http_logger, to_log_text, truncate


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started_at = time.perf_counter()
        request_body = await request.body()
        http_logger.info(
            "--> %s %s query=%s body=%s",
            request.method,
            request.url.path,
            dict(request.query_params),
            body_to_log_text(request_body),
        )

        async def receive():
            return {"type": "http.request", "body": request_body, "more_body": False}

        request = Request(request.scope, receive)

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            http_logger.exception(
                "<-- %s %s ERROR elapsed=%.2fms",
                request.method,
                request.url.path,
                elapsed_ms,
            )
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            http_logger.info(
                "<-- %s %s status=%s content-type=%s elapsed=%.2fms body=<streaming>",
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
            "<-- %s %s status=%s elapsed=%.2fms body=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            body_to_log_text(response_body),
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


def body_to_log_text(body: bytes) -> str:
    if not body:
        return "<empty>"
    try:
        return to_log_text(json.loads(body.decode("utf-8")))
    except Exception:
        return truncate(body.decode("utf-8", errors="replace"))
