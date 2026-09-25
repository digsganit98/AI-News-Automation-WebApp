"""Tidies items before dedupe: strips click-tracking from links and extra spaces from titles."""

from __future__ import annotations

from digest.dataModels import RawItem
from digest.urlCleaning import cleanUrl


def normalize(items: list[RawItem]) -> list[RawItem]:
    return [
        item.model_copy(
            update={
                "url": cleanUrl(item.url),
                "title": " ".join(item.title.split()),
                # Hacker News' front-page feed has only a "Comments" link as its summary.
                "excerpt": "" if item.excerpt.strip().lower() == "comments" else item.excerpt,
            }
        )
        for item in items
    ]
