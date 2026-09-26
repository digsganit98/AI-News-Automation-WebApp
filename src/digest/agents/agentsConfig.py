"""Loads config/agents.yaml (models, fallbacks, budget, scout groups)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from digest.envSettings import CONFIG_DIR
from digest.sourcesConfig import expandSettings

AGENTS_FILE = CONFIG_DIR / "agents.yaml"


class Provider(BaseModel):
    baseUrl: str
    apiKeyEnv: str
    tokensPerMinute: int | None = None  # free-tier limit per model; None = not paced
    tokensPerDay: int | None = None  # free-tier daily limit per model; None = not tracked


class ModelChoice(BaseModel):
    provider: str
    model: str
    reasoningEffort: str | None = None  # "low" keeps reasoning models from using up the output


class Budget(BaseModel):
    dailyCallCap: int = 100
    dailyEditionReserve: int = 25
    maxItemsPerScout: int = 25
    maxArticlesPerScout: int = 3
    maxStoriesForWriter: int = 12


class ScoutSpec(BaseModel):
    name: str
    groups: list[str]


class AgentsConfig(BaseModel):
    providers: dict[str, Provider]
    budget: Budget = Budget()
    models: dict[str, list[ModelChoice]]
    maxOutputTokens: dict[str, int] = {}
    scouts: dict[str, ScoutSpec]


def loadAgentsConfig(path: Path | None = None) -> AgentsConfig:
    with open(path or AGENTS_FILE, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AgentsConfig.model_validate(expandSettings(raw))
