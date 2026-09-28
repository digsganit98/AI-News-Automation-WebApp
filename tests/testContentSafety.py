"""Content policy: explicit, hateful, anti-religious and violent content never gets through."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from digest.agents.agentModels import DigestDraft, OpEdDraft, Story
from digest.agents.promptKit import PROMPT_DIR, loadPrompt
from digest.dataModels import RawItem
from digest.processing.contentSafety import blockedPattern, dropBlocked, guardOutput, isBlocked
from digest.sourcesConfig import loadConfig

POLICY = blockedPattern(loadConfig().settings.blockedTerms)


@pytest.mark.parametrize(
    "text",
    [
        "AI Sex Chat Apps 2026: A Consumer Report",
        "New nudify app raises alarm",
        "Best AI girlfriend apps ranked",
        "Racist chatbot goes viral",
        "Misogynistic comments by CEO",
        "Anti-Muslim posts flood platform",
        "Anti-Hindu content spreads",
        "Terrorist group uses AI",
        "Mass shooting suspect's manifesto",
        "Chatbot linked to suicide",
    ],
)
def testBlockedContentIsCaught(text):
    assert isBlocked(text, POLICY)


@pytest.mark.parametrize(
    "text",
    [
        "OpenAI releases a new reasoning model",
        "AWS Bedrock adds agent memory",
        "Sussex University opens an AI lab",  # "sex" only as a whole word
        "Essex council pilots AI assistants",
        "Researchers publish a new benchmark for coding agents",
    ],
)
def testNormalAiNewsIsKept(text):
    assert not isBlocked(text, POLICY)


def testBlockedItemsAreDroppedFromAnySource():
    items = [
        RawItem(
            source="web-search", sourceName="Web", title="AI Sex Chat Apps", url="https://a.test/1"
        ),
        RawItem(
            source="openai", sourceName="OpenAI", title="GPT-7 is here", url="https://a.test/2"
        ),
        RawItem(
            source="hackernews",
            sourceName="HN",
            title="A quiet post",
            excerpt="Contains anti-religious rants",
            url="https://a.test/3",
        ),
    ]
    assert [i.title for i in dropBlocked(items, POLICY)] == ["GPT-7 is here"]


def story(sid: str, headline: str) -> Story:
    return Story(
        id=sid,
        createdAt=datetime.now(UTC).isoformat(),
        headline=headline,
        summary="S.",
        category="Research",
        importance=3,
        sources=[{"name": "x", "url": f"https://a.test/{sid}"}],
    )


def edition(opEdParagraph: str):
    return SimpleNamespace(
        digest=DigestDraft(headline="H", dek="D", tldr=["t"], intro="I"),
        opEd=OpEdDraft(title="T", dek="D", paragraphs=["a", "b", opEdParagraph]),
        stories=[story("ok", "A new open model")],
    )


def testWhatTheAiWroteIsCheckedBeforeSaving():
    outcome = SimpleNamespace(
        stories=[story("ok", "A new open model"), story("bad", "Explicit images spread online")],
        edition=edition("A calm, constructive paragraph."),
    )
    removed = guardOutput(outcome, POLICY)
    assert [s.id for s in outcome.stories] == ["ok"]
    assert outcome.edition is not None and removed == ["Explicit images spread online"]


def testAnEditionThatBreaksThePolicyIsWithheld():
    outcome = SimpleNamespace(stories=[], edition=edition("This glorifies a massacre."))
    guardOutput(outcome, POLICY)
    assert outcome.edition is None


def testEveryAgentPromptCarriesTheContentPolicy():
    names = [p.stem for p in PROMPT_DIR.glob("*.md") if p.stem != "contentPolicy"]
    assert names
    for name in names:
        try:
            text = loadPrompt(name)
        except KeyError:  # prompts with {placeholders}
            text = loadPrompt(name, scoutName="S", maxArticles=3, categories="A")
        assert "Content policy" in text, name
