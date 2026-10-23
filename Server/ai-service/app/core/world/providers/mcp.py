"""MCP stdio adapter; sessions and subprocesses live for exactly one call."""
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..models import WebDocument, WebSearchResponse, WorldError

ROOT = Path(__file__).resolve().parents[4]
MAX_PAYLOAD = 100000


class MCPWorldProvider:
    def __init__(self, command: str | None = None, args: list[str] | None = None):
        self.parameters = StdioServerParameters(
            command=command or sys.executable,
            args=args if args is not None else ["-m", "app.core.world.mcp_server"],
            cwd=ROOT,
            # Never inherit application/database/model secrets into the child.
            env={"BRAVE_SEARCH_API_KEY": os.getenv("BRAVE_SEARCH_API_KEY", ""), "PYTHONIOENCODING": "utf-8"},
        )

    async def _call(self, name: str, arguments: dict) -> dict:
        # Do not leak arbitrary server exception messages or stderr into chat logs.
        with open(os.devnull, "w") as errlog:
            async with stdio_client(self.parameters, errlog=errlog) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
        if result.isError:
            raise WorldError("provider_error", "外部信息源未能完成请求。")
        payload = result.structuredContent
        if payload is None:
            text = "".join(block.text for block in result.content if block.type == "text")
            if len(text) > MAX_PAYLOAD:
                raise WorldError("invalid_response", "外部信息源返回了过大的数据。")
            payload = json.loads(text)
        if not isinstance(payload, dict) or len(json.dumps(payload, ensure_ascii=False)) > MAX_PAYLOAD:
            raise WorldError("invalid_response", "外部信息源返回格式不正确。")
        if payload.get("ok") is False:
            # Codes only: remote messages may contain secrets or instructions.
            code = payload.get("error", {}).get("code")
            allowed = {"not_configured", "unsafe_url", "dns_error", "empty_document", "timeout", "unsupported_content"}
            code = code if code in allowed else "provider_error"
            raise WorldError(code, "外部信息源未能完成请求；请勿声称已经查询或读取成功。")
        return payload

    async def search_web(self, query: str, *, max_results: int = 5) -> WebSearchResponse:
        return WebSearchResponse.model_validate(await self._call("search_web", {"query": query, "max_results": max_results}))

    async def fetch_url(self, url: str) -> WebDocument:
        return WebDocument.model_validate(await self._call("fetch_url", {"url": url}))
