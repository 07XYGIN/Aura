from typing import Protocol

from ..models import WebDocument, WebSearchResponse


class WorldProvider(Protocol):
    async def search_web(self, query: str, *, max_results: int = 5) -> WebSearchResponse: ...

    async def fetch_url(self, url: str) -> WebDocument: ...
