from types import SimpleNamespace
from contextlib import asynccontextmanager
import sys
import unittest
from unittest.mock import AsyncMock, patch

from app.core.world.providers.mcp import MCPWorldProvider
from app.core.world.registry import get_world_service
from app.core.world.models import WorldError
from app.core.world.mcp_server import brave_search
from app.core.world.service import WorldService


class MCPAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_hung_stdio_call_is_cancelled(self):
        code = "\n".join([
            "import asyncio", "from mcp.server.fastmcp import FastMCP",
            "server = FastMCP('test', log_level='ERROR')", "@server.tool()",
            "async def search_web(query: str, max_results: int = 5) -> dict:",
            "    await asyncio.Event().wait()", "    return {}", "server.run(transport='stdio')",
        ])
        service = WorldService(MCPWorldProvider(sys.executable, ["-c", code]), timeout=1.5)
        with self.assertRaises(WorldError) as caught:
            await service.search_web("test")
        self.assertEqual(caught.exception.code, "timeout")

    async def test_mcp_json_contract_and_failure_envelope(self):
        @asynccontextmanager
        async def transport(*args, **kwargs):
            yield None, None

        result = SimpleNamespace(isError=False, structuredContent=None, content=[SimpleNamespace(type="text", text='{"query":"q","searchedAt":"2026-09-20T00:00:00Z","results":[]}')])
        session = SimpleNamespace(initialize=AsyncMock(), call_tool=AsyncMock(return_value=result))

        @asynccontextmanager
        async def client(*args, **kwargs):
            yield session

        with patch("app.core.world.providers.mcp.stdio_client", transport), patch("app.core.world.providers.mcp.ClientSession", client):
            provider = MCPWorldProvider()
            self.assertEqual((await provider.search_web("q")).results, [])
            result.isError = True
            result.content[0].text = "SECRET_RAW_ERROR"
            with self.assertRaises(WorldError) as caught:
                await provider.search_web("q")
            self.assertNotIn("SECRET", str(caught.exception))

    async def test_real_stdio_handshake_reports_missing_search_key(self):
        # Real bundled subprocess, no network call and no credentials.
        with patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": ""}):
            provider = MCPWorldProvider()
        with self.assertRaises(WorldError) as caught:
            await provider.search_web("synthetic test")
        self.assertEqual(caught.exception.code, "not_configured")

    async def test_real_stdio_rejects_private_url(self):
        with self.assertRaises(WorldError) as caught:
            await MCPWorldProvider().fetch_url("http://127.0.0.1/")
        self.assertEqual(caught.exception.code, "unsafe_url")

    def test_child_does_not_inherit_application_secrets(self):
        with patch.dict("os.environ", {"DB_PASSWORD": "private", "DASHSCOPE_API_KEY": "private", "BRAVE_SEARCH_API_KEY": "brave-test"}):
            env = MCPWorldProvider().parameters.env
        self.assertNotIn("DB_PASSWORD", env)
        self.assertNotIn("DASHSCOPE_API_KEY", env)
        self.assertEqual(env["BRAVE_SEARCH_API_KEY"], "brave-test")

    def test_invalid_or_disabled_registry(self):
        for values in [{"WORLD_ENABLED": "false"}, {"WORLD_ENABLED": "true", "WORLD_MCP_ARGS": "not json"}, {"WORLD_ENABLED": "true", "WORLD_MCP_ARGS": "{}"}]:
            with patch.dict("os.environ", values), self.assertRaises(WorldError):
                get_world_service()

    def test_brave_mapping_and_auth_header(self):
        import json
        response = SimpleNamespace(status=200, close=lambda: None, read=lambda *args, **kwargs: json.dumps({"web": {"results": [{"title": "News", "url": "https://example.com/news", "description": "text"}]}}).encode())
        with patch.dict("os.environ", {"BRAVE_SEARCH_API_KEY": "synthetic"}), patch("urllib3.PoolManager") as pool:
            pool.return_value.__enter__.return_value.request.return_value = response
            result = brave_search("news", 1)
            request = pool.return_value.__enter__.return_value.request.call_args
        self.assertEqual(result.results[0].title, "News")
        self.assertEqual(request.kwargs["headers"]["X-Subscription-Token"], "synthetic")
        self.assertFalse(request.kwargs["redirect"])
