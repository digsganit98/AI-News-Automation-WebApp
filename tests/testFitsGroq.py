"""The writer and editor trim their requests so Groq (8k tokens/minute) can always take over
when Gemini is busy: no request is ever "too large" for any model in the chain."""

from __future__ import annotations

from datetime import UTC, datetime

from digest.agents.agentModels import DigestDraft, EditorIssue, EditorReview, OpEdDraft, Story
from digest.agents.agentsConfig import loadAgentsConfig
from digest.agents.llmBudget import LlmBudget
from digest.agents.llmRouter import LlmRouter, estimateTokens
from digest.agents.writerAgent import fitOriginals, writeEdition

GROQ_PER_MINUTE = 8000
LONG = "A detailed sentence about a new model, its benchmarks and what it costs. " * 40


class RecordingRouter(LlmRouter):
    """Answers with canned drafts and records each request's size as Groq would count it."""

    sizes: list[tuple[str, int]]

    async def structured(self, agent, schema, system, user, maxOutput=None):
        prompt = f"{user}\n\nReply with only a JSON object shaped like this:\n"
        needed = estimateTokens(system, prompt) + (maxOutput or self.maxOutput(agent)) + 100
        self.sizes.append((agent, needed))
        ids = [f"s{n}" for n in range(5)]
        if schema is DigestDraft:
            return DigestDraft(headline="H", dek="D", tldr=["t"], intro="I", topStoryIds=ids)
        if schema is OpEdDraft:
            return OpEdDraft(title="T", dek="D", paragraphs=[LONG[:900]] * 5, basedOnStoryIds=ids)
        issues = [EditorIssue(where=w, problem="p", fix="f") for w in ("digest", "opEd")]
        return EditorReview(approved=False, issues=issues)


def story(n: int) -> Story:
    return Story(
        id=f"s{n}",
        createdAt=datetime.now(UTC).isoformat(),
        headline=f"Headline number {n} about a big launch",
        summary=LONG[:600],
        whyItMatters=LONG[:250],
        category="New Model Release",
        importance=5 - n % 5,
        sources=[{"name": "Lab", "url": f"https://lab.test/{n}"}],
    )


async def testEveryWriterAndEditorRequestFitsGroq(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    config = loadAgentsConfig()
    router = RecordingRouter(config, LlmBudget(config.budget, "dailyEdition", tmp_path / "u.json"))
    router.sizes = []

    async def longArticle(url: str) -> dict:
        return {"text": LONG * 3}

    stories = [story(n) for n in range(config.budget.maxStoriesForWriter)]
    edition = await writeEdition(stories, router, longArticle)

    agents = [agent for agent, _ in router.sizes]
    assert agents == ["writer", "writer", "editor", "writer", "writer"]  # incl. both revisions
    for agent, needed in router.sizes:
        assert needed <= GROQ_PER_MINUTE, f"{agent} request needs {needed} tokens"
    assert edition.originalsChecked >= 1  # trimmed, not thrown away


def testOriginalsAreShortenedBeforeAnyIsDropped():
    originals = [{"storyId": f"s{n}", "url": "u", "text": "x" * 1200} for n in range(6)]
    roomy = fitOriginals(originals, 100_000)
    assert [len(o["text"]) for o in roomy] == [1200] * 6

    tight = fitOriginals(originals, 1200)
    assert len(tight) == 6 and all(len(o["text"]) < 1200 for o in tight)

    tiny = fitOriginals(originals, 300)
    assert 0 < len(tiny) < 6  # even short excerpts don't fit: the last ones go


def testNoLimitMeansNoTrimming(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    config = loadAgentsConfig()
    router = LlmRouter(config, LlmBudget(config.budget, "dailyEdition", tmp_path / "u.json"))
    assert router.inputBudget("editor", "system", EditorReview) is None  # Gemini only
