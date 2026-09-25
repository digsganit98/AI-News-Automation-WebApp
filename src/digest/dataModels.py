"""Data shapes shared by every stage of the pipeline."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from digest.urlCleaning import urlId


class RawItem(BaseModel):
    """One thing a collector found: a blog post, HN story, video, tweet, newsletter entry."""

    source: str  # source id from sources.yaml, e.g. "openai"
    sourceName: str  # human-readable, e.g. "OpenAI"
    title: str
    url: str
    publishedAt: datetime | None = None
    excerpt: str = ""
    author: str | None = None
    extra: dict = Field(default_factory=dict)  # source-specific data (points, likes, ...)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> str:
        """Same id for the same article, however the link was written."""
        return urlId(self.url)

    def public(self) -> dict:
        """Dict for public data files: drops private extras (keys starting with "_")."""
        data = self.model_dump(mode="json")
        data["extra"] = {k: v for k, v in self.extra.items() if not k.startswith("_")}
        return data


class SourceHealth(BaseModel):
    source: str
    sourceName: str
    ok: bool
    items: int = 0
    error: str | None = None
    checkedAt: datetime


class CollectionResult(BaseModel):
    """Everything gathered in one run, before any LLM processing."""

    runAt: datetime
    items: list[RawItem]
    health: list[SourceHealth]
