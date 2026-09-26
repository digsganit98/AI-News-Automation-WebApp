"""The agent workflow, as a LangGraph graph. The order is fixed in code, not chosen by an LLM:

    START ─┬─ scout: labs & research ─┐
           ├─ scout: community ───────┤
           ├─ scout: video & newsletters ─┼─► analyst ─► (09:30 IST only) writer + editor ─► END
           └─ scout: X ───────────────┘

The four scouts run in parallel. One failing agent never stops the others: its error is
recorded and the run carries on with what it has.
"""

from __future__ import annotations

import logging
import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from digest.agents.agentModels import ScoutNote, Story
from digest.agents.agentsConfig import AgentsConfig
from digest.agents.analystAgent import runAnalyst
from digest.agents.llmRouter import LlmRouter, LlmUnavailableError
from digest.agents.scoutAgent import FetchArticle, runScout
from digest.agents.writerAgent import Edition, writeEdition
from digest.dataModels import RawItem
from digest.monitoring.langfuseTracing import observeAgent

log = logging.getLogger(__name__)


class NewsState(TypedDict, total=False):
    mode: str  # "update" | "dailyEdition"
    itemsByScout: dict[str, list[RawItem]]
    recentStories: list[dict]
    notes: Annotated[list[tuple[str, ScoutNote]], operator.add]  # filled by all scouts
    stories: list[Story]
    edition: Edition | None
    errors: Annotated[list[str], operator.add]


@dataclass
class GraphDeps:
    config: AgentsConfig
    router: LlmRouter
    fetchArticle: FetchArticle
    editionStories: Callable[
        [list[Story]], list[Story]
    ]  # this run's stories -> stories to write about


def summarizeForTrace(result: dict) -> dict:
    """A small, readable output for the agent's Langfuse span."""
    summary: dict = {}
    if "notes" in result:
        summary["notes"] = [n.title for _, n in result["notes"]]
    if "stories" in result:
        summary["stories"] = [f"[{s.importance}] {s.headline}" for s in result["stories"]]
    if result.get("edition"):
        e = result["edition"]
        summary["digest"] = e.digest.headline
        summary["opEd"] = e.opEd.title
        summary["editorApproved"] = e.review.approved
    if result.get("errors"):
        summary["errors"] = result["errors"]
    return summary


def traced(name: str, node):
    """Record a graph node as an agent span in Langfuse (no-op when monitoring is off)."""

    async def run(state: NewsState) -> dict:
        with observeAgent(name) as span:
            result = await node(state)
            if span is not None:
                span.update(output=summarizeForTrace(result))
            return result

    return run


def buildNewsGraph(deps: GraphDeps):
    graph = StateGraph(NewsState)

    def makeScoutNode(scoutId: str):
        spec = deps.config.scouts[scoutId]

        async def scoutNode(state: NewsState) -> dict:
            items = state.get("itemsByScout", {}).get(scoutId, [])
            if not items:
                return {"notes": []}
            try:
                report = await runScout(
                    spec, items, deps.router, deps.fetchArticle, deps.config.budget
                )
            except LlmUnavailableError as exc:
                log.warning("%s skipped: %s", spec.name, exc)
                return {"notes": [], "errors": [f"{spec.name}: {exc}"]}
            names = {i.url: i.sourceName for i in items}
            byId = {i.id: i.sourceName for i in items}
            return {
                "notes": [
                    (byId.get(n.itemId or "") or names.get(n.url) or spec.name, n)
                    for n in report.notes
                ]
            }

        return scoutNode

    async def analystNode(state: NewsState) -> dict:
        try:
            stories = await runAnalyst(
                state.get("notes", []), state.get("recentStories", []), deps.router
            )
        except LlmUnavailableError as exc:
            log.warning("Analyst skipped: %s", exc)
            return {"stories": [], "errors": [f"Analyst: {exc}"]}
        return {"stories": stories}

    async def writerEditorNode(state: NewsState) -> dict:
        stories = deps.editionStories(state.get("stories", []))
        if not stories:
            return {"edition": None, "errors": ["Writer: no stories to write about"]}
        maxStories = deps.config.budget.maxStoriesForWriter
        try:
            return {
                "edition": await writeEdition(stories[:maxStories], deps.router, deps.fetchArticle)
            }
        except LlmUnavailableError as exc:
            log.warning("Daily edition skipped: %s", exc)
            return {"edition": None, "errors": [f"Writer/editor: {exc}"]}

    for scoutId in deps.config.scouts:
        graph.add_node(
            f"scout_{scoutId}", traced(deps.config.scouts[scoutId].name, makeScoutNode(scoutId))
        )
        graph.add_edge(START, f"scout_{scoutId}")
        graph.add_edge(f"scout_{scoutId}", "analyst")
    graph.add_node("analyst", traced("Analyst", analystNode))
    graph.add_node("writerEditor", traced("Writer + Editor", writerEditorNode))
    graph.add_conditional_edges(
        "analyst",
        lambda state: "writerEditor" if state.get("mode") == "dailyEdition" else END,
        {"writerEditor": "writerEditor", END: END},
    )
    graph.add_edge("writerEditor", END)
    return graph.compile()


def splitItemsByScout(
    items: list[RawItem], config: AgentsConfig, groupOf: dict[str, str]
) -> dict[str, list[RawItem]]:
    """Give each scout the items from its source groups."""
    scoutOfGroup = {g: scoutId for scoutId, spec in config.scouts.items() for g in spec.groups}
    split: dict[str, list[RawItem]] = {scoutId: [] for scoutId in config.scouts}
    for item in items:
        scoutId = scoutOfGroup.get(groupOf.get(item.source, ""))
        if scoutId:
            split[scoutId].append(item)
    return split
