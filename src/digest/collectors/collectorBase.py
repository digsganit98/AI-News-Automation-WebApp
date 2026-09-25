"""Shared pieces for every collector: the interface, the registry and HTTP helpers."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import weakref
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from digest.dataModels import RawItem
from digest.envSettings import env
from digest.sourcesConfig import SourceConfig

log = logging.getLogger(__name__)

EXCERPT_CHARS = 500


class CollectorError(Exception):
    """A collector could not produce results. The run continues without this source."""


class Collector(ABC):
    """Turns one configured source into a list of RawItems."""

    type: str  # matches `type:` in sources.yaml

    def __init__(self, source: SourceConfig):
        self.source = source

    @abstractmethod
    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        """Return items published after `since` (or undated items; they are filtered later)."""

    def item(self, **fields) -> RawItem:
        return RawItem(source=self.source.id, sourceName=self.source.name, **fields)


_REGISTRY: dict[str, type[Collector]] = {}


def register(cls: type[Collector]) -> type[Collector]:
    _REGISTRY[cls.type] = cls
    return cls


def buildCollector(source: SourceConfig) -> Collector:
    try:
        return _REGISTRY[source.type](source)
    except KeyError:
        raise CollectorError(f"Unknown source type '{source.type}' for '{source.id}'") from None


def _isRetryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, httpx.TransportError)


# Requests to the same site take turns, one at a time, with a gap between them, so the site
# doesn't rate-limit us (HTTP 429). Shared by every HTTP client in the process, so the
# collectors and the agents' fetchArticle tool pace each other too.
_lastRequestAt: dict[str, float] = {}
_gateLocks: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Lock]] = (
    weakref.WeakKeyDictionary()
)
MAX_RETRY_AFTER_SECONDS = 120


def hostGate(url: str) -> tuple[str, float]:
    """The pacing key and gap (seconds) for a URL.

    Sites listed in HOST_SPACING_OVERRIDES (e.g. "arxiv.org=4") get their own gap, shared by
    all their subdomains: arXiv's limit covers rss.arxiv.org, export.arxiv.org and arxiv.org.
    """
    host = (urlsplit(url).hostname or "").lower()
    for rule in env("HOST_SPACING_OVERRIDES", "").split(","):
        domain, _, seconds = rule.strip().partition("=")
        if domain and seconds and (host == domain or host.endswith("." + domain)):
            return domain, float(seconds)
    return host, float(env("HOST_REQUEST_SPACING_SECONDS", "2"))


async def waitForHost(url: str) -> asyncio.Lock:
    """Wait for this site's turn. The caller releases the returned lock after its request."""
    key, spacing = hostGate(url)
    lock = _gateLocks.setdefault(asyncio.get_running_loop(), {}).setdefault(key, asyncio.Lock())
    await lock.acquire()
    wait = _lastRequestAt.get(key, 0.0) + spacing - time.monotonic()
    if wait > 0:
        await asyncio.sleep(wait)
    _lastRequestAt[key] = time.monotonic()
    return lock


_backoff = wait_exponential(multiplier=2, min=4, max=30)


def _retryWait(state: RetryCallState) -> float:
    """Exponential backoff, or longer when the site says so (Retry-After on 429/503)."""
    wait = _backoff(state)
    exc = state.outcome.exception() if state.outcome else None
    if isinstance(exc, httpx.HTTPStatusError):
        retryAfter = exc.response.headers.get("Retry-After", "")
        if retryAfter.isdigit():
            wait = max(wait, min(float(retryAfter), MAX_RETRY_AFTER_SECONDS))
    return wait


@retry(
    retry=retry_if_exception(_isRetryable),
    stop=stop_after_attempt(3),
    wait=_retryWait,
    reraise=True,
)
async def fetch(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """GET with retries on network errors, 429 and 5xx. Raises on any other non-2xx
    (except 304 Not Modified, the answer to a conditional request)."""
    lock = await waitForHost(url)
    try:
        resp = await client.get(url, **kwargs)
    finally:
        lock.release()
    if resp.status_code != 304:
        resp.raise_for_status()
    return resp


def htmlToText(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def excerpt(htmlOrText: str, limit: int = EXCERPT_CHARS) -> str:
    text = htmlToText(htmlOrText) if "<" in htmlOrText else htmlOrText.strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
