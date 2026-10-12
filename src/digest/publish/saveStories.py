"""Saves what the agents produce, as public data the website reads:

data/stories/<date>.json   analyst stories, added to through the day (every 3 hours)
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from digest.agents.agentModels import Story
from digest.publish.saveDataFiles import DATA_DIR, digestDate, writeJson

STORIES_DIR = DATA_DIR / "stories"


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
