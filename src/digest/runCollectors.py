"""Runs collectors in parallel. Used by the CLI and by the MCP server.

One source failing never stops the others; its error is recorded in SourceHealth.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx

from digest.collectors import CollectorError, buildCollector
from digest.dataModels import CollectionResult, RawItem, SourceHealth
from digest.envSettings import env
from digest.processing.articleFilter import keepArticlesOnly
from digest.processing.cleanItems import normalize
from digest.processing.removeDuplicates import inWindow
from digest.processing.titleFilter import applyTitleFilter
from digest.sourcesConfig import Config, SourceConfig

log = logging.getLogger(__name__)


def httpClient(config: Config) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": env("USER_AGENT")},
        timeout=config.settings.requestTimeout,
        follow_redirects=True,
    )


async def _runOne(
    source: SourceConfig, client: httpx.AsyncClient, since: datetime, notArticleHosts: list[str]
) -> tuple[list[RawItem], SourceHealth]:
    now = datetime.now(UTC)
    try:
        fetched = await buildCollector(source).collect(client, since)
        items = applyTitleFilter(fetched, source.opt("titleFilter"))
        if source.opt("articlesOnly"):  # drop discussion threads and social posts
            items = keepArticlesOnly(items, notArticleHosts)
        if maxItems := source.opt("maxItems"):  # busy feeds: keep only the newest few
            items = sorted(
                items,
                key=lambda i: i.publishedAt.isoformat() if i.publishedAt else "",
                reverse=True,
            )[:maxItems]
        log.info("%-24s fetched %4d items, kept %4d", source.id, len(fetched), len(items))
        health = SourceHealth(
            source=source.id, sourceName=source.name, ok=True, items=len(items), checkedAt=now
        )
        return items, health
    except Exception as exc:  # one broken source, even an unexpected bug, never stops the rest
        expected = isinstance(exc, (CollectorError, httpx.HTTPError, OSError, ValueError))
        if expected:
            log.warning("%-24s FAILED: %s", source.id, exc)
        else:  # e.g. a feed changed shape: keep the traceback so it can be fixed
            log.exception("%-24s FAILED unexpectedly", source.id)
        firstLine = (str(exc).splitlines() or [""])[0]
        error = f"{type(exc).__name__}: {firstLine}"[:300]
        health = SourceHealth(
            source=source.id, sourceName=source.name, ok=False, error=error, checkedAt=now
        )
        return [], health


async def collectSources(
    config: Config, sources: list[SourceConfig] | None = None, hours: int | None = None
) -> CollectionResult:
    """Fetch every given source (default: all enabled) and keep items from the last `hours`."""
    sources = config.enabledSources if sources is None else sources
    runAt = datetime.now(UTC)
    since = runAt - timedelta(hours=hours or config.settings.windowHours)

    async with httpClient(config) as client:
        hosts = config.settings.notArticleHosts
        results = await asyncio.gather(*(_runOne(s, client, since, hosts) for s in sources))

    items = [item for batch, _ in results for item in batch]
    items = inWindow(normalize(items), since)
    return CollectionResult(runAt=runAt, items=items, health=[h for _, h in results])
