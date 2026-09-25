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
            }
        )
        for item in items
    ]
