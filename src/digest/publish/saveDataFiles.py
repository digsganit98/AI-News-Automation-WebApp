"""Reads and writes the files in data/ (public, committed) and state/ (pipeline memory)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from digest.dataModels import CollectionResult
from digest.envSettings import REPO_ROOT, env

DATA_DIR = REPO_ROOT / "data"
STATE_DIR = REPO_ROOT / "state"
SEEN_FILE = STATE_DIR / "seen.json"


def digestDate(at: datetime) -> date:
    """The digest's date in the audience's timezone (DIGEST_TIMEZONE, default Asia/Kolkata)."""
    return at.astimezone(ZoneInfo(env("DIGEST_TIMEZONE", "Asia/Kolkata"))).date()


def writeJson(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def writeCollection(result: CollectionResult, outDir: Path | None = None) -> Path:
    """Add this run's items to the day's file, data/raw/<date>.json.

    The pipeline runs every 3 hours, so a day's file grows through the day: each run adds
    its new items and a record of which sources worked. Private fields (e.g. newsletter
    full text) are never written.
    """
    day = digestDate(result.runAt)
    path = (outDir or DATA_DIR / "raw") / f"{day.isoformat()}.json"
    dayFile = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"date": day.isoformat(), "runs": [], "items": []}
    )

    knownIds = {i["id"] for i in dayFile["items"]}
    newItems = []
    for item in result.items:
        if item.id not in knownIds:
            newItems.append({**item.public(), "collectedAt": result.runAt.isoformat()})
            knownIds.add(item.id)

    dayFile["updatedAt"] = result.runAt.isoformat()
    dayFile["runs"].append(
        {
            "runAt": result.runAt.isoformat(),
            "newItems": len(newItems),
            "health": [h.model_dump(mode="json") for h in result.health],
        }
    )
    dayFile["items"].extend(newItems)
    return writeJson(path, dayFile)
