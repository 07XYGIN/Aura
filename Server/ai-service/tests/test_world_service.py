import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.core.world.models import SearchResult, WebDocument, WebSearchResponse, WorldError
from app.core.world.service import WorldService
from app.core.world.security import resolve_public_url, validate_url


def search_response(count=1):
    return WebSearchResponse(query="test", searched_at=datetime.now(UTC), results=[
        SearchResult(title="Page", url=f"https://example.com/{i}", snippet="hello") for i in range(count)
    ])


def document(content="body", url="https://example.com/"):
    return WebDocument(url=url, content=content, fetched_at=datetime.now(UTC))


class WorldServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.provider = SimpleNamespace(search_web=AsyncMock(return_value=search_response()), fetch_url=AsyncMock(return_value=document()))
        self.service = WorldService(self.provider, timeout=2)
        self.dns = patch("app.core.world.service.resolve_public_url", return_value=("https://example.com/", ["93.184.216.34"]))
        self.dns.start()
        self.addCleanup(self.dns.stop)

    async def test_search_success_and_limits(self):
        self.provider.search_web.return_value = search_response(9)
        result = await self.service.search_web(" news ", 100)
        self.assertEqual(len(result.results), 5)
        self.assertEqual(result.query, "news")
        self.provider.search_web.assert_awaited_once_with("news", max_results=5)
        self.assertEqual(len((await self.service.search_web("news", 2)).results), 2)

    async def test_empty_query_and_bad_limit(self):
        for value in ["", "  ", "x" * 601]:
            with self.subTest(value=value), self.assertRaises(WorldError):
                await self.service.search_web(value)
        with self.assertRaises(WorldError):
            await self.service.search_web("news", 0)
        self.provider.search_web.assert_not_awaited()

    async def test_search_empty_and_unsafe_results(self):
        result = search_response()
        result.results[0].url = "http://127.0.0.1/"
        self.provider.search_web.return_value = result
        self.assertEqual((await self.service.search_web("q")).results, [])

    async def test_provider_failures_do_not_leak(self):
        for method, argument in [("search_web", "news"), ("fetch_url", "https://example.com/")]:
            getattr(self.provider, method).side_effect = RuntimeError("SECRET_TOKEN")
            with self.subTest(method=method), self.assertRaises(WorldError) as caught:
                await getattr(self.service, method)(argument)
            self.assertNotIn("SECRET_TOKEN", str(caught.exception))

    async def test_timeout_for_both_operations(self):
        self.service.timeout = .03
        async def slow(*args, **kwargs):
            await asyncio.sleep(1)
        for method, argument in [("search_web", "news"), ("fetch_url", "https://example.com/")]:
            getattr(self.provider, method).side_effect = slow
            with self.subTest(method=method), self.assertRaises(WorldError) as caught:
                await getattr(self.service, method)(argument)
            self.assertEqual(caught.exception.code, "timeout")

    async def test_fetch_success_truncation_and_empty(self):
        self.assertEqual((await self.service.fetch_url("https://example.com/")).content, "body")
        self.provider.fetch_url.return_value = document("x" * 15000)
        result = await self.service.fetch_url("https://example.com/")
        self.assertEqual(len(result.content), 12000)
        self.assertTrue(result.truncated)
        self.provider.fetch_url.return_value = document(" \n ")
        with self.assertRaises(WorldError) as caught:
            await self.service.fetch_url("https://example.com/")
        self.assertEqual(caught.exception.code, "empty_document")

    async def test_invalid_url_never_reaches_provider(self):
        for url in ["file:///etc/passwd", "ftp://example.com", "http://localhost", "http://127.0.0.1", "http://10.1.2.3", "http://192.168.1.1", "http://172.16.0.1", "http://0.0.0.0", "http://[::1]", "http://[::ffff:127.0.0.1]", "http://169.254.169.254", "http://user:password@example.com", "https://example.com:8000", "http://224.0.0.1", "http://example.com\\@127.0.0.1"]:
            with self.subTest(url=url), self.assertRaises(WorldError):
                await self.service.fetch_url(url)
        self.provider.fetch_url.assert_not_awaited()

    async def test_private_final_url_rejected(self):
        self.provider.fetch_url.return_value = document(url="http://10.0.0.1/")
        with self.assertRaises(WorldError):
            await self.service.fetch_url("https://example.com/")


class URLSecurityTest(unittest.TestCase):
    def test_mixed_public_private_dns_rejected(self):
        rows = [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("127.0.0.1", 443))]
        with patch("socket.getaddrinfo", return_value=rows), self.assertRaises(WorldError):
            resolve_public_url("https://example.com/")

    def test_alternative_numeric_loopback_rejected_after_dns(self):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 80))]), self.assertRaises(WorldError):
            resolve_public_url("http://127.1/")

    def test_public_url_normalized(self):
        self.assertEqual(validate_url("https://EXAMPLE.com/article#section"), "https://example.com/article")
