"""Tidies items before dedupe: strips click-tracking from links, extra spaces from titles,
and feed boilerplate from summaries."""

from __future__ import annotations

import re

from digest.dataModels import RawItem
from digest.urlCleaning import cleanUrl

# Reddit's RSS puts "submitted by /u/name to r/sub [link] [comments]" in every summary.
_REDDIT_BOILERPLATE = re.compile(
    r"\s*submitted by\s+/u/\S+(\s+to\s+r/\S+)?\s*(\[link\])?\s*(\[comments\])?\s*$", re.IGNORECASE
)


def cleanExcerpt(text: str) -> str:
    return _REDDIT_BOILERPLATE.sub("", text).strip()


def normalize(items: list[RawItem]) -> list[RawItem]:
    return [
        item.model_copy(
            update={
                "url": cleanUrl(item.url),
                "title": " ".join(item.title.split()),
                "excerpt": cleanExcerpt(item.excerpt),
            }
        )
        for item in items
    ]
