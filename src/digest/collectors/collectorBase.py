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


# Per HTTP client: host -> (lock, time of last request). Sources on the same site
# (e.g. two subreddits) take turns with a gap between requests, so the site doesn't
# rate-limit us (HTTP 429).
_hostGates: weakref.WeakKeyDictionary[httpx.AsyncClient, dict[str, list]] = (
    weakref.WeakKeyDictionary()
)


async def _waitForHost(client: httpx.AsyncClient, url: str) -> asyncio.Lock:
    host = urlsplit(url).hostname or ""
    gates = _hostGates.setdefault(client, {})
    gate = gates.setdefault(host, [asyncio.Lock(), 0.0])
    await gate[0].acquire()
    wait = gate[1] + float(env("HOST_REQUEST_SPACING_SECONDS", "2")) - time.monotonic()
    if wait > 0:
        await asyncio.sleep(wait)
    gate[1] = time.monotonic()
    return gate[0]


@retry(
    retry=retry_if_exception(_isRetryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    reraise=True,
)
async def fetch(client: httpx.AsyncClient, url: str, **kwargs) -> httpx.Response:
    """GET with retries on network errors, 429 and 5xx. Raises on any other non-2xx."""
    lock = await _waitForHost(client, url)
    try:
        resp = await client.get(url, **kwargs)
    finally:
        lock.release()
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
