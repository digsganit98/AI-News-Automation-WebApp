"""Loads prompt files and wraps scraped content so agents treat it as data, not instructions."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"


@cache
def _read(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def loadPrompt(name: str, **values: object) -> str:
    """Read prompts/<name>.md and fill its {placeholders}."""
    text = _read(name)
    return text.format(**values) if values else text


def untrusted(data: object, label: str = "items") -> str:
    """Scraped web content, clearly fenced off from the instructions."""
    body = json.dumps(data, ensure_ascii=False, indent=1)
    return f'<untrusted_data kind="{label}">\n{body}\n</untrusted_data>'
