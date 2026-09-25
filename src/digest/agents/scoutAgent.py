"""Scout agent: triages its sources' new items, reads the important ones in full through
the MCP `fetchArticle` tool, and writes a short note for each real news item.

Exactly 2 LLM calls per scout per run (0 if its sources had nothing new):
  1. triage: keep / drop each item, pick up to N items worth reading in full
  2. brief: a note per kept item, using the full articles it chose to read

To save tokens on free tiers, items are shown as short refs ("i1", "i2"...) without URLs,
triage sees only titles and short excerpts, and code (not the LLM) attaches every URL.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from digest.agents.agentModels import (
    GoDeeper,
    ScoutBrief,
    ScoutNote,
    ScoutNoteDraft,
    ScoutReport,
    ScoutTriage,
)
from digest.agents.agentsConfig import Budget, ScoutSpec
from digest.agents.groundingStats import groundingStats
from digest.agents.llmRouter import LlmRouter
from digest.agents.promptKit import loadPrompt, untrusted
from digest.dataModels import RawItem

log = logging.getLogger(__name__)

FetchArticle = Callable[[str], Awaitable[dict]]
TRIAGE_EXCERPT_CHARS = 160  # enough to tell news from a tutorial
BRIEF_EXCERPT_CHARS = 300
ARTICLE_CHARS = 1800  # the key facts; more costs tokens without better notes
NEWSLETTER_CHARS = 5000
LINK_EXTRAS = ("githubRepo", "arxivUrl", "projectPage", "discussionUrl")


def triageView(ref: str, item: RawItem) -> dict:
    """What triage sees: just enough to decide keep or drop."""
    view: dict = {"ref": ref, "source": item.sourceName, "title": item.title}
    if item.excerpt:
        view["excerpt"] = item.excerpt[:TRIAGE_EXCERPT_CHARS]
    signals = {k: item.extra[k] for k in ("points", "upvotes") if item.extra.get(k)}
    if signals:
        view["signals"] = signals
    return view


def briefView(ref: str, item: RawItem, fullText: str | None = None) -> dict:
    """What the brief step sees: the item's facts, its links, and the article if read."""
    extra = item.extra
    view: dict = {"ref": ref, "source": item.sourceName, "title": item.title}
    if item.excerpt:
        view["excerpt"] = item.excerpt[:BRIEF_EXCERPT_CHARS]
    links = {k: extra[k] for k in LINK_EXTRAS if extra.get(k) and k != "discussionUrl"}
    if links:
        view["links"] = links
    if extra.get("_bodyText"):  # newsletter: the scout pulls stories out of the full text
        view["newsletterText"] = extra["_bodyText"][:NEWSLETTER_CHARS]
        view["newsletterLinks"] = extra.get("_links", [])[:40]
    if fullText:
        view["fullArticle"] = fullText[:ARTICLE_CHARS]
    return view


def allowedLinks(items: list[RawItem]) -> set[str]:
    """Every URL the scout may cite: the items, their extra links, newsletter links."""
    urls = {i.url for i in items}
    for i in items:
        urls |= {i.extra[k] for k in LINK_EXTRAS if i.extra.get(k)}
        urls |= {link["url"] for link in i.extra.get("_links", [])}
    return urls


def groundNote(
    draft: ScoutNoteDraft, byRef: dict[str, RawItem], allowed: set[str], texts: str
) -> ScoutNote | None:
    """Turn the LLM's draft into a note that points at collected data, or drop it."""
    item = byRef.get(draft.ref or "")
    if item is not None:
        url, itemId = item.url, item.id  # always the exact collected URL
    elif draft.url and draft.url in allowed:
        url, itemId = draft.url, None  # a story from a newsletter's own link list
    else:
        groundingStats["scoutNotesDropped"] += 1
        return None
    links = {k: v for k, v in draft.goDeeper.model_dump().items() if v}
    deeper = {k: v for k, v in links.items() if v in allowed or v in texts}
    groundingStats["scoutLinksRemoved"] += len(links) - len(deeper)
    return ScoutNote(
        itemId=itemId,
        title=draft.title,
        url=url,
        summary=draft.summary,
        goDeeper=GoDeeper(**deeper),
    )


async def runScout(
    spec: ScoutSpec,
    items: list[RawItem],
    router: LlmRouter,
    fetchArticle: FetchArticle,
    budget: Budget,
) -> ScoutReport:
    items = sorted(
        items, key=lambda i: i.publishedAt.isoformat() if i.publishedAt else "", reverse=True
    )[: budget.maxItemsPerScout]
    if not items:
        return ScoutReport()
    byRef = {f"i{n}": item for n, item in enumerate(items, 1)}

    triage = await router.structured(
        "scout",
        ScoutTriage,
        loadPrompt("scoutTriage", scoutName=spec.name, maxArticles=budget.maxArticlesPerScout),
        untrusted([triageView(ref, item) for ref, item in byRef.items()]),
    )
    keptRefs = [r for r in dict.fromkeys(triage.keepRefs) if r in byRef]
    if not keptRefs:
        log.info("%s: nothing newsworthy in %d items", spec.name, len(items))
        return ScoutReport()

    # The agent chose what to read; fetch those articles through the MCP tool.
    fullTexts: dict[str, str] = {}
    toRead = [r for r in triage.readInFullRefs if r in keptRefs][: budget.maxArticlesPerScout]
    for ref in toRead:
        try:
            article = await fetchArticle(byRef[ref].url)
            fullTexts[ref] = str(article.get("text", ""))
        except Exception as exc:  # a page that won't load just means no full text
            log.info("%s: could not read %s (%s)", spec.name, byRef[ref].url, exc)

    brief = await router.structured(
        "scout",
        ScoutBrief,
        loadPrompt("scoutBrief", scoutName=spec.name),
        untrusted([briefView(ref, byRef[ref], fullTexts.get(ref)) for ref in keptRefs]),
    )
    kept = [byRef[r] for r in keptRefs]
    allowed = allowedLinks(kept)
    texts = " ".join(fullTexts.values())
    notes = [n for n in (groundNote(d, byRef, allowed, texts) for d in brief.notes) if n]
    log.info("%s: %d items -> kept %d -> %d notes", spec.name, len(items), len(kept), len(notes))
    return ScoutReport(notes=notes)
