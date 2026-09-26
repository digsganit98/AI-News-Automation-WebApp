"""Loads config/sources.yaml.

Values written as ${NAME} are filled in from the environment (see settings.py), so the
YAML only says *which* setting a source uses and every URL lives in config/app.env.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from digest.envSettings import CONFIG_DIR, env

DEFAULT_SOURCES_FILE = CONFIG_DIR / "sources.yaml"
_VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


class SourceConfig(BaseModel):
    """One entry under `sources:`. Type-specific keys (selectors, query, ...) are kept as extras."""

    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    type: str
    enabled: bool = True
    url: str | None = None

    def opt(self, key: str, default: Any = None) -> Any:
        return (self.model_extra or {}).get(key, default)


class Settings(BaseModel):
    windowHours: int = 36
    requestTimeout: float = 30.0
    notArticleHosts: list[str] = []  # discussion/social sites: a link there isn't an article


class Config(BaseModel):
    settings: Settings = Field(default_factory=Settings)
    sources: list[SourceConfig]

    @property
    def enabledSources(self) -> list[SourceConfig]:
        return [s for s in self.sources if s.enabled]


def expandSettings(value: Any) -> Any:
    if isinstance(value, str):
        return _VAR.sub(lambda m: env(m.group(1)), value)
    if isinstance(value, list):
        return [expandSettings(v) for v in value]
    if isinstance(value, dict):
        return {k: expandSettings(v) for k, v in value.items()}
    return value


def loadConfig(path: Path | None = None) -> Config:
    with open(path or DEFAULT_SOURCES_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    # Only enabled sources need their settings to exist.
    raw["sources"] = [
        expandSettings(s) if s.get("enabled", True) else s for s in raw.get("sources", [])
    ]
    return Config.model_validate(raw)
