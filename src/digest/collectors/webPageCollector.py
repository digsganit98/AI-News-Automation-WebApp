"""Reads a news listing web page for sites without RSS (e.g. Anthropic).

Which elements to read is set by CSS selectors in sources.yaml, so a site redesign
usually needs a config change, not a code change.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from digest.collectors.collectorBase import Collector, CollectorError, fetch, register, utc
from digest.dataModels import RawItem

_HAS_TIME = re.compile(r"\d{1,2}:\d{2}")


def parseListingDate(text: str) -> datetime | None:
    """Parse a date like 'Sep 23, 2026'.

    A date without a time is treated as the end of that day (UTC). Otherwise a post from
    late in the day could fall outside the collection window before the next run.
    """
    text = text.strip()
    if not text:
        return None
    try:
        dt = dateparser.parse(text)
    except (ValueError, OverflowError):
        return None
    if not _HAS_TIME.search(text):
        dt = dt.replace(hour=23, minute=59, second=59)
    return utc(dt)


def parseListing(html: str, pageUrl: str, collector: Collector) -> list[RawItem]:
    selectors: dict = collector.source.opt("selectors", {})
    itemSel = selectors.get("item")
    if not itemSel:
        raise CollectorError(f"Source '{collector.source.id}' needs selectors.item")

    soup = BeautifulSoup(html, "html.parser")
    items: list[RawItem] = []
    seenUrls: set[str] = set()
    for el in soup.select(itemSel):
        href = el.get("href") or (el.select_one("a[href]") or {}).get("href")
        if not href:
            continue
        url = urljoin(pageUrl, href)
        if url in seenUrls:
            continue

        titleEl = el.select_one(selectors["title"]) if selectors.get("title") else None
        title = (titleEl or el).get_text(" ", strip=True)
        dateEl = el.select_one(selectors["date"]) if selectors.get("date") else None
        published = None
        if dateEl is not None:
            published = parseListingDate(dateEl.get("datetime") or dateEl.get_text())
        if not title:
            continue

        seenUrls.add(url)
        items.append(collector.item(title=title, url=url, publishedAt=published))

    if not items:
        raise CollectorError(
            f"No items matched '{itemSel}' on {pageUrl}; the page layout may have changed"
        )
    return items


@register
class HtmlListingCollector(Collector):
    type = "webPage"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        if not self.source.url:
            raise CollectorError(f"Source '{self.source.id}' has no url")
        resp = await fetch(client, self.source.url)
        return parseListing(resp.text, str(resp.url), self)
