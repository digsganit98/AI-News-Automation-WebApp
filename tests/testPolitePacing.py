"""Polite fetching: per-site pacing (arXiv asks for 3+ s between requests) and feed caching."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import httpx
import respx
from conftest import makeCollector, readFixture

from digest.collectors import feedCache
from digest.collectors.collectorBase import fetch, hostGate

FEED = "https://rss.arxiv.test/rss/cs.AI"
SINCE = datetime(2000, 1, 1, tzinfo=UTC)


def testSlowSiteSharesOneGateAcrossSubdomains(monkeypatch):
    monkeypatch.setenv("HOST_SPACING_OVERRIDES", "arxiv.org=4")
    monkeypatch.setenv("HOST_REQUEST_SPACING_SECONDS", "2")
    assert hostGate("https://rss.arxiv.org/rss/cs.AI") == ("arxiv.org", 4.0)
    assert hostGate("https://export.arxiv.org/api/query") == ("arxiv.org", 4.0)
    assert hostGate("https://arxiv.org/abs/2609.00001") == ("arxiv.org", 4.0)
    assert hostGate("https://notarxiv.org/x") == ("notarxiv.org", 2.0)


@respx.mock
async def testRequestsToASlowSiteAreSpacedOut(monkeypatch):
    monkeypatch.setenv("HOST_SPACING_OVERRIDES", "slow.test=0.3")
    respx.get(url__startswith="https://a.slow.test/").mock(return_value=httpx.Response(200))
    respx.get(url__startswith="https://b.slow.test/").mock(return_value=httpx.Response(200))
    async with httpx.AsyncClient() as client:
        start = time.monotonic()
        await fetch(client, "https://a.slow.test/1")
        await fetch(client, "https://b.slow.test/2")  # another subdomain, same site
        await fetch(client, "https://a.slow.test/3")
    assert time.monotonic() - start >= 0.6


@respx.mock
async def testCachedFeedIsFetchedOnlyWhenItMayHaveChanged():
    route = respx.get(FEED).mock(
        return_value=httpx.Response(
            200,
            content=readFixture("openaiFeed.xml"),
            headers={"ETag": '"v1"', "Cache-Control": "max-age=86000"},
        )
    )
    collector = makeCollector("rss", url=FEED, respectCacheControl=True)
    async with httpx.AsyncClient() as client:
        assert len(await collector.collect(client, SINCE)) == 2

        # Still fresh: the site isn't asked again.
        assert await collector.collect(client, SINCE) == []
        assert route.call_count == 1

        # Expired: ask "changed since?"; an unchanged feed answers 304 with no body.
        feedCache._load()[FEED]["freshUntil"] = (datetime.now(UTC) - timedelta(1)).isoformat()
        route.mock(return_value=httpx.Response(304, headers={"Cache-Control": "max-age=86000"}))
        assert await collector.collect(client, SINCE) == []
        assert route.calls.last.request.headers["If-None-Match"] == '"v1"'
        assert feedCache.isFresh(FEED)


def testFeedCacheIsSavedAndReloaded(monkeypatch, tmp_path):
    headers = {"ETag": "x", "Cache-Control": "max-age=60"}
    feedCache.remember(FEED, httpx.Response(200, headers=headers))
    path = tmp_path / "cache.json"
    feedCache.saveFeedCache(path)
    feedCache.resetFeedCache()
    monkeypatch.setattr(feedCache, "FEED_CACHE_FILE", path)
    assert feedCache.conditionalHeaders(FEED) == {"If-None-Match": "x"}
