"""Generic RSS/Atom collector: lab blogs, and anything else with a feed."""

from __future__ import annotations

import calendar
import logging
import re
from datetime import UTC, datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

from digest.collectors import feedCache
from digest.collectors.collectorBase import (
    Collector,
    CollectorError,
    excerpt,
    fetch,
    htmlToText,
    register,
)
from digest.dataModels import RawItem

log = logging.getLogger(__name__)


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
        extra = {}
        if collector.source.opt("useLinkedArticle"):
            # Link aggregators (Reddit): point the item at the article the post links to, and
            # keep the thread as its discussion. A text-only post links to itself; the
            # `articlesOnly` filter then drops it.
            extra["discussionUrl"] = url
            url = linkedArticle(summary) or url
            summary = AGGREGATOR_FOOTER.sub("", htmlToText(summary))
        items.append(
            collector.item(
                title=title,
                url=url,
                publishedAt=published,
                excerpt=excerpt(summary) if summary else "",
                author=entry.get("author"),
                extra=extra,
            )
        )
    return items


# Reddit's feed ends every post with "submitted by /u/name to r/sub [link] [comments]".
AGGREGATOR_FOOTER = re.compile(
    r"\s*submitted by\s+/u/\S+(\s+to\s+r/\S+)?\s*\[link\]\s*\[comments\]\s*$"
)


def linkedArticle(summaryHtml: str) -> str | None:
    """The URL behind a post's "[link]" anchor (Reddit's feed format)."""
    for anchor in BeautifulSoup(summaryHtml, "html.parser").find_all("a"):
        if anchor.get_text(strip=True) == "[link]" and anchor.get("href"):
            return str(anchor["href"])
    return None


@register
class RssCollector(Collector):
    type = "rss"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        url = self.source.url
        if not url:
            raise CollectorError(f"Source '{self.source.id}' has no url")
        if not self.source.opt("respectCacheControl", False):
            return parseFeed((await fetch(client, url)).content, self)

        # Slow-changing feeds (arXiv): skip until the copy we have expires, then ask
        # "changed since?" so an unchanged feed is a tiny 304 reply.
        if feedCache.isFresh(url):
            log.info("%-24s unchanged: cached copy still valid, not fetched", self.source.id)
            return []
        resp = await fetch(client, url, headers=feedCache.conditionalHeaders(url))
        feedCache.remember(url, resp)
        return [] if resp.status_code == 304 else parseFeed(resp.content, self)
