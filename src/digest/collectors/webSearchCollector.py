"""Web search (Tavily): finds fresh GenAI news the feeds don't cover, such as LinkedIn,
X and Instagram posts via their coverage, YC launches, labs without RSS, and regional
(Coimbatore) AI news. Items are tagged "AI-assisted" in the research log.

The free tier allows 1,000 searches a month, so each run uses only `queriesPerRun`
queries (default 4 x 8 runs a day ≈ 960 a month), rotating through the list in
sources.yaml so every query runs about twice a day.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from digest.collectors.collectorBase import Collector, CollectorError, excerpt, register, utc
from digest.dataModels import RawItem
from digest.envSettings import env, envUrl

log = logging.getLogger(__name__)


def queriesForThisRun(queries: list[str], perRun: int, now: datetime | None = None) -> list[str]:
    """Rotate through the queries: each 3-hour slot of the day takes the next `perRun`."""
    if not queries:
        return []
    now = now or datetime.now(UTC)
    slot = now.hour // 3 + now.timetuple().tm_yday * 8
    start = (slot * perRun) % len(queries)
    return [queries[(start + i) % len(queries)] for i in range(min(perRun, len(queries)))]


def parseResults(data: dict, query: str, collector: Collector) -> list[RawItem]:
    items = []
    for result in data.get("results", []):
        url, title = result.get("url"), (result.get("title") or "").strip()
        if not url or not title:
            continue
        published = None
        if result.get("published_date"):
            try:
                published = utc(parsedate_to_datetime(result["published_date"]))
            except (TypeError, ValueError):
                published = None
        items.append(
            collector.item(
                title=title,
                url=url,
                publishedAt=published,
                excerpt=excerpt(result.get("content") or ""),
                extra={"query": query, "score": round(float(result.get("score") or 0), 3)},
            )
        )
    return items


@register
class WebSearchCollector(Collector):
    type = "webSearch"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        apiKey = env("TAVILY_API_KEY", "")
        if not apiKey:
            raise CollectorError("TAVILY_API_KEY is not set")
        queries = queriesForThisRun(
            self.source.opt("queries", []), int(self.source.opt("queriesPerRun", 4))
        )
        items: list[RawItem] = []
        for query in queries:
            resp = await client.post(
                envUrl("TAVILY_SEARCH_URL"),
                headers={"Authorization": f"Bearer {apiKey}"},
                json={
                    "query": query,
                    "topic": "news",
                    "days": int(self.source.opt("days", 2)),
                    "max_results": int(self.source.opt("resultsPerQuery", 5)),
                    # Articles only: no forum threads or social posts (saves search credits too).
                    "exclude_domains": list(self.source.opt("excludeDomains", [])),
                },
            )
            resp.raise_for_status()
            items += parseResults(resp.json(), query, self)
        log.info("Web search: %d queries -> %d results", len(queries), len(items))
        return items
