"""fetchArticle: download one web page and return its readable text.

Agents call this with URLs taken from scraped content, so it is locked down:
- only http(s) URLs, and only to public internet addresses (no localhost / private network)
- the download is capped at ARTICLE_MAX_BYTES, and the text at ARTICLE_MAX_CHARS
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit

import httpx
import trafilatura
from pydantic import BaseModel

from digest.envSettings import env


class FetchedArticle(BaseModel):
    url: str
    title: str | None = None
    text: str
    truncated: bool = False


class UnsafeUrlError(ValueError):
    pass


async def checkUrlIsPublic(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise UnsafeUrlError(f"Only http(s) URLs are allowed: {url}")
    infos = await asyncio.to_thread(socket.getaddrinfo, parts.hostname, None)
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeUrlError(f"{parts.hostname} resolves to a non-public address ({ip})")


async def fetchArticle(client: httpx.AsyncClient, url: str) -> FetchedArticle:
    maxBytes = int(env("ARTICLE_MAX_BYTES"))
    maxChars = int(env("ARTICLE_MAX_CHARS"))

    # Follow redirects by hand so every hop is checked, not just the first URL.
    for _ in range(5):
        await checkUrlIsPublic(url)
        async with client.stream("GET", url, follow_redirects=False) as resp:
            if resp.is_redirect:
                url = str(resp.url.join(resp.headers["location"]))
                continue
            resp.raise_for_status()
            body = bytearray()
            async for chunk in resp.aiter_bytes():
                body.extend(chunk)
                if len(body) >= maxBytes:
                    break
            html = body.decode(resp.encoding or "utf-8", errors="replace")
            break
    else:
        raise httpx.TooManyRedirects(f"Too many redirects for {url}")

    text = trafilatura.extract(html, include_comments=False, include_tables=False) or ""
    meta = trafilatura.extract_metadata(html)
    return FetchedArticle(
        url=url,
        title=meta.title if meta else None,
        text=text[:maxChars],
        truncated=len(text) > maxChars,
    )
