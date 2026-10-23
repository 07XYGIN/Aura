"""Provider-independent contracts. External text is always untrusted data."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class WorldModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class SearchResult(WorldModel):
    title: str
    url: str
    snippet: str | None = None
    published_at: datetime | None = None
    source: str | None = None


class WebSearchResponse(WorldModel):
    query: str
    results: list[SearchResult] = Field(default_factory=list)
    searched_at: datetime


class WebDocument(WorldModel):
    url: str
    title: str | None = None
    content: str
    fetched_at: datetime
    truncated: bool = False


class WorldError(Exception):
    """Only the code and controlled message may be returned to the model/logs."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
