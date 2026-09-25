"""Running `digest collect` on two days in a row must not save the same story twice."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from digest import cli
from digest.dataModels import CollectionResult, RawItem, SourceHealth


def fakeCollection(*urls: str) -> CollectionResult:
    now = datetime.now(UTC)
    return CollectionResult(
        runAt=now,
        items=[
            RawItem(source="s", sourceName="S", title=f"Story {u}", url=u, publishedAt=now)
            for u in urls
        ],
        health=[SourceHealth(source="s", sourceName="S", ok=True, items=len(urls), checkedAt=now)],
    )


def runCollect(monkeypatch, tmp_path, collection: CollectionResult) -> list[str]:
    async def fakeCollectSources(config, hours=None):
        return collection.model_copy(deep=True)

    monkeypatch.setattr(cli, "collectSources", fakeCollectSources)
    monkeypatch.setattr(cli, "SEEN_FILE", tmp_path / "state" / "seen.json")
    outDir = tmp_path / "raw"
    assert cli.main(["collect", "--out", str(outDir)]) == 0
    [saved] = outDir.glob("*.json")
    urls = [i["url"] for i in json.loads(saved.read_text(encoding="utf-8"))["items"]]
    saved.unlink()
    return urls


def testSecondDayOnlySavesNewStories(monkeypatch, tmp_path):
    day1 = runCollect(monkeypatch, tmp_path, fakeCollection("https://a.test/1", "https://a.test/2"))
    # Day 2's 36-hour window still contains story 2, plus a new story 3.
    day2 = runCollect(monkeypatch, tmp_path, fakeCollection("https://a.test/2", "https://a.test/3"))

    assert day1 == ["https://a.test/1", "https://a.test/2"]
    assert day2 == ["https://a.test/3"]


def testNoMarkSeenLeavesStateUntouched(monkeypatch, tmp_path):
    async def fakeCollectSources(config, hours=None):
        return fakeCollection("https://a.test/1")

    seenFile = tmp_path / "state" / "seen.json"
    monkeypatch.setattr(cli, "collectSources", fakeCollectSources)
    monkeypatch.setattr(cli, "SEEN_FILE", seenFile)
    assert cli.main(["collect", "--out", str(tmp_path / "raw"), "--no-mark-seen"]) == 0
    assert not seenFile.exists()


def testRunsOnTheSameDayAddToOneFile(monkeypatch, tmp_path):
    """Every-3-hours runs: one file per day that grows, with each run recorded."""
    monkeypatch.setattr(cli, "SEEN_FILE", tmp_path / "state" / "seen.json")
    outDir = tmp_path / "raw"
    for urls in (
        ("https://a.test/1", "https://a.test/2"),
        ("https://a.test/2", "https://a.test/3"),
    ):

        async def fakeCollectSources(config, hours=None, urls=urls):
            return fakeCollection(*urls)

        monkeypatch.setattr(cli, "collectSources", fakeCollectSources)
        assert cli.main(["collect", "--out", str(outDir)]) == 0

    [dayFile] = outDir.glob("*.json")
    data = json.loads(dayFile.read_text(encoding="utf-8"))
    assert [i["url"] for i in data["items"]] == [
        "https://a.test/1",
        "https://a.test/2",
        "https://a.test/3",
    ]
    assert [run["newItems"] for run in data["runs"]] == [2, 1]
    assert all("collectedAt" in i for i in data["items"])
