"""Content safety: items whose title or summary matches a blocked term are dropped.

Applied to every source at collection time, before any agent or page sees the item. Sexual or
explicit content, and racist, sexist, misogynistic, hateful or anti-religious content, is never
collected. The terms are `blockedTerms` in config/sources.yaml (the website applies the same
list to data already collected).
"""

from __future__ import annotations

import re

from digest.dataModels import RawItem


def blockedPattern(terms: list[str]) -> re.Pattern[str] | None:
    if not terms:
        return None
    return re.compile("|".join(f"(?:{t})" for t in terms), re.IGNORECASE)


def isBlocked(text: str, pattern: re.Pattern[str] | None) -> bool:
    return bool(pattern and pattern.search(text))


def dropBlocked(items: list[RawItem], pattern: re.Pattern[str] | None) -> list[RawItem]:
    return [i for i in items if not isBlocked(f"{i.title} {i.excerpt}", pattern)]


def storyText(story) -> str:
    return f"{story.headline} {story.summary} {story.whyItMatters}"


def guardOutput(outcome, pattern: re.Pattern[str] | None) -> list[str]:
    """Last check on what the AI wrote, before anything is saved or published.

    Stories that break the policy are removed. If the digest, the op-ed or any story they use
    breaks it, the whole edition is withheld (a later run writes a new one). Returns what
    was removed, for the run summary.
    """
    removed = [s.headline for s in outcome.stories if isBlocked(storyText(s), pattern)]
    outcome.stories = [s for s in outcome.stories if not isBlocked(storyText(s), pattern)]
    edition = outcome.edition
    if edition is not None:
        digest, opEd = edition.digest, edition.opEd
        text = " ".join(
            [digest.headline, digest.dek, digest.intro, *digest.tldr]
            + [opEd.title, opEd.dek, *opEd.paragraphs]
            + [storyText(s) for s in edition.stories]
        )
        if isBlocked(text, pattern):
            outcome.edition = None
            removed.append("the daily edition (a later run will write a new one)")
    return removed
