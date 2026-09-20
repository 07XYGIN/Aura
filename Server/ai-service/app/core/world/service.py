"""Validation, limits and safe error conversion around any WorldProvider."""
import asyncio
import re
import unicodedata

from .models import WebDocument, WebSearchResponse, WorldError
from .providers.base import WorldProvider
from .security import resolve_public_url, validate_url

MAX_CONTENT = 12000


def clean_text(value: str) -> str:
    value = "".join(c for c in value if c in "\n\t" or unicodedata.category(c) not in {"Cc", "Cf"})
    return re.sub(r"[ \t]+", " ", value).strip()


class WorldService:
    def __init__(self, provider: WorldProvider, *, timeout: float = 20):
        self.provider = provider
        self.timeout = timeout

    async def search_web(self, query: str, max_results: int = 5) -> WebSearchResponse:
        if not isinstance(query, str) or not query.strip() or len(query) > 600 or len(query.split()) > 75:
            raise WorldError("invalid_query", "搜索词不能为空，且不得超过 600 字符或 75 个词。")
        if type(max_results) is not int or max_results < 1:
            raise WorldError("invalid_limit", "搜索结果数量必须为正整数，最多返回 5 条。")
        limit = min(max_results, 5)
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.provider.search_web(query.strip(), max_results=limit)
            response = WebSearchResponse.model_validate(response)
            results = []
            for item in response.results:
                try:
                    item.url = validate_url(item.url)
                except WorldError:
                    continue
                item.title = clean_text(item.title)[:300]
                item.snippet = clean_text(item.snippet or "")[:1200] or None
                item.source = clean_text(item.source or "")[:200] or None
                results.append(item)
                if len(results) == limit:
                    break
            return response.model_copy(update={"query": query.strip(), "results": results})
        except WorldError:
            raise
        except TimeoutError:
            raise WorldError("timeout", "外部信息查询超时，未成功取得实时信息。") from None
        except Exception:
            raise WorldError("provider_error", "暂时无法连接外部信息源。") from None

    async def fetch_url(self, url: str) -> WebDocument:
        url = validate_url(url)
        try:
            async with asyncio.timeout(self.timeout):
                # Early rejection; the bundled MCP independently pins DNS at every hop.
                await asyncio.to_thread(resolve_public_url, url)
                document = WebDocument.model_validate(await self.provider.fetch_url(url))
                document.url = validate_url(document.url)
                await asyncio.to_thread(resolve_public_url, document.url)
            content = clean_text(document.content)
            if not content:
                raise WorldError("empty_document", "网页没有可读取的正文，不能根据 URL 猜测内容。")
            return document.model_copy(update={
                "content": content[:MAX_CONTENT],
                "title": clean_text(document.title or "")[:300] or None,
                "truncated": document.truncated or len(content) > MAX_CONTENT,
            })
        except WorldError:
            raise
        except TimeoutError:
            raise WorldError("timeout", "网页读取超时，未成功读取正文。") from None
        except Exception:
            raise WorldError("provider_error", "网页无法读取，不能根据 URL 猜测内容。") from None
