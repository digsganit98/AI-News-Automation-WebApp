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
    source: SourceConfig, client: httpx.AsyncClient, since: datetime
) -> tuple[list[RawItem], SourceHealth]:
    now = datetime.now(UTC)
    try:
        fetched = await buildCollector(source).collect(client, since)
        items = applyTitleFilter(fetched, source.opt("titleFilter"))
        log.info("%-24s fetched %4d items, kept %4d", source.id, len(fetched), len(items))
        health = SourceHealth(
            source=source.id, sourceName=source.name, ok=True, items=len(items), checkedAt=now
        )
        return items, health
    except (CollectorError, httpx.HTTPError, OSError, ValueError) as exc:
        log.warning("%-24s FAILED: %s", source.id, exc)
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
        results = await asyncio.gather(*(_runOne(s, client, since) for s in sources))

    items = [item for batch, _ in results for item in batch]
    items = inWindow(normalize(items), since)
    return CollectionResult(runAt=runAt, items=items, health=[h for _, h in results])
