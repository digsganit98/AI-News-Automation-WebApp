"""The YouTube title filter keeps news videos and drops tutorials.

Uses the real filter from config/sources.yaml and Krish Naik's real upload titles
(English + Hindi channels, September 2026).
"""

from __future__ import annotations

import pytest

from digest.processing.titleFilter import keepTitle
from digest.sourcesConfig import loadConfig

NEWS_VIDEOS = [
    "Will BDH replace Transformers? Post-Transformer AI Explained for Everyone",
    "Will Jev Replace LLM's? What is Jev From TypeSafe AI",
    "Traditional SDLC Is Changing: Welcome to Vibe Coding & Agentic Engineering",
]

TUTORIALS = [
    "Live Marathon- FDE Project Live Implementation",
    "Fine-Tune, Deploy & Serve Open LLMs with Crusoe Intelligence Foundry",
    "AI Forward Deployed Engineer(FDE) Bootcamp",
    "Complete End To End AI Forward Deployed Engineer(FDE) Project Implementation",
    "Build a Complete AI SaaS Application with Lovable",
    "Complete AI Forward Deployed Engineer(FDE) Roadmap With Usecases",
    "3.0 Ultimate AI Engineering Bootcamp Induction Session",
    "Build Production-Grade AI Agents with the Gemini Enterprise Agent Platform",
    "Complete Claude Ecosystem - AI, Code, Cowork, M365 & Certification Udemy Course",
    "Complete AI LLM Gateway Crash Course With Mesh API",
    "AI Engineering Vs AI Forward Deployed Engineer(FDE)",
    "Loop Engineering And Harness Engineering Crash Course",
    "Building Memory In AI Agents Using Mem0 Crash Course- Krish Naik Hindi",
    "Building AI Agents With Pydantic AI Crash Course-Krish Naik Hindi",
    "Retrieval Augmented Generation(RAG) LangGraph Crash Course In Hindi",
    "I built My Own Private AI Assistant",
    "Generative AI Crash course With Langchain in 3 hours- Krish Naik Hindi",
    "7-Introduction To RAG(Retrieval-Augmented Generation?) In Hindi",
    "6-Tools With Langchain-Integrate LLM with Tools",
    "5-End To End Conversational Q&A Assistant With Memory Using Langchain",
    "4-Getting Started With Langchain- LLM calls,Streaming, Prompt Template, Build Chains",
    "3-Langchain Project Set Up With UV Package Manager In Hindi",
    "2-Introduction To Langchain And LangGraph- Why to Learn?",
    "1-Roadmap To Learn Generative AI And Agentic AI In Hindi",
    "#1-New Series Building Generative AI App With HuggingFace Open Source Models With Langchain",
    "Turn Your Computer Into Gen AI Computer- Krish Naik Hindi",
    "Run Pandas Library 50x Time Faster on Google Colab Using Rapids cuDF - Krish Naik Hindi",
]


@pytest.fixture(scope="module")
def krishNaikFilter() -> dict:
    source = next(s for s in loadConfig().sources if s.id == "krish-naik")
    return source.opt("titleFilter")


@pytest.mark.parametrize("title", NEWS_VIDEOS)
def testNewsVideosAreKept(krishNaikFilter, title):
    assert keepTitle(title, krishNaikFilter["include"], krishNaikFilter["exclude"])


@pytest.mark.parametrize("title", TUTORIALS)
def testTutorialsAreDropped(krishNaikFilter, title):
    assert not keepTitle(title, krishNaikFilter["include"], krishNaikFilter["exclude"])


def testHindiChannelUsesTheSameFilter(krishNaikFilter):
    hindi = next(s for s in loadConfig().sources if s.id == "krish-naik-hindi")
    assert hindi.opt("titleFilter") == krishNaikFilter


def testNoFilterKeepsEverything():
    assert keepTitle("Anything at all", None, None)
