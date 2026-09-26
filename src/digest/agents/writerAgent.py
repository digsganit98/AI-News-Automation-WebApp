"""Writer and Editor agents: the 09:30 IST daily digest and op-ed.

writer: digest (1 call) + op-ed (1 call)
editor: fact-check both against the ORIGINAL articles of the stories they use (1 call);
        the originals are fetched fresh through the MCP fetchArticle tool, not stored
writer: fix the editor's issues, once, only in the flagged piece(s) (0-2 calls)
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from digest.agents.agentModels import DigestDraft, EditorReview, OpEdDraft, Story
from digest.agents.llmRouter import LlmRouter
from digest.agents.promptKit import loadPrompt, untrusted

log = logging.getLogger(__name__)

FetchArticle = Callable[[str], Awaitable[dict]]
MAX_ORIGINALS = 6  # stories whose original article the editor reads
ORIGINAL_CHARS = 1200  # per original: enough for the key facts, within free-tier limits
REVISION_MAX_OUTPUT = 2200  # one piece (digest or op-ed) rewritten in full


def storiesForPrompt(stories: list[Story]) -> list[dict]:
    return [
        {
            "id": s.id,
            "headline": s.headline,
            "summary": s.summary,
            "whyItMatters": s.whyItMatters,
            "category": s.category,
            "importance": s.importance,
            "sources": [src.name for src in s.sources],
        }
        for s in stories
    ]


def keepKnownIds(ids: list[str], stories: list[Story], fallback: int) -> list[str]:
    known = {s.id for s in stories}
    kept = [i for i in dict.fromkeys(ids) if i in known]
    return kept or [s.id for s in stories[:fallback]]


def drafts(digest: DigestDraft, opEd: OpEdDraft) -> dict:
    return {"digest": digest.model_dump(), "opEd": opEd.model_dump()}


async def fetchOriginals(
    storyIds: list[str], stories: list[Story], fetchArticle: FetchArticle
) -> list[dict]:
    """The original source text of the stories the drafts rely on."""
    byId = {s.id: s for s in stories}
    originals = []
    for storyId in list(dict.fromkeys(storyIds))[:MAX_ORIGINALS]:
        story = byId[storyId]
        url = story.sources[0].url
        try:
            text = str((await fetchArticle(url)).get("text", ""))[:ORIGINAL_CHARS]
        except Exception as exc:  # unreadable page: the editor is told it's unavailable
            log.info("Editor could not read %s (%s)", url, exc)
            text = ""
        originals.append({"storyId": storyId, "url": url, "text": text or "(not available)"})
    return originals


@dataclass
class Edition:
    digest: DigestDraft
    opEd: OpEdDraft
    review: EditorReview
    revised: bool = False
    stories: list[Story] = field(default_factory=list)
    originalsChecked: int = 0


async def writeEdition(
    stories: list[Story], router: LlmRouter, fetchArticle: FetchArticle
) -> Edition:
    """Stories must be sorted most important first."""
    data = untrusted(storiesForPrompt(stories), "stories")
    digest = await router.structured("writer", DigestDraft, loadPrompt("writerDigest"), data)
    opEd = await router.structured("writer", OpEdDraft, loadPrompt("writerOpEd"), data)
    digest.topStoryIds = keepKnownIds(digest.topStoryIds, stories, 5)
    opEd.basedOnStoryIds = keepKnownIds(opEd.basedOnStoryIds, stories, 3)

    originals = await fetchOriginals(
        digest.topStoryIds + opEd.basedOnStoryIds, stories, fetchArticle
    )
    review = await router.structured(
        "editor",
        EditorReview,
        loadPrompt("editor"),
        f"{data}\n\n{untrusted(originals, 'original articles')}\n\n"
        f"{untrusted(drafts(digest, opEd), 'drafts')}",
    )
    revised = False
    if not review.approved and review.issues:
        # Revise only the piece(s) the editor flagged, one at a time: smaller requests
        # fit the free tiers' per-minute limits.
        originalsText = untrusted(originals, "original articles")
        for where, draft in (("digest", digest), ("opEd", opEd)):
            issues = [i.model_dump() for i in review.issues if i.where == where]
            if not issues:
                continue
            fixed = await router.structured(
                "writer",
                type(draft),
                loadPrompt("writerRevision"),
                f"{originalsText}\n\n"
                + untrusted(draft.model_dump(), where)
                + "\n\nEditor's issues to fix:\n"
                + untrusted(issues, "issues"),
                maxOutput=REVISION_MAX_OUTPUT,
            )
            if where == "digest":
                digest = fixed
            else:
                opEd = fixed
            revised = True
        digest.topStoryIds = keepKnownIds(digest.topStoryIds, stories, 5)
        opEd.basedOnStoryIds = keepKnownIds(opEd.basedOnStoryIds, stories, 3)

    checked = sum(1 for o in originals if o["text"] != "(not available)")
    return Edition(digest, opEd, review, revised, stories, checked)
