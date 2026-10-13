"""Remembers which stories each person already got, so nobody gets one twice.

state/ is committed to a public repo, so addresses are stored only as a short salted hash.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from digest.envSettings import env
from digest.publish.saveDataFiles import STATE_DIR, writeJson

SENT_FILE = STATE_DIR / "emailSent.json"
KEEP_IDS = 400  # per person; older ids are far outside the story window anyway


def personKey(address: str) -> str:
    salt = env("EMAIL_LOG_SALT", env("GMAIL_ADDRESS", "genai-daily"))
    return hashlib.sha256(f"{salt}:{address.strip().lower()}".encode()).hexdigest()[:16]


class SentLog:
    def __init__(self, path: Path = SENT_FILE):
        self.path = path
        self.people: dict[str, list[str]] = {}
        if path.exists():
            self.people = json.loads(path.read_text(encoding="utf-8")).get("people", {})

    def sentIds(self, address: str) -> set[str]:
        return set(self.people.get(personKey(address), []))

    def record(self, address: str, storyIds: list[str]) -> None:
        key = personKey(address)
        merged = [*self.people.get(key, []), *storyIds]
        self.people[key] = merged[-KEEP_IDS:]

    def save(self) -> None:
        writeJson(self.path, {"people": self.people})
