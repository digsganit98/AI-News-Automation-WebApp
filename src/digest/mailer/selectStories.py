"""Chooses which stories one person gets. Plain code, no LLM."""

from __future__ import annotations

from digest.mailer.recipients import Recipient


def _wanted(value: str, wanted: list[str]) -> bool:
    return not wanted or value.strip().lower() in {w.strip().lower() for w in wanted}


def matches(story: dict, person: Recipient) -> bool:
    return (
        story.get("importance", 1) >= person.minImportance
        and _wanted(story.get("category", ""), person.categories)
        and _wanted(story.get("cloudPlatform", ""), person.clouds)
        and _wanted(story.get("industryVertical", ""), person.verticals)
    )


def selectStories(
    stories: list[dict], person: Recipient, alreadySent: set[str] | None = None
) -> list[dict]:
    """The person's stories: unseen, matching their preferences, most important first."""
    sent = alreadySent or set()
    fresh = [s for s in stories if s["id"] not in sent and matches(s, person)]
    fresh.sort(key=lambda s: (s.get("importance", 1), s.get("createdAt", "")), reverse=True)
    return fresh[: person.maxStories]
