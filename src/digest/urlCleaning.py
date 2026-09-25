"""URL helpers.

- `cleanUrl` removes click-tracking parameters. The result is the link readers get.
- `canonicalKey` goes further (https, no www, no trailing slash, sorted query). It is used
  only to decide whether two links point to the same article, never as a link itself.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "ref_url",
    "igshid",
    "si",
    "_hsenc",
    "_hsmi",
    "mkt_tok",
}
TRACKING_PREFIXES = ("utm_",)


def _dropTracking(query: str) -> list[tuple[str, str]]:
    return [
        (k, v)
        for k, v in parse_qsl(query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    ]


def cleanUrl(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return url.strip()  # e.g. "mid:" links for newsletters
    return urlunsplit(parts._replace(query=urlencode(_dropTracking(parts.query)), fragment=""))


def canonicalKey(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return url.strip()
    host = (parts.hostname or "").lower().removeprefix("www.")
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(_dropTracking(parts.query))), ""))


def urlId(url: str) -> str:
    return hashlib.sha1(canonicalKey(url).encode("utf-8")).hexdigest()[:16]
