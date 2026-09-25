"""Hugging Face: trending models and the community-curated Daily Papers.

Where new open models and papers show up first. Both are free public JSON APIs
(HF_TRENDING_MODELS_API_URL, HF_DAILY_PAPERS_API_URL).
"""

from __future__ import annotations

from datetime import datetime

import httpx
from dateutil import parser as dateparser

from digest.collectors.collectorBase import Collector, excerpt, fetch, register, utc
from digest.dataModels import RawItem
from digest.envSettings import envUrl


def parseDailyPapers(data: list[dict], minUpvotes: int, collector: Collector) -> list[RawItem]:
    items = []
    for entry in data:
        paper = entry.get("paper", {})
        upvotes = paper.get("upvotes", 0)
        if not paper.get("id") or upvotes < minUpvotes:
            continue
        published = paper.get("submittedOnDailyAt") or entry.get("publishedAt")
        authors = [a["name"] for a in paper.get("authors", []) if a.get("name")]
        items.append(
            collector.item(
                title=paper.get("title", "").strip(),
                url=envUrl("HF_PAPER_URL", id=paper["id"]),
                publishedAt=utc(dateparser.isoparse(published)) if published else None,
                excerpt=excerpt(paper.get("summary", "")),
                author=", ".join(authors) or None,
                extra={
                    "upvotes": upvotes,
                    "githubRepo": paper.get("githubRepo"),
                    "projectPage": paper.get("projectPage"),
                    "arxivUrl": envUrl("ARXIV_ABS_URL", id=paper["id"]),
                },
            )
        )
    return items


def parseTrendingModels(data: list[dict], collector: Collector) -> list[RawItem]:
    return [
        collector.item(
            title=f"Trending model: {model['id']}",
            url=envUrl("HF_MODEL_URL", id=model["id"]),
            author=model.get("author"),
            extra={
                "likes": model.get("likes", 0),
                "trendingScore": model.get("trendingScore", 0),
                "task": model.get("pipeline_tag"),
            },
        )
        for model in data
        if model.get("id")
    ]


@register
class HuggingFacePapersCollector(Collector):
    type = "huggingFacePapers"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        params = {"limit": self.source.opt("limit", 50)}
        resp = await fetch(client, envUrl("HF_DAILY_PAPERS_API_URL"), params=params)
        return parseDailyPapers(resp.json(), self.source.opt("minUpvotes", 10), self)


@register
class HuggingFaceTrendingModelsCollector(Collector):
    type = "huggingFaceTrendingModels"

    async def collect(self, client: httpx.AsyncClient, since: datetime) -> list[RawItem]:
        params = {"sort": "trendingScore", "limit": self.source.opt("limit", 10)}
        resp = await fetch(client, envUrl("HF_TRENDING_MODELS_API_URL"), params=params)
        return parseTrendingModels(resp.json(), self)
