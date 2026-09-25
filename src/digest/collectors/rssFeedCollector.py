"""Generic RSS/Atom collector: lab blogs, and anything else with a feed."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime

import feedparser
import httpx

from digest.collectors.collectorBase import Collector, CollectorError, excerpt, fetch, register
from digest.dataModels import RawItem


def parseFeed(content: bytes | str, collector: Collector) -> list[RawItem]:
    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        raise CollectorError(f"Could not parse feed: {feed.bozo_exception}")

    items = []
    for entry in feed.entries:
        url = entry.get("link")
        title = (entry.get("title") or "").strip()
        if not url or not title:
            continue
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        published = datetime.fromtimestamp(calendar.timegm(parsed), UTC) if parsed else None
        summary = entry.get("summary") or ""
        items.append(
            collector.item(
                title=title,
                url=url,
                publishedAt=published,
                excerpt=excerpt(summary) if summary else "",
                author=entry.get("author"),
            )
        )
    return items


@register
class RssCollector(Collector):
    type = "rss"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        if not self.source.url:
            raise CollectorError(f"Source '{self.source.id}' has no url")
        resp = await fetch(client, self.source.url)
        return parseFeed(resp.content, self)
