"""Who gets the email, and what they want in it.

The repo is public, so addresses are never committed. They come from a GitHub secret
(`EMAIL_RECIPIENTS`, a JSON list) or, for local runs, from a file named by
`EMAIL_RECIPIENTS_FILE` that git ignores. An empty list in a filter field means "no filter".
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from digest.envSettings import loadEnv

ADDRESS = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Recipient(BaseModel):
    name: str = ""
    email: str
    enabled: bool = True
    categories: list[str] = Field(default_factory=list)  # Tech Domain, e.g. "Agentic Systems"
    clouds: list[str] = Field(default_factory=list)  # e.g. "AWS", "Cross-cloud"
    verticals: list[str] = Field(default_factory=list)  # e.g. "BFSI", "Healthcare"
    minImportance: int = Field(default=1, ge=1, le=5)
    maxStories: int = Field(default=8, ge=1, le=30)

    @field_validator("email")
    @classmethod
    def validAddress(cls, value: str) -> str:
        value = value.strip()
        if not ADDRESS.match(value):
            raise ValueError(f"not an email address: {value!r}")
        return value

    @property
    def greetingName(self) -> str:
        return self.name.strip() or "there"


class RecipientsError(RuntimeError):
    pass


def parseRecipients(text: str) -> list[Recipient]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RecipientsError(f"Recipients are not valid JSON: {e}") from e
    if not isinstance(data, list):
        raise RecipientsError("Recipients must be a JSON list of people.")
    people = [Recipient.model_validate(entry) for entry in data]
    seen: set[str] = set()
    unique = []
    for p in people:
        key = p.email.lower()
        if key not in seen:  # the same address twice would get two emails
            seen.add(key)
            unique.append(p)
    return unique


def loadRecipients() -> list[Recipient]:
    """Enabled recipients from `EMAIL_RECIPIENTS` or `EMAIL_RECIPIENTS_FILE`."""
    loadEnv()
    text = os.environ.get("EMAIL_RECIPIENTS", "").strip()
    if not text and (path := os.environ.get("EMAIL_RECIPIENTS_FILE", "").strip()):
        text = Path(path).read_text(encoding="utf-8")
    if not text:
        raise RecipientsError(
            "No recipients. Set the EMAIL_RECIPIENTS secret (a JSON list) or, locally, "
            "EMAIL_RECIPIENTS_FILE in .env. See docs/emailAgentPlan.md."
        )
    return [p for p in parseRecipients(text) if p.enabled]
