"""Analyst agent: turns the scouts' notes into stories.

Groups notes about the same event, compares with the last 7 days of stories (so the
same news on a different day isn't repeated), categorizes and scores importance.
One LLM call per 40 notes (normally one per run).

The analyst sees numbered notes without URLs and cites them by number ("noteRefs");
code attaches the real sources and links. That saves output tokens and means a story
can only ever point at pages that were actually collected.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from digest.agents.agentModels import (
    CATEGORIES,
    AnalystReport,
    GoDeeper,
    ScoutNote,
    Story,
    StorySource,
)
from digest.agents.groundingStats import groundingStats
from digest.agents.llmRouter import LlmRouter
from digest.agents.promptKit import loadPrompt, untrusted
from digest.envSettings import env

NOTES_PER_CALL = 40
MEMORY_STORIES = 40  # recent headlines the analyst compares against


def storyId(headline: str, firstUrl: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", headline.lower()).strip("-")[:48].rstrip("-")
    return f"{slug}-{hashlib.sha1(firstUrl.encode()).hexdigest()[:6]}"


def mergeGoDeeper(notes: list[ScoutNote]) -> GoDeeper:
    merged: dict[str, str] = {}
    for note in notes:
        for kind, url in note.goDeeper.model_dump().items():
            if url and kind not in merged:
                merged[kind] = url
    return GoDeeper(**merged)


async def runAnalyst(
    notes: list[tuple[str, ScoutNote]],  # (source name, note)
    recentStories: list[dict],
    router: LlmRouter,
) -> list[Story]:
    """Returns new and follow-up stories; already-covered ones are dropped."""
    if not notes:
        return []
    memory = [f"{s['id']} | {s['headline']}" for s in recentStories[:MEMORY_STORIES]]
    now = datetime.now(UTC).isoformat()

    stories: list[Story] = []
    for start in range(0, len(notes), NOTES_PER_CALL):
        chunk = notes[start : start + NOTES_PER_CALL]
        payload = {
            "notes": [
                {"n": n, "source": name, "title": note.title, "summary": note.summary}
                for n, (name, note) in enumerate(chunk, 1)
            ],
            "recentStories": memory,
        }
        report = await router.structured(
            "analyst",
            AnalystReport,
            loadPrompt("analyst", categories=", ".join(CATEGORIES)),
            untrusted(payload, "notes and recent stories"),
        )
        for draft in report.stories:
            if draft.status == "alreadyCovered":
                continue
            refs = [r for r in dict.fromkeys(draft.noteRefs) if 1 <= r <= len(chunk)]
            groundingStats["analystRefsInvalid"] += len(set(draft.noteRefs)) - len(refs)
            if not refs:  # every story must rest on at least one real note
                groundingStats["analystStoriesDropped"] += 1
                continue
            used = [chunk[r - 1] for r in refs]
            sources = [StorySource(name=name, url=note.url) for name, note in used]
            fields = draft.model_dump(exclude={"noteRefs", "researcher"})
            stories.append(
                Story(
                    **fields,
                    id=storyId(draft.headline, sources[0].url),
                    createdAt=now,
                    researcher=(draft.researcher or "").strip() or env("DEFAULT_RESEARCHER", ""),
                    sources=sources,
                    goDeeper=mergeGoDeeper([note for _, note in used]),
                )
            )
    return stories
