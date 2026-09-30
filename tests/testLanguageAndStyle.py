"""English only, and AI-written text in house style (no long dashes, no empty bullets)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import makeTakes

from digest.agents.agentModels import DigestDraft
from digest.dataModels import RawItem
from digest.processing.languageFilter import isEnglish, keepEnglish
from digest.processing.textStyle import tidyLines, tidyOutcome, tidyText


@pytest.mark.parametrize(
    "text",
    [
        "De la Lógica Tradicional a la AGI: Las 7 Capas de la Inteligencia Artificial",
        "LLM’e ne kadar güvenebiliriz? Generative AI Sadece İçerik Üretmiyor",
        "Qwen-Audio-3.1-Realtime — 에이전틱 실시간 음성 상호작용의 신뢰성 확보",
        "जनरेटिव एआई क्या है और यह कैसे काम करता है",
        "Die Zukunft der KI: Warum das neue Modell für Unternehmen wichtig ist und sich lohnt",
        "Comment l'IA générative change le travail des développeurs dans les entreprises",
    ],
)
def testOtherLanguagesAreDetected(text):
    assert not isEnglish(text)


@pytest.mark.parametrize(
    "text",
    [
        "Papaya: Continuous optimization for AI agents | Y Combinator",
        "Qwen3.8-27B",
        "OpenAI releases a new reasoning model for coding agents",
        "Café-scale inference: running Llama on a laptop",
        "Tokens per second doubled with speculative decoding, et al. report",
    ],
)
def testEnglishIsKept(text):
    assert isEnglish(text)


def testNonEnglishItemsAreDropped():
    items = [
        RawItem(
            source="m",
            sourceName="Medium",
            title="Las 7 Capas de la IA",
            excerpt="La evolución de la Inteligencia Artificial no ocurrió de la noche a la mañana",
            url="https://a.test/1",
        ),
        RawItem(
            source="m", sourceName="Medium", title="The 7 layers of AI", url="https://a.test/2"
        ),
    ]
    assert [i.title for i in keepEnglish(items)] == ["The 7 layers of AI"]


@pytest.mark.parametrize(
    ("raw", "tidy"),
    [
        (
            "The cost of retrofitting safety after a breach—both financially and "
            "reputationally—far outweighs the overhead.",
            "The cost of retrofitting safety after a breach, both financially and "
            "reputationally, far outweighs the overhead.",
        ),
        ("Agents are fast — but risky.", "Agents are fast, but risky."),
        ("It ends here —.", "It ends here."),
        ("GPT‑6 scored 62– 70 on pages 10–12", "GPT-6 scored 62, 70 on pages 10-12"),
        ("A clean sentence.", "A clean sentence."),
    ],
)
def testLongDashesBecomeProperPunctuation(raw, tidy):
    assert tidyText(raw) == tidy


def testEmptyBulletsAndParagraphsAreRemoved():
    lines = ["First point.", "", "   ", "Second point."]
    assert tidyLines(lines) == ["First point.", "Second point."]


def testEverythingTheAgentsWroteIsTidied():
    edition = SimpleNamespace(
        digest=DigestDraft(headline="A—B", dek="D", tldr=["One—two.", " "], intro="I"),
        takes=makeTakes("Agents are fast—but risky."),
        stories=[],
    )
    outcome = SimpleNamespace(stories=[], edition=edition)
    tidyOutcome(outcome)
    assert edition.digest.headline == "A, B"
    assert edition.digest.tldr == ["One, two."]
    assert edition.takes.takes[0].take == "Agents are fast, but risky."


def testPlainCapitalLettersAreNeverForeign():
    """Regression: "ı".upper() is "I" and "ß".upper() is "SS"; plain English must pass."""
    assert isEnglish("SIGGRAPH: IS IT TIME FOR AI SYSTEMS TO SHIP? SPEED IS STILL KEY")
