"""Shared test helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from digest.collectors import buildCollector
from digest.sourcesConfig import SourceConfig

FIXTURES = Path(__file__).parent / "fixtures"


def readFixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def makeCollector(type: str, **options):
    """A collector for `type` with a throwaway source config."""
    source = SourceConfig(id=f"test-{type}", name=f"Test {type}", type=type, **options)
    return buildCollector(source)


@pytest.fixture(autouse=True)
def isolatedSpacing(monkeypatch, tmp_path):
    # Tests should not wait between requests to the same host, or touch the real feed cache.
    from digest.collectors import feedCache

    monkeypatch.setenv("HOST_REQUEST_SPACING_SECONDS", "0")
    monkeypatch.setenv("HOST_SPACING_OVERRIDES", "")
    monkeypatch.setattr(feedCache, "FEED_CACHE_FILE", tmp_path / "feedCache.json")
    feedCache.resetFeedCache()
    yield
    feedCache.resetFeedCache()


@pytest.fixture(autouse=True)
def noRealServices(monkeypatch):
    """Tests never talk to Langfuse, even when .env has real keys."""
    from digest.monitoring import langfuseTracing

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    langfuseTracing.langfuseClient.cache_clear()
    yield
    langfuseTracing.langfuseClient.cache_clear()
