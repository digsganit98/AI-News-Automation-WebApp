"""Newsletters (TLDR AI, The Rundown, Superhuman...) read from a dedicated Gmail inbox.

Setup (see README): subscribe the inbox to each newsletter and add a Gmail filter that puts
them under the label set in sources.yaml. Messages are read with BODY.PEEK so nothing is
marked read or changed. Re-runs are safe because repeats are removed by the seen-list.

Each email becomes one RawItem. The full text and links are kept in private `extra`
fields (names starting with "_"). The LLM step turns them into individual stories, and
private fields are never written to the public data files.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import logging
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime

import httpx
from bs4 import BeautifulSoup

from digest.collectors.collectorBase import Collector, CollectorError, excerpt, register, utc
from digest.dataModels import RawItem
from digest.envSettings import env

log = logging.getLogger(__name__)

MAX_LINKS = 80


def _decode(value: str | None) -> str:
    return str(make_header(decode_header(value))) if value else ""


def _bodyHtmlAndText(msg: Message) -> tuple[str, str]:
    html, text = "", ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        decoded = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/html" and not html:
            html = decoded
        elif ctype == "text/plain" and not text:
            text = decoded
    return html, text


def parseNewsletter(raw: bytes, senders: dict[str, str], collector: Collector) -> RawItem | None:
    """Turn one raw email into a RawItem, or None if it is not from a known newsletter."""
    msg = email.message_from_bytes(raw)
    fromName, fromAddr = parseaddr(_decode(msg.get("From")))
    match = next((name for key, name in senders.items() if key.lower() in fromAddr.lower()), None)
    if match is None:
        return None

    html, text = _bodyHtmlAndText(msg)
    links: list[dict[str, str]] = []
    viewOnline = None
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href^=http]"):
            label = a.get_text(" ", strip=True)
            href = a["href"]
            if viewOnline is None and "view" in label.lower() and "online" in label.lower():
                viewOnline = href
            elif label and len(links) < MAX_LINKS:
                links.append({"text": label, "url": href})
        text = soup.get_text("\n", strip=True)

    messageId = (msg.get("Message-ID") or "").strip("<> ")
    date = msg.get("Date")
    return collector.item(
        title=_decode(msg.get("Subject")) or f"{match} newsletter",
        # "mid:" is the standard URI scheme for an email Message-ID (RFC 2392).
        url=viewOnline or f"mid:{messageId}",
        publishedAt=utc(parsedate_to_datetime(date)) if date else None,
        excerpt=excerpt(text),
        author=match,
        extra={"newsletter": match, "_bodyText": text, "_links": links},
    )


@register
class NewslettersImapCollector(Collector):
    type = "newsletterInbox"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        return await asyncio.to_thread(self._collectSync, since)

    def _collectSync(self, since: datetime) -> list[RawItem]:
        address = env("GMAIL_ADDRESS", "")
        password = env("GMAIL_APP_PASSWORD", "")
        if not address or not password:
            raise CollectorError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set")
        senders: dict[str, str] = self.source.opt("senders", {})
        label = self.source.opt("label", "INBOX")

        # IMAP SINCE works on whole days, so go back one extra day and let the
        # time-window filter do the exact cut.
        sinceDay = (since - timedelta(days=1)).strftime("%d-%b-%Y")
        items: list[RawItem] = []
        with imaplib.IMAP4_SSL(env("GMAIL_IMAP_HOST"), int(env("GMAIL_IMAP_PORT"))) as imap:
            imap.login(address, password)
            status, _ = imap.select(f'"{label}"', readonly=True)
            if status != "OK":
                raise CollectorError(f"Gmail label '{label}' not found")
            _, data = imap.search(None, "SINCE", sinceDay)
            for num in data[0].split():
                _, parts = imap.fetch(num, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if raw and (item := parseNewsletter(raw, senders, self)):
                    items.append(item)
        log.info("Read %d newsletter emails", len(items))
        return items
