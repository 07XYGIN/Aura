"""Bundled, read-only stdio MCP: Brave Search and an SSRF-hardened reader.

This process deliberately never loads Aura's .env or application config.
"""
from datetime import UTC, datetime
import json
import os

from mcp.server.fastmcp import FastMCP
import urllib3

from .models import SearchResult, WebSearchResponse, WorldError
from .reader import read_public_page

server = FastMCP("Aura World Access v1", log_level="ERROR")


def brave_search(query: str, max_results: int = 5) -> WebSearchResponse:
    key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    if not key:
        raise WorldError("not_configured", "未配置 Brave Search API Key。")
    if not query.strip() or len(query) > 600 or len(query.split()) > 75:
        raise WorldError("invalid_query", "搜索词不符合长度要求。")
    with urllib3.PoolManager() as pool:
        response = pool.request(
            "GET", "https://api.search.brave.com/res/v1/web/search",
            fields={"q": query, "count": min(5, max(1, max_results))},
            headers={"X-Subscription-Token": key, "Accept": "application/json", "Accept-Encoding": "identity"},
            timeout=urllib3.Timeout(connect=5, read=10), retries=False, redirect=False, preload_content=False,
        )
        try:
            if response.status != 200:
                raise WorldError("provider_error", "搜索服务未能完成请求。")
            raw = response.read(512001, decode_content=False)
            if len(raw) > 512000:
                raise WorldError("invalid_response", "搜索响应过大。")
            payload = json.loads(raw)
        finally:
            response.close()
    results = [SearchResult(title=str(row.get("title", ""))[:300], url=row["url"], snippet=str(row.get("description", ""))[:1200], source=(row.get("profile") or {}).get("name"))
               for row in (payload.get("web") or {}).get("results", [])[:min(5, max(1, max_results))]]
    return WebSearchResponse(query=query, results=results, searched_at=datetime.now(UTC))


def safe_result(callback, *args) -> dict:
    try:
        return callback(*args).model_dump(mode="json", by_alias=True)
    except WorldError as exc:
        return {"ok": False, "error": {"code": exc.code}}
    except Exception:
        return {"ok": False, "error": {"code": "provider_error"}}


@server.tool()
def search_web(query: str, max_results: int = 5) -> dict:
    """Search public web pages via Brave; return the Aura World contract."""
    return safe_result(brave_search, query, max_results)


@server.tool()
def fetch_url(url: str) -> dict:
    """Read public HTML/plain text; never follow private addresses or unsafe redirects."""
    return safe_result(read_public_page, url)


if __name__ == "__main__":
    server.run(transport="stdio")
