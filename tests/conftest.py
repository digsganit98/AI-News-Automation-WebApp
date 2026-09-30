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


def makeTakes(takeText: str = "I think it matters.", storyIds: list[str] | None = None):
    """Two short opinion takes for tests; `takeText` is the first take's opinion."""
    from digest.agents.agentModels import Take, TakesDraft

    def take(theme: str, text: str) -> Take:
        return Take(
            theme=theme,
            title=f"{theme} take",
            verdict="A clear verdict.",
            whatHappened="Something was released.",
            take=text,
            watchFor="Watch the next release.",
            basedOnStoryIds=list(storyIds or []),
        )

    return TakesDraft(takes=[take("Models", takeText), take("Policy", "I think it helps.")])
