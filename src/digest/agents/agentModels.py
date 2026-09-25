"""Shapes of what each agent returns. Every LLM answer is validated against these."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# "Tech Domain" in the research log.
Category = Literal[
    "New Model Release",
    "Framework/Tooling",
    "Agentic Systems",
    "Methodology",
    "Industry Use Case",
    "Infrastructure/MLOps",
    "Research",
    "AGI",
    "Policy & Safety",
    "Business & Funding",
]
SourceType = Literal["Directed", "Emergent", "AI-assisted"]
CATEGORIES: list[str] = list(Category.__args__)  # type: ignore[attr-defined]


class GoDeeper(BaseModel):
    """Follow-up links: the paper, the code, the model card, a demo."""

    paper: str | None = None
    code: str | None = None
    model: str | None = None
    demo: str | None = None


# ---------------------------------------------------------------- scouts
# The LLM refers to items by short refs ("i1", "i2"...) and never writes their URLs:
# code maps refs back to the collected items. Fewer tokens, and no invented links.


class ScoutTriage(BaseModel):
    """Scout step 1 (LLM): which items are real GenAI news, and which to read in full."""

    keepRefs: list[str] = Field(default_factory=list)
    readInFullRefs: list[str] = Field(default_factory=list)


class ScoutNoteDraft(BaseModel):
    """Scout step 2 (LLM): one note per kept item."""

    ref: str | None = None  # the item's ref; null for a story pulled out of a newsletter
    url: str | None = None  # only for newsletter stories: the link from the newsletter
    title: str
    summary: str  # 1-2 plain sentences
    goDeeper: GoDeeper = Field(default_factory=GoDeeper)


class ScoutBrief(BaseModel):
    notes: list[ScoutNoteDraft] = Field(default_factory=list)


class ScoutNote(BaseModel):
    """A grounded note (built by code): always points at a collected page."""

    itemId: str | None = None
    title: str
    url: str
    summary: str
    goDeeper: GoDeeper = Field(default_factory=GoDeeper)


class ScoutReport(BaseModel):
    notes: list[ScoutNote] = Field(default_factory=list)


# ---------------------------------------------------------------- analyst


class StorySource(BaseModel):
    name: str
    url: str


class AnalystStoryDraft(BaseModel):
    """A story as the analyst (LLM) writes it: it cites notes by number, not by URL."""

    headline: str
    summary: str  # 2 sentences, plain language
    whyItMatters: str = ""  # 1 sentence for non-experts
    category: Category
    importance: int = Field(ge=1, le=5)
    status: Literal["new", "followUp", "alreadyCovered"] = "new"
    followUpOf: str | None = None  # storyId of the earlier story, for follow-ups
    cloudPlatform: str = "Cross-cloud"  # e.g. AWS, Azure, GCP, OpenAI, Anthropic, Open-source
    industryVertical: str = "Cross-industry"  # e.g. BFSI, Healthcare, Retail, Manufacturing
    researcher: str | None = None  # a named original author, only if the notes clearly name one
    noteRefs: list[int] = Field(default_factory=list)  # numbers of the notes it's based on


class AnalystReport(BaseModel):
    stories: list[AnalystStoryDraft] = Field(default_factory=list)


class Story(BaseModel):
    """A story as saved to data/stories/<date>.json (sources and links added by code)."""

    id: str
    createdAt: str
    headline: str
    summary: str
    whyItMatters: str = ""
    category: Category
    importance: int = Field(ge=1, le=5)
    status: Literal["new", "followUp", "alreadyCovered"] = "new"
    followUpOf: str | None = None
    cloudPlatform: str = "Cross-cloud"
    industryVertical: str = "Cross-industry"
    researcher: str = ""
    sourceType: SourceType = "Directed"  # set by code from the sources' groups
    sources: list[StorySource]
    goDeeper: GoDeeper = Field(default_factory=GoDeeper)


# ---------------------------------------------------------------- writer + editor


class DigestDraft(BaseModel):
    headline: str
    dek: str  # one-line subtitle
    tldr: list[str] = Field(min_length=1, max_length=5)
    intro: str  # 2-3 sentences setting up the day
    topStoryIds: list[str] = Field(default_factory=list, max_length=5)


class OpEdDraft(BaseModel):
    title: str
    dek: str
    paragraphs: list[str] = Field(min_length=3)
    basedOnStoryIds: list[str] = Field(default_factory=list)


class EditorIssue(BaseModel):
    where: Literal["digest", "opEd"]
    problem: str
    fix: str


class EditorReview(BaseModel):
    approved: bool
    issues: list[EditorIssue] = Field(default_factory=list)
