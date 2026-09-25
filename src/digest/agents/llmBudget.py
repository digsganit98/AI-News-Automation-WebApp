"""Daily LLM call budget, kept in state/llmUsage.json.

Every call is counted. 3-hourly updates may use the budget only up to
`dailyCallCap - dailyEditionReserve`, so the 10:00 IST edition always has calls left.
The count resets each day (in the digest's timezone).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from digest.agents.agentsConfig import Budget
from digest.publish.saveDataFiles import STATE_DIR, digestDate

USAGE_FILE = STATE_DIR / "llmUsage.json"


class BudgetExceededError(RuntimeError):
    pass


class LlmBudget:
    def __init__(self, budget: Budget, mode: str, path: Path = USAGE_FILE):
        self.budget = budget
        self.mode = mode
        self.path = path
        today = digestDate(datetime.now(UTC)).isoformat()
        usage = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if usage.get("date") != today:
            usage = {
                "date": today,
                "calls": 0,
                "tokensIn": 0,
                "tokensOut": 0,
                "byAgent": {},
                "byModel": {},
                "tokensByModel": {},
            }
        self.usage = usage

    @property
    def limit(self) -> int:
        cap = self.budget.dailyCallCap
        return cap if self.mode == "dailyEdition" else cap - self.budget.dailyEditionReserve

    def remaining(self) -> int:
        return max(0, self.limit - self.usage["calls"])

    def check(self) -> None:
        if self.remaining() <= 0:
            raise BudgetExceededError(
                f"Daily LLM budget used up: {self.usage['calls']}/{self.limit} calls ({self.mode})"
            )

    def record(self, agent: str, model: str, tokensIn: int = 0, tokensOut: int = 0) -> None:
        u = self.usage
        u["calls"] += 1
        u["tokensIn"] += tokensIn
        u["tokensOut"] += tokensOut
        u["byAgent"][agent] = u["byAgent"].get(agent, 0) + 1
        u["byModel"][model] = u["byModel"].get(model, 0) + 1
        byModel = u.setdefault("tokensByModel", {})
        byModel[model] = byModel.get(model, 0) + tokensIn + tokensOut

    def modelTokens(self, model: str) -> int:
        """Tokens a model has used today (free tiers cap this per model)."""
        return self.usage.get("tokensByModel", {}).get(model, 0)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.usage, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
