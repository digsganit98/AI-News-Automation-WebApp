"""Per-source title filter, e.g. keep an educator's news videos but skip their tutorials.

Set in sources.yaml:

    titleFilter:
      include: ["\\bexplained\\b", "\\blaunch"]   # keep only titles matching at least one
      exclude: ["crash course", "\\bbootcamp\\b"]  # then drop titles matching any

Patterns are case-insensitive regular expressions. Leave `include` out to keep everything
that isn't excluded. The Phase 2 scout agents double-check what gets through.
"""

from __future__ import annotations

import re
from functools import cache

from digest.dataModels import RawItem


@cache
def _compile(patterns: tuple[str, ...]) -> re.Pattern[str] | None:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE) if patterns else None


def keepTitle(title: str, include: list[str] | None, exclude: list[str] | None) -> bool:
    includeRe = _compile(tuple(include or ()))
    excludeRe = _compile(tuple(exclude or ()))
    if includeRe and not includeRe.search(title):
        return False
    return not (excludeRe and excludeRe.search(title))


def applyTitleFilter(items: list[RawItem], titleFilter: dict | None) -> list[RawItem]:
    if not titleFilter:
        return items
    include, exclude = titleFilter.get("include"), titleFilter.get("exclude")
    return [i for i in items if keepTitle(i.title, include, exclude)]
