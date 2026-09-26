"""Writer and Editor agents: the 09:30 IST daily digest and op-ed.

writer: digest (1 call) + op-ed (1 call)
editor: fact-check both against the ORIGINAL articles of the stories they use (1 call);
        the originals are fetched fresh through the MCP fetchArticle tool, not stored
writer: fix the editor's issues, once, only in the flagged piece(s) (0-2 calls)

Every request is trimmed to fit ALL of the agent's models, including Groq's 8k tokens/minute
(fewer stories, shorter originals), so when Gemini is busy or out of quota, Groq can take over.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from digest.agents.agentModels import DigestDraft, EditorReview, OpEdDraft, Story
from digest.agents.llmRouter import LlmRouter, estimateTokens
from digest.agents.promptKit import loadPrompt, untrusted

log = logging.getLogger(__name__)

FetchArticle = Callable[[str], Awaitable[dict]]
MAX_ORIGINALS = 6  # stories whose original article the editor reads
ORIGINAL_CHARS = 1200  # per original: enough for the key facts, within free-tier limits
REVISION_MAX_OUTPUT = 2200  # one piece (digest or op-ed) rewritten in full
MIN_ORIGINAL_CHARS = 300  # shortest useful excerpt of an original before dropping one
MIN_WRITER_STORIES = 5  # the digest's top 5


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


def fits(text: str, tokensLeft: int | None) -> bool:
    return tokensLeft is None or estimateTokens(text) <= tokensLeft


def smallest(*budgets: int | None) -> int | None:
    known = [b for b in budgets if b is not None]
    return min(known) if known else None


def fitStories(stories: list[Story], tokensLeft: int | None) -> list[Story]:
    """The most important stories whose prompt fits (never fewer than the digest's top 5)."""
    kept = list(stories)
    while len(kept) > MIN_WRITER_STORIES and not fits(
        untrusted(storiesForPrompt(kept), "stories"), tokensLeft
    ):
        kept.pop()
    return kept


def fitOriginals(originals: list[dict], tokensLeft: int | None) -> list[dict]:
    """Shorten the originals' text until they fit; if even short excerpts don't, drop the
    last ones (the op-ed's, which come after the digest's top stories)."""
    if tokensLeft is None:
        return originals
    chars, kept = ORIGINAL_CHARS, list(originals)
    while kept:
        trimmed = [{**o, "text": o["text"][:chars]} for o in kept]
        if fits(untrusted(trimmed, "original articles"), tokensLeft):
            return trimmed
        if chars > MIN_ORIGINAL_CHARS:
            chars = max(MIN_ORIGINAL_CHARS, int(chars * 0.8))
        else:
            kept.pop()
    return []


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
    digestPrompt, opEdPrompt = loadPrompt("writerDigest"), loadPrompt("writerOpEd")
    stories = fitStories(
        stories,
        smallest(
            router.inputBudget("writer", digestPrompt, DigestDraft),
            router.inputBudget("writer", opEdPrompt, OpEdDraft),
        ),
    )
    data = untrusted(storiesForPrompt(stories), "stories")
    digest = await router.structured("writer", DigestDraft, digestPrompt, data)
    opEd = await router.structured("writer", OpEdDraft, opEdPrompt, data)
    digest.topStoryIds = keepKnownIds(digest.topStoryIds, stories, 5)
    opEd.basedOnStoryIds = keepKnownIds(opEd.basedOnStoryIds, stories, 3)

    usedIds = digest.topStoryIds + opEd.basedOnStoryIds
    originals = await fetchOriginals(usedIds, stories, fetchArticle)

    # The editor sees the drafts, the stories and the originals. If that's too much for the
    # tightest model, it gets only the stories the drafts use, then shorter originals.
    editorPrompt = loadPrompt("editor")
    draftsText = untrusted(drafts(digest, opEd), "drafts")
    editorBudget = router.inputBudget("editor", editorPrompt, EditorReview)
    editorData = data
    if editorBudget is not None:
        roomForOriginals = editorBudget - estimateTokens(data, draftsText)
        if roomForOriginals < len(originals) * MIN_ORIGINAL_CHARS // 3 + 100:
            used = [s for s in stories if s.id in set(usedIds)]
            editorData = untrusted(storiesForPrompt(used), "stories")
        editorBudget -= estimateTokens(editorData, draftsText)
    checkedOriginals = fitOriginals(originals, editorBudget)
    review = await router.structured(
        "editor",
        EditorReview,
        editorPrompt,
        f"{editorData}\n\n{untrusted(checkedOriginals, 'original articles')}\n\n{draftsText}",
    )
    revised = False
    if not review.approved and review.issues:
        # Revise only the piece(s) the editor flagged, one at a time: smaller requests
        # fit the free tiers' per-minute limits.
        revisionPrompt = loadPrompt("writerRevision")
        for where, draft in (("digest", digest), ("opEd", opEd)):
            issues = [i.model_dump() for i in review.issues if i.where == where]
            if not issues:
                continue
            request = (
                untrusted(draft.model_dump(), where)
                + "\n\nEditor's issues to fix:\n"
                + untrusted(issues, "issues")
            )
            budget = router.inputBudget("writer", revisionPrompt, type(draft), REVISION_MAX_OUTPUT)
            if budget is not None:
                budget -= estimateTokens(request)
            originalsText = untrusted(fitOriginals(originals, budget), "original articles")
            fixed = await router.structured(
                "writer",
                type(draft),
                revisionPrompt,
                f"{originalsText}\n\n{request}",
                maxOutput=REVISION_MAX_OUTPUT,
            )
            if where == "digest":
                digest = fixed
            else:
                opEd = fixed
            revised = True
        digest.topStoryIds = keepKnownIds(digest.topStoryIds, stories, 5)
        opEd.basedOnStoryIds = keepKnownIds(opEd.basedOnStoryIds, stories, 3)

    checked = sum(1 for o in checkedOriginals if o["text"] != "(not available)")
    return Edition(digest, opEd, review, revised, stories, checked)
