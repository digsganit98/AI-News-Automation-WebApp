"""Saves what the agents produce, as public data the website reads:

data/stories/<date>.json   analyst stories, added to through the day (every 3 hours)
data/digests/<date>.json   the 10:00 IST digest + op-ed
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from digest.agents.agentModels import CATEGORIES, Story
from digest.agents.writerAgent import Edition
from digest.publish.saveDataFiles import DATA_DIR, digestDate, writeJson

STORIES_DIR = DATA_DIR / "stories"
DIGESTS_DIR = DATA_DIR / "digests"


def _readJson(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def loadRecentStories(
    days: int = 7, storiesDir: Path = STORIES_DIR, today: date | None = None
) -> list[dict]:
    """Stories from the last `days` days, newest first."""
    today = today or digestDate(datetime.now(UTC))
    stories: list[dict] = []
    for back in range(days):
        day = _readJson(storiesDir / f"{(today - timedelta(days=back)).isoformat()}.json")
        if day:
            stories.extend(reversed(day["stories"]))
    return stories


def saveStories(stories: list[Story], storiesDir: Path = STORIES_DIR) -> Path | None:
    if not stories:
        return None
    now = datetime.now(UTC)
    day = digestDate(now).isoformat()
    path = storiesDir / f"{day}.json"
    dayFile = _readJson(path) or {"date": day, "stories": []}
    known = {s["id"] for s in dayFile["stories"]}
    for story in stories:
        if story.id not in known:  # also skips repeats within this batch
            dayFile["stories"].append(story.model_dump(mode="json"))
            known.add(story.id)
    dayFile["updatedAt"] = now.isoformat()
    return writeJson(path, dayFile)


def storiesForEdition(hours: int = 30, storiesDir: Path = STORIES_DIR) -> list[Story]:
    """Stories from roughly the last day, most important first, for the daily edition."""
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    recent = [Story(**s) for s in loadRecentStories(2, storiesDir) if s["createdAt"] >= cutoff]
    return sorted(recent, key=lambda s: (-s.importance, s.createdAt))


def saveEdition(edition: Edition, models: dict[str, int], digestsDir: Path = DIGESTS_DIR) -> Path:
    now = datetime.now(UTC)
    day = digestDate(now).isoformat()
    byId = {s.id: s for s in edition.stories}
    sections = {
        cat: [
            s.id
            for s in edition.stories
            if s.category == cat and s.id not in edition.digest.topStoryIds
        ]
        for cat in CATEGORIES
    }
    return writeJson(
        digestsDir / f"{day}.json",
        {
            "date": day,
            "createdAt": now.isoformat(),
            "digest": edition.digest.model_dump(mode="json"),
            "opEd": edition.opEd.model_dump(mode="json"),
            "sections": {cat: ids for cat, ids in sections.items() if ids},
            "stories": {sid: s.model_dump(mode="json") for sid, s in byId.items()},
            "editor": {
                "approved": edition.review.approved,
                "issuesFound": len(edition.review.issues),
                "revised": edition.revised,
                "originalsChecked": edition.originalsChecked,
            },
            "models": models,
        },
    )
