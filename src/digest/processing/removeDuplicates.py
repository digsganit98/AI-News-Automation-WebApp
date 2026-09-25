"""Removes items already covered in earlier runs, and repeats within a run.

Items from different sources about the same event are NOT merged here: the analyst agent
groups those into one story that lists every source.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rapidfuzz import fuzz

from digest.dataModels import RawItem

TITLE_SIMILARITY = 92  # 0-100; same-source titles at least this similar count as repeats
KEEP_DAYS = 30
_NUMBER = re.compile(r"\d+(?:\.\d+)*")


def isSameTitle(a: str, b: str) -> bool:
    """Near-identical titles, e.g. a typo fix or extra punctuation.

    Titles with different numbers are never the same: "GPT-5 released" vs "GPT-6 released".
    """
    if set(_NUMBER.findall(a)) != set(_NUMBER.findall(b)):
        return False
    return fuzz.token_sort_ratio(a.lower(), b.lower()) >= TITLE_SIMILARITY


class SeenStore:
    """Ids of items already used, kept in state/seen.json as {id: first_seen_iso}."""

    def __init__(self, path: Path):
        self.path = path
        self.seen: dict[str, str] = {}
        if path.exists():
            self.seen = json.loads(path.read_text(encoding="utf-8"))

    def __contains__(self, itemId: str) -> bool:
        return itemId in self.seen

    def add(self, items: list[RawItem], now: datetime | None = None) -> None:
        stamp = (now or datetime.now(UTC)).isoformat()
        for item in items:
            self.seen.setdefault(item.id, stamp)

    def prune(self, now: datetime | None = None) -> None:
        cutoff = (now or datetime.now(UTC)) - timedelta(days=KEEP_DAYS)
        self.seen = {k: v for k, v in self.seen.items() if datetime.fromisoformat(v) >= cutoff}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.seen, indent=0, sort_keys=True), encoding="utf-8")


def inWindow(items: list[RawItem], since: datetime) -> list[RawItem]:
    """Keep items published after `since`. Undated items are kept; the seen-list stops repeats."""
    return [i for i in items if i.publishedAt is None or i.publishedAt >= since]


def dedupe(items: list[RawItem], seen: SeenStore) -> list[RawItem]:
    kept: list[RawItem] = []
    ids: set[str] = set()
    for item in items:
        if item.id in seen or item.id in ids:
            continue
        if any(k.source == item.source and isSameTitle(k.title, item.title) for k in kept):
            continue
        ids.add(item.id)
        kept.append(item)
    return kept
