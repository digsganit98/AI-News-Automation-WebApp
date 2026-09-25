"""Counts what the grounding checks removed during a run.

Every time a model writes a link or a source that wasn't in the collected data, the code
removes it and counts it here. The totals go to the run summary and to Langfuse: a live
signal of how often the models tried to make something up.
"""

from __future__ import annotations

from collections import Counter

groundingStats: Counter[str] = Counter()

LABELS = {
    "scoutNotesDropped": "scout notes pointing at uncollected pages",
    "scoutLinksRemoved": "invented 'go deeper' links (scouts)",
    "analystRefsInvalid": "citations of notes that don't exist (analyst)",
    "analystStoriesDropped": "stories with no real source (analyst)",
}


def resetGroundingStats() -> None:
    groundingStats.clear()


def totalCatches() -> int:
    return sum(groundingStats.values())
