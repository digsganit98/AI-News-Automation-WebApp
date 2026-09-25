"""Hacker News stories about AI, via the free Algolia HN Search API.

Falls back to the front-page RSS feed (no points data) if the API is unreachable.
URLs come from HN_ALGOLIA_URL, HN_ITEM_URL and HN_FRONTPAGE_RSS_URL.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

import httpx

from digest.collectors.collectorBase import Collector, fetch, register
from digest.collectors.rssFeedCollector import parseFeed
from digest.dataModels import RawItem
from digest.envSettings import envUrl

log = logging.getLogger(__name__)

MAX_PAGES = 3


def keywordPattern(keywords: list[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(k) for k in keywords)
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


def parseHits(hits: list[dict], pattern: re.Pattern[str], collector: Collector) -> list[RawItem]:
    items = []
    for hit in hits:
        title = hit.get("title") or ""
        if not title or not pattern.search(title):
            continue
        hnUrl = envUrl("HN_ITEM_URL", id=hit["objectID"])
        items.append(
            collector.item(
                title=title,
                url=hit.get("url") or hnUrl,
                publishedAt=datetime.fromtimestamp(hit["created_at_i"], UTC),
                author=hit.get("author"),
                extra={
                    "points": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                    "discussionUrl": hnUrl,
                },
            )
        )
    return items


async def searchHackerNews(
    client: httpx.AsyncClient, query: str, days: int = 7, limit: int = 20
) -> list[dict]:
    """Most relevant HN stories matching `query` from the last `days` days."""
    since = int(datetime.now(UTC).timestamp()) - days * 86400
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{since}",
        "hitsPerPage": min(limit, 50),
    }
    data = (await fetch(client, envUrl("HN_ALGOLIA_SEARCH_URL"), params=params)).json()
    return [
        {
            "title": hit.get("title"),
            "url": hit.get("url") or envUrl("HN_ITEM_URL", id=hit["objectID"]),
            "points": hit.get("points", 0),
            "comments": hit.get("num_comments", 0),
            "discussionUrl": envUrl("HN_ITEM_URL", id=hit["objectID"]),
            "publishedAt": datetime.fromtimestamp(hit["created_at_i"], UTC).isoformat(),
        }
        for hit in data.get("hits", [])
    ]


@register
class HackerNewsCollector(Collector):
    type = "hackerNews"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        pattern = keywordPattern(self.source.opt("keywords", ["AI", "LLM"]))
        try:
            return await self._fromAlgolia(client, since, pattern)
        except httpx.HTTPError as exc:
            log.warning("HN Algolia API failed (%s); using front-page RSS instead", exc)
            resp = await fetch(client, envUrl("HN_FRONTPAGE_RSS_URL"))
            return [i for i in parseFeed(resp.content, self) if pattern.search(i.title)]

    async def _fromAlgolia(
        self, client: httpx.AsyncClient, since: datetime, pattern: re.Pattern[str]
    ) -> list[RawItem]:
        minPoints = self.source.opt("minPoints", 50)
        filters = f"created_at_i>{int(since.timestamp())},points>={minPoints}"
        items: list[RawItem] = []
        for page in range(MAX_PAGES):
            params = {
                "tags": "story",
                "numericFilters": filters,
                "hitsPerPage": 100,
                "page": page,
            }
            data = (await fetch(client, envUrl("HN_ALGOLIA_URL"), params=params)).json()
            items += parseHits(data.get("hits", []), pattern, self)
            if page + 1 >= data.get("nbPages", 0):
                break
        return items
