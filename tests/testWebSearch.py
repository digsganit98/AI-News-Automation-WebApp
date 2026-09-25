"""Web-search collector (Tavily) and research-log source types, without network calls."""

from __future__ import annotations

from datetime import UTC, datetime

from conftest import makeCollector

from digest.agents.agentModels import Story
from digest.agents.runAgents import sourceTypeFor
from digest.collectors.webSearchCollector import parseResults, queriesForThisRun


def testQueriesRotateAndStayWithinTheFreeTier():
    queries = [f"q{i}" for i in range(12)]
    runs = [
        queriesForThisRun(queries, 4, datetime(2026, 9, 25, h, 30, tzinfo=UTC))
        for h in range(0, 24, 3)
    ]
    assert all(len(r) == 4 for r in runs)  # 4 searches x 8 runs = 32 a day, ~960 a month
    assert {q for r in runs for q in r} == set(queries)  # every query runs each day


def testSearchResultsBecomeItems():
    data = {
        "results": [
            {
                "url": "https://example.com/launch",
                "title": "Lab launches model",
                "content": "Details.",
                "score": 0.61,
                "published_date": "Wed, 23 Sep 2026 10:00:00 GMT",
            },
            {"url": "", "title": "no url"},
        ]
    }
    [item] = parseResults(data, "new model", makeCollector("webSearch"))
    assert item.url == "https://example.com/launch"
    assert item.publishedAt == datetime(2026, 9, 23, 10, 0, tzinfo=UTC)
    assert item.extra == {"query": "new model", "score": 0.61}


def testSourceTypeFollowsWhereTheStoryWasFound():
    def story(*urls):
        return Story(
            id="s",
            createdAt="2026-09-25T00:00:00+00:00",
            headline="H",
            summary="S",
            category="Research",
            importance=3,
            sources=[{"name": "n", "url": u} for u in urls],
        )

    groups = {"https://lab/x": "labs", "https://hn/y": "community", "https://web/z": "webSearch"}
    assert sourceTypeFor(story("https://lab/x", "https://hn/y"), groups) == "Directed"
    assert sourceTypeFor(story("https://hn/y"), groups) == "Emergent"
    assert sourceTypeFor(story("https://web/z"), groups) == "AI-assisted"
