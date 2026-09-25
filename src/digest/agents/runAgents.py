"""Runs the agent graph on newly collected items and saves the results.

The scouts read full articles through the project's own MCP server (`digest mcp`),
started here as a child process and reached with langchain-mcp-adapters.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from digest.agents.agentModels import Story
from digest.agents.agentsConfig import AgentsConfig, loadAgentsConfig
from digest.agents.groundingStats import groundingStats, resetGroundingStats
from digest.agents.llmBudget import LlmBudget
from digest.agents.llmRouter import CallRecord, LlmRouter
from digest.agents.newsGraph import GraphDeps, buildNewsGraph, splitItemsByScout
from digest.agents.scoutAgent import FetchArticle
from digest.agents.writerAgent import Edition
from digest.dataModels import RawItem
from digest.envSettings import env
from digest.publish.saveStories import loadRecentStories, storiesForEdition
from digest.sourcesConfig import loadConfig

log = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    ran: bool
    stories: list[Story] = field(default_factory=list)
    edition: Edition | None = None
    errors: list[str] = field(default_factory=list)
    calls: list[CallRecord] = field(default_factory=list)
    skippedReason: str = ""
    grounding: dict[str, int] = field(default_factory=dict)  # what the grounding checks removed


def _toolOutputToDict(output: object) -> dict:
    """MCP tool results arrive as a JSON string or a list of text blocks."""
    if isinstance(output, tuple):
        output = output[0]
    if isinstance(output, list):
        output = "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in output)
    if isinstance(output, str):
        return json.loads(output)
    return dict(output)  # type: ignore[arg-type]


@asynccontextmanager
async def mcpFetchArticle():
    """Yields fetchArticle(url) backed by the MCP news-tools server."""
    client = MultiServerMCPClient(
        {
            "news": {
                "command": sys.executable,
                "args": ["-m", env("MCP_SERVER_MODULE"), "mcp"],
                "transport": "stdio",
            }
        }
    )
    async with client.session("news") as session:
        tools = {t.name: t for t in await load_mcp_tools(session)}
        tool = tools["fetchArticle"]

        async def fetchArticle(url: str) -> dict:
            return _toolOutputToDict(await tool.ainvoke({"url": url}))

        yield fetchArticle


# Source Type (research log): official/known sources are "Directed"; items spotted on
# community platforms are "Emergent"; found by the web-search scout, "AI-assisted".
DIRECTED_GROUPS = {"labs", "research", "cloud"}


def sourceTypeFor(story: Story, urlGroup: dict[str, str]) -> str:
    groups = {urlGroup.get(src.url, "") for src in story.sources}
    if groups & DIRECTED_GROUPS:
        return "Directed"
    return "AI-assisted" if "webSearch" in groups else "Emergent"


def mergeForEdition(runStories: list[Story]) -> list[Story]:
    """Today's edition covers this run's stories plus those from the last ~30 hours."""
    byId = {s.id: s for s in storiesForEdition()}
    byId.update({s.id: s for s in runStories})
    return sorted(byId.values(), key=lambda s: (-s.importance, s.createdAt))


async def runAgents(
    items: list[RawItem],
    mode: str,
    config: AgentsConfig | None = None,
    router: LlmRouter | None = None,
    fetchArticle: FetchArticle | None = None,
    saveUsage: bool = True,
) -> AgentRunResult:
    config = config or loadAgentsConfig()
    router = router or LlmRouter(config, LlmBudget(config.budget, mode))
    if not router.isAvailable():
        return AgentRunResult(
            False, skippedReason="no LLM API keys set (GROQ_API_KEY / GEMINI_API_KEY)"
        )
    if not items and mode != "dailyEdition":
        return AgentRunResult(False, skippedReason="no new items")

    resetGroundingStats()
    groupOf = {s.id: s.opt("group", "") for s in loadConfig().sources}
    state = {
        "mode": mode,
        "itemsByScout": splitItemsByScout(items, config, groupOf),
        "recentStories": loadRecentStories(7),
    }

    async def run(fetch: FetchArticle) -> dict:
        deps = GraphDeps(config, router, fetch, mergeForEdition)
        return await buildNewsGraph(deps).ainvoke(state)

    if fetchArticle is not None:
        final = await run(fetchArticle)
    else:
        async with mcpFetchArticle() as fetch:
            final = await run(fetch)

    if saveUsage:
        router.budget.save()
    urlGroup = {i.url: groupOf.get(i.source, "") for i in items}
    for story in final.get("stories", []):
        story.sourceType = sourceTypeFor(story, urlGroup)
    return AgentRunResult(
        True,
        stories=final.get("stories", []),
        edition=final.get("edition"),
        errors=final.get("errors", []),
        calls=router.calls,
        grounding=dict(groundingStats),
    )
