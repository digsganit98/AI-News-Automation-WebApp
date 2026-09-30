"""House style for AI-written text, applied in code before anything is saved.

The prompts ask for plain, grammatical English without long dashes, but models don't always
listen (gpt-oss loves "—" and non-breaking hyphens). So every story, digest and take is
tidied here: dashes between clauses become commas, odd hyphen characters become "-", and
empty bullet points or paragraphs are removed.
"""

from __future__ import annotations

import re

ODD_HYPHENS = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "⁃": "-"})
# A long dash between clauses: — or ―, an en dash with a space on either side, or " -- ".
CLAUSE_DASH = re.compile(r"\s*[—―]\s*|\s*–\s+|\s+–\s*|\s+--\s+")
RANGE_DASH = re.compile(r"–")  # what's left is a range: 2–3, pages 10–12
SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
DOUBLE_COMMA = re.compile(r",\s*,+")
COMMA_BEFORE_STOP = re.compile(r",\s*([.;:!?])")
MANY_SPACES = re.compile(r"[ \t]{2,}")


def tidyText(text: str) -> str:
    """One piece of AI-written text in house style."""
    text = text.translate(ODD_HYPHENS)
    text = CLAUSE_DASH.sub(", ", text)
    text = RANGE_DASH.sub("-", text)
    text = SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = DOUBLE_COMMA.sub(",", text)
    text = COMMA_BEFORE_STOP.sub(r"\1", text)
    text = MANY_SPACES.sub(" ", text).strip()
    return text.lstrip(",").strip()


def tidyLines(lines: list[str]) -> list[str]:
    """Bullets or paragraphs: tidied, with empty ones removed."""
    return [t for t in (tidyText(line) for line in lines) if t]


TAKE_TEXT_FIELDS = ("theme", "title", "verdict", "whatHappened", "take", "watchFor")


def tidyStory(story) -> None:
    story.headline = tidyText(story.headline)
    story.summary = tidyText(story.summary)
    story.whyItMatters = tidyText(story.whyItMatters)


def tidyOutcome(outcome) -> None:
    """Everything the agents wrote in this run, in house style (in place)."""
    for story in outcome.stories:
        tidyStory(story)
    edition = outcome.edition
    if edition is None:
        return
    digest = edition.digest
    digest.headline, digest.dek = tidyText(digest.headline), tidyText(digest.dek)
    digest.intro = tidyText(digest.intro)
    digest.tldr = tidyLines(digest.tldr)
    for take in edition.takes.takes:
        for name in TAKE_TEXT_FIELDS:
            setattr(take, name, tidyText(getattr(take, name)))
    for story in edition.stories:
        tidyStory(story)
