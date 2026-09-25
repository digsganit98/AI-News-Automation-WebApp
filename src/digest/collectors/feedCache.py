"""Remembers a feed's caching headers between runs, so a slow-changing feed isn't re-downloaded.

arXiv's feed changes once a day and asks automated clients to go easy. A source with
`respectCacheControl: true` is fetched only after its Cache-Control max-age has passed, and
then with If-None-Match / If-Modified-Since, so an unchanged feed costs one tiny 304 reply.
Saved in state/feedCache.json with the seen-list (not during dry runs).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from digest.publish.saveDataFiles import STATE_DIR

FEED_CACHE_FILE = STATE_DIR / "feedCache.json"
# arXiv always says "valid for ~24 h", whenever you ask. Re-checking after at most 6 h keeps
# new papers from arriving up to a day late; an unchanged feed then costs only a 304 reply.
MAX_FRESH_HOURS = 6

_entries: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _entries
    if _entries is None:
        path = FEED_CACHE_FILE
        _entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _entries


def isFresh(url: str, now: datetime | None = None) -> bool:
    """True while the last copy is still valid: no need to ask the site again."""
    entry = _load().get(url)
    return bool(entry) and datetime.fromisoformat(entry["freshUntil"]) > (now or datetime.now(UTC))


def conditionalHeaders(url: str) -> dict[str, str]:
    entry = _load().get(url, {})
    headers = {}
    if entry.get("etag"):
        headers["If-None-Match"] = entry["etag"]
    if entry.get("lastModified"):
        headers["If-Modified-Since"] = entry["lastModified"]
    return headers


def remember(url: str, resp: httpx.Response, now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    match = re.search(r"max-age=(\d+)", resp.headers.get("Cache-Control", ""))
    seconds = min(int(match.group(1)) if match else 0, MAX_FRESH_HOURS * 3600)
    old = _load().get(url, {})
    _load()[url] = {
        "etag": resp.headers.get("ETag") or old.get("etag"),
        "lastModified": resp.headers.get("Last-Modified") or old.get("lastModified"),
        "freshUntil": (now + timedelta(seconds=seconds)).isoformat(),
    }


def saveFeedCache(path: Path | None = None) -> None:
    if _entries is None:  # nothing was loaded or changed this run
        return
    path = path or FEED_CACHE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resetFeedCache() -> None:
    global _entries
    _entries = None
