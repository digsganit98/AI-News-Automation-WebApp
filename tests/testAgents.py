"""The AI agents, with a fake LLM: no API keys, no cost, no network."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from digest.agents import runAgents as runAgentsModule
from digest.agents.agentModels import (
    AnalystReport,
    DigestDraft,
    EditorReview,
    OpEdDraft,
    ScoutBrief,
    ScoutTriage,
    Story,
)
from digest.agents.agentsConfig import Budget, loadAgentsConfig
from digest.agents.llmBudget import LlmBudget
from digest.agents.llmRouter import LlmRouter, LlmUnavailableError
from digest.agents.runAgents import runAgents
from digest.agents.scoutAgent import runScout
from digest.dataModels import RawItem
from digest.publish.saveStories import saveEdition, saveStories

NOW = datetime.now(UTC)


def item(itemId: str, source: str, title: str, url: str, **extra) -> RawItem:
    raw = RawItem(
        source=source, sourceName=source.title(), title=title, url=url, publishedAt=NOW, extra=extra
    )
    # RawItem.id comes from the URL; tests refer to items by that id.
    assert raw.id
    return raw


class FakeRouter:
    """Stands in for LlmRouter: answers each (agent, schema) from a script."""

    def __init__(self, answers: dict):
        self.answers = answers  # schema class -> answer, or list of answers (consumed in order)
        self.asked: list[tuple[str, str, str]] = []
        self.calls: list = []
        self.budget = type("NoBudget", (), {"save": lambda self: None})()

    def isAvailable(self) -> bool:
        return True

    def inputBudget(self, agent, system, schema, maxOutput=None):
        return None  # no per-minute limit: nothing is trimmed (see testFitsGroq)

    async def structured(self, agent, schema, system, user, maxOutput=None):
        self.asked.append((agent, schema.__name__, user))
        answer = self.answers[schema]
        if isinstance(answer, list):
            answer = answer.pop(0)
        return answer(user) if callable(answer) else answer


# ------------------------------------------------------------------ scout


async def testScoutReadsChosenArticlesAndDropsInventedLinks():
    launch = item("a", "openai", "GPT-6 launches", "https://openai.com/gpt-6")
    tutorial = item("b", "openai", "Build an app in 5 minutes", "https://openai.com/tutorial")
    fetched: list[str] = []

    async def fetchArticle(url: str) -> dict:
        fetched.append(url)
        return {"text": "Full text. Paper at https://arxiv.org/abs/2609.1 and more."}

    router = FakeRouter(
        {
            # items are shown to the LLM as refs: i1 = launch, i2 = tutorial
            ScoutTriage: ScoutTriage(keepRefs=["i1"], readInFullRefs=["i1"]),
            ScoutBrief: ScoutBrief.model_validate(
                {
                    "notes": [
                        {
                            "ref": "i1",
                            "title": "GPT-6 launches",
                            "url": "https://wrong.example/x",
                            "summary": "OpenAI released GPT-6.",
                            "goDeeper": {
                                "paper": "https://arxiv.org/abs/2609.1",
                                "code": "https://github.com/made/up",
                            },
                        },
                        {
                            "ref": None,
                            "title": "Invented story",
                            "url": "https://not-collected.example",
                            "summary": "Nope.",
                        },
                    ]
                }
            ),
        }
    )
    spec = loadAgentsConfig().scouts["labsResearch"]
    report = await runScout(spec, [launch, tutorial], router, fetchArticle, Budget())

    assert fetched == ["https://openai.com/gpt-6"]  # the agent's choice, fetched via the tool
    [note] = report.notes  # the invented story is dropped
    assert note.url == "https://openai.com/gpt-6"  # corrected to the collected URL
    assert note.goDeeper.paper == "https://arxiv.org/abs/2609.1"  # present in the article text
    assert note.goDeeper.code is None  # invented link removed
    assert "<untrusted_data" in router.asked[0][2]  # scraped content is fenced off


async def testScoutWithNothingNewMakesNoCalls():
    router = FakeRouter({})
    spec = loadAgentsConfig().scouts["x"]
    report = await runScout(spec, [], router, lambda url: None, Budget())
    assert report.notes == [] and router.asked == []


# ------------------------------------------------------------------ full graph


def analystAnswer(user: str) -> AnalystReport:
    return AnalystReport.model_validate(
        {
            "stories": [
                {
                    "headline": "OpenAI launches GPT-6",
                    "summary": "A new model. It is faster.",
                    "whyItMatters": "Cheaper AI for everyone.",
                    "category": "New Model Release",
                    "importance": 5,
                    "noteRefs": [1, 2],  # both notes: the launch post and the HN thread
                },
                {
                    "headline": "Old news again",
                    "summary": "Seen before.",
                    "category": "Research",
                    "importance": 3,
                    "status": "alreadyCovered",
                    "noteRefs": [1],
                },
                {
                    "headline": "Made-up story",
                    "summary": "No real source.",
                    "category": "Research",
                    "importance": 4,
                    "noteRefs": [99],  # a note that doesn't exist
                },
            ]
        }
    )


def scoutNotes(user: str) -> ScoutBrief:
    data = json.loads(user.split("\n", 1)[1].rsplit("\n", 1)[0])
    return ScoutBrief.model_validate(
        {"notes": [{"ref": d["ref"], "title": d["title"], "summary": "Summary."} for d in data]}
    )


def triageKeepAll(user: str) -> ScoutTriage:
    data = json.loads(user.split("\n", 1)[1].rsplit("\n", 1)[0])
    return ScoutTriage(keepRefs=[d["ref"] for d in data])


@pytest.fixture
def noSavedStories(monkeypatch):
    monkeypatch.setattr(runAgentsModule, "loadRecentStories", lambda days: [])
    monkeypatch.setattr(runAgentsModule, "storiesForEdition", lambda: [])


async def testUpdateRunProducesGroundedStoriesOnly(noSavedStories):
    items = [
        item("a", "openai", "GPT-6 launches", "https://openai.com/gpt-6"),
        item(
            "b", "hackernews", "GPT-6 is out (discussion)", "https://news.ycombinator.com/item?id=1"
        ),
    ]
    router = FakeRouter(
        {ScoutTriage: triageKeepAll, ScoutBrief: scoutNotes, AnalystReport: analystAnswer}
    )
    result = await runAgents(items, "update", router=router, fetchArticle=lambda url: None)

    assert result.ran and result.edition is None  # no writer outside the 09:30 edition
    assert [s.headline for s in result.stories] == ["OpenAI launches GPT-6"]
    assert len(result.stories[0].sources) == 2  # one story, both sources
    scoutsAsked = [a for a in router.asked if a[1] == "ScoutTriage"]
    assert len(scoutsAsked) == 2  # labs + community scouts; video and X had nothing


async def testDailyEditionWritesDigestAndRevisesOnce(noSavedStories):
    items = [item("a", "openai", "GPT-6 launches", "https://openai.com/gpt-6")]
    digest = DigestDraft(
        headline="GPT-6 arrives",
        dek="A big day.",
        tldr=["GPT-6 is out."],
        intro="Today OpenAI...",
        topStoryIds=["does-not-exist"],
    )
    opEd = OpEdDraft(
        title="Why GPT-6 matters", dek="An opinion.", paragraphs=["One.", "Two.", "Three."]
    )
    fixedDigest = digest.model_copy(update={"headline": "OpenAI releases GPT-6"})
    router = FakeRouter(
        {
            ScoutTriage: triageKeepAll,
            ScoutBrief: scoutNotes,
            AnalystReport: analystAnswer,
            DigestDraft: [digest, fixedDigest],
            OpEdDraft: opEd,
            EditorReview: EditorReview.model_validate(
                {
                    "approved": False,
                    "issues": [{"where": "digest", "problem": "Hype.", "fix": "Be factual."}],
                }
            ),
        }
    )

    async def fetchOriginal(url: str) -> dict:
        return {"text": "ORIGINAL ARTICLE: GPT-6 ships in three sizes."}

    result = await runAgents(items, "dailyEdition", router=router, fetchArticle=fetchOriginal)

    edition = result.edition
    assert edition is not None and edition.revised
    assert edition.digest.headline == "OpenAI releases GPT-6"
    assert edition.digest.topStoryIds == [result.stories[0].id]  # unknown id replaced
    # only the flagged piece (the digest) is revised, once; the op-ed is left alone
    assert [a[1] for a in router.asked].count("DigestDraft") == 2
    assert [a[1] for a in router.asked].count("OpEdDraft") == 1
    editorPrompt = next(a[2] for a in router.asked if a[1] == "EditorReview")
    assert "original articles" in editorPrompt  # the editor checks the source, not a summary
    assert "GPT-6 ships in three sizes" in editorPrompt
    assert edition.originalsChecked == 1


async def testNoApiKeysSkipsAgents(monkeypatch):
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(key, "")
    result = await runAgents([], "update")
    assert not result.ran and "API keys" in result.skippedReason


# ------------------------------------------------------------------ router + budget


class FakeChat:
    """Stands in for ChatOpenAI: returns a message whose content is JSON (or raises)."""

    def __init__(self, outcome):
        self.outcome = outcome

    def bind(self, **kwargs):
        return self

    async def ainvoke(self, messages):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        outcome = self.outcome
        content = outcome if isinstance(outcome, str) else outcome.model_dump_json()
        usage = {"input_tokens": 100, "output_tokens": 20}
        return type("Msg", (), {"content": content, "usage_metadata": usage})()


def makeRouter(monkeypatch, tmp_path, outcomes: dict[str, object], mode="update", cap=100):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    config = loadAgentsConfig()
    config.budget.dailyCallCap = cap
    for provider in config.providers.values():
        provider.tokensPerMinute = None  # no pacing waits in tests
    router = LlmRouter(config, LlmBudget(config.budget, mode, tmp_path / "llmUsage.json"))
    monkeypatch.setattr(
        router, "_chat", lambda agent, choice, maxOutput=None: FakeChat(outcomes[choice.model])
    )
    return router


async def testRouterFallsBackToTheNextModel(monkeypatch, tmp_path):
    triage = ScoutTriage(keepRefs=["i1"])
    router = makeRouter(
        monkeypatch,
        tmp_path,
        {
            "qwen/qwen3.8-27b": RuntimeError("429 rate limited"),
            "gemini-3.5-flash-lite": triage,
        },
    )
    assert await router.structured("scout", ScoutTriage, "sys", "user") == triage
    assert [(c.model, c.ok) for c in router.calls] == [
        ("groq/qwen/qwen3.8-27b", False),
        ("gemini/gemini-3.5-flash-lite", True),
    ]
    assert router.budget.usage["calls"] == 1  # the failed request never reached a model


async def testBudgetKeepsCallsForTheDailyEdition(monkeypatch, tmp_path):
    # cap 30, reserve 25: 3-hourly updates may use only 5 calls
    router = makeRouter(monkeypatch, tmp_path, {"qwen/qwen3.8-27b": ScoutTriage()}, cap=30)
    for _ in range(5):
        await router.structured("scout", ScoutTriage, "s", "u")
    with pytest.raises(LlmUnavailableError, match="budget"):
        await router.structured("scout", ScoutTriage, "s", "u")
    router.budget.save()

    edition = makeRouter(
        monkeypatch,
        tmp_path,
        {"openai/gpt-oss-120b": EditorReview(approved=True)},
        mode="dailyEdition",
        cap=30,
    )
    assert edition.budget.remaining() == 25  # the reserve is still there at 09:30


# ------------------------------------------------------------------ saving


def testStoriesAndEditionAreSaved(tmp_path):
    story = Story(
        id="gpt-6-abc123",
        createdAt=NOW.isoformat(),
        headline="GPT-6",
        summary="S.",
        category="New Model Release",
        importance=5,
        sources=[{"name": "OpenAI", "url": "https://openai.com/gpt-6"}],
    )
    path = saveStories([story, story], tmp_path / "stories")
    assert len(json.loads(path.read_text(encoding="utf-8"))["stories"]) == 1  # no duplicates

    from digest.agents.writerAgent import Edition

    edition = Edition(
        DigestDraft(headline="H", dek="D", tldr=["T"], intro="I", topStoryIds=[story.id]),
        OpEdDraft(title="T", dek="D", paragraphs=["1", "2", "3"], basedOnStoryIds=[story.id]),
        EditorReview(approved=True),
        False,
        [story],
    )
    saved = json.loads(
        saveEdition(edition, {"gemini/gemini-3.8-flash": 2}, tmp_path / "digests").read_text(
            encoding="utf-8"
        )
    )
    assert saved["digest"]["headline"] == "H" and saved["stories"][story.id]["importance"] == 5
    assert saved["editor"] == {
        "approved": True,
        "issuesFound": 0,
        "revised": False,
        "originalsChecked": 0,
    }


async def testPacerWaitsWhenTheMinuteIsFull(monkeypatch):
    from digest.agents import llmRouter

    slept: list[float] = []

    async def fakeSleep(seconds):
        slept.append(seconds)
        pacer.windows["m"].clear()  # pretend the minute has passed

    monkeypatch.setattr(llmRouter.asyncio, "sleep", fakeSleep)
    pacer = llmRouter.TokenPacer()
    await pacer.reserve("m", 6000, 8000)
    await pacer.reserve("m", 6000, 8000)  # would exceed 8,000 in the same minute
    assert len(slept) == 1


def testRetryAfterIsReadFromTheErrorMessage():
    from digest.agents.llmRouter import retryAfterSeconds

    assert retryAfterSeconds(RuntimeError("Please try again in 16.7775s. Need more")) == 16.7775
    assert retryAfterSeconds(RuntimeError("try again in 850ms")) == 0.85
    assert retryAfterSeconds(RuntimeError("quota exceeded")) is None


def testParserForgivesFencesAndBareListsButStillValidates():
    from digest.agents.llmRouter import parseAnswer

    note = {"ref": "i1", "title": "T", "url": "https://x.test", "summary": "S."}
    fenced = "```json\n" + json.dumps({"notes": [note]}) + "\n```"
    assert parseAnswer(fenced, ScoutBrief)[0].notes[0].title == "T"
    assert parseAnswer(json.dumps([note]), ScoutBrief)[0].notes[0].url == "https://x.test"
    bad, reason = parseAnswer(json.dumps([{"title": "no summary"}]), ScoutBrief)
    assert bad is None and "schema" in reason  # missing fields are still rejected
    assert parseAnswer("not json at all", ScoutBrief)[0] is None


async def testUnusableAnswerFallsBackToTheNextModel(monkeypatch, tmp_path):
    router = makeRouter(
        monkeypatch,
        tmp_path,
        {
            "qwen/qwen3.8-27b": "Sorry, here you go: {oops",
            "gemini-3.5-flash-lite": ScoutTriage(keepRefs=["i2"]),
        },
    )
    assert (await router.structured("scout", ScoutTriage, "s", "u")).keepRefs == ["i2"]
    assert [c.error for c in router.calls] == ["invalid JSON", ""]


def testMonitoringIsOffInTests():
    from digest.monitoring.langfuseTracing import isEnabled

    assert not isEnabled()


def testGroundingCatchesAreCounted():
    from digest.agents.groundingStats import groundingStats, resetGroundingStats, totalCatches

    resetGroundingStats()
    groundingStats["scoutLinksRemoved"] += 2
    assert totalCatches() == 2
    resetGroundingStats()
    assert totalCatches() == 0
