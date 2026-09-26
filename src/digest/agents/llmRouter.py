"""Sends each agent's request to its models in order, until one gives a valid answer.

- Models come from config/agents.yaml; providers without an API key are skipped.
- Free tiers limit tokens per minute (Groq: 8,000 per model), so calls are paced, and a
  short "rate limited" or "overloaded" reply is waited out and retried on the same model.
- Answers must be JSON matching the agent's Pydantic schema, or the next model is tried.
- Every call is counted in the daily budget and logged for the run summary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TypeVar

import openai
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from digest.agents.agentsConfig import AgentsConfig, ModelChoice
from digest.agents.llmBudget import BudgetExceededError, LlmBudget
from digest.envSettings import env
from digest.monitoring.langfuseTracing import endGeneration, observeGeneration

log = logging.getLogger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)

TEMPERATURE = {"writer": 0.7}  # everyone else: 0.2 (factual work)
DEFAULT_MAX_OUTPUT = 3000
PROMPT_WRAPPER_TOKENS = 100  # "Reply with only a JSON object..." + a safety margin
MAX_WAIT_SECONDS = 45  # longer waits (e.g. a daily quota) mean: move on to the next model
ATTEMPTS_PER_MODEL = 3
_RETRY_AFTER = re.compile(r"(?:try again|retry) in ([\d.]+)\s*(ms|s)", re.IGNORECASE)


class LlmUnavailableError(RuntimeError):
    """No model could answer (no keys, all failing, or budget used up)."""


@dataclass
class CallRecord:
    agent: str
    model: str
    ok: bool
    tokensIn: int = 0
    tokensOut: int = 0
    error: str = ""


class TokenPacer:
    """Keeps each model under its tokens-per-minute limit (sliding 60-second window)."""

    def __init__(self) -> None:
        self.windows: dict[str, deque[tuple[float, int]]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    async def reserve(self, model: str, tokens: int, perMinute: int | None) -> None:
        if not perMinute:
            return
        tokens = min(tokens, perMinute)
        lock = self.locks.setdefault(model, asyncio.Lock())
        async with lock:
            window = self.windows.setdefault(model, deque())
            while True:
                now = time.monotonic()
                while window and now - window[0][0] >= 60:
                    window.popleft()
                if sum(t for _, t in window) + tokens <= perMinute:
                    window.append((now, tokens))
                    return
                await asyncio.sleep(60 - (now - window[0][0]) + 0.5)


def retryAfterSeconds(exc: Exception) -> float | None:
    match = _RETRY_AFTER.search(str(exc))
    if not match:
        return None
    value = float(match.group(1))
    return value / 1000 if match.group(2).lower() == "ms" else value


def isWorthRetrying(exc: Exception) -> bool:
    """Rate limits and overloaded servers usually clear within seconds; a used-up daily
    quota doesn't, so that goes straight to the next model."""
    if "exceeded your current quota" in str(exc).lower():
        return False
    if isinstance(exc, openai.RateLimitError | openai.APITimeoutError | openai.APIConnectionError):
        return True
    return isinstance(exc, openai.APIStatusError) and exc.status_code in (500, 502, 503, 504)


def messageText(message: object) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, list):  # some providers return content blocks
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parseAnswer[T: BaseModel](text: str, schema: type[T]) -> tuple[T | None, str]:
    """Parse a model's JSON answer into `schema`, forgiving harmless slips:
    code fences around the JSON, or a bare list when the schema is a single list field
    (e.g. `[...]` instead of `{"notes": [...]}`). Every field is still validated."""
    try:
        data = json.loads(_FENCE.sub("", text.strip()))
    except json.JSONDecodeError as exc:
        return None, f"not JSON ({exc.msg})"
    listFields = [
        name
        for name, f in schema.model_fields.items()
        if getattr(f.annotation, "__origin__", None) is list
    ]
    if isinstance(data, list) and len(schema.model_fields) == 1 and listFields:
        data = {listFields[0]: data}
    try:
        return schema.model_validate(data), ""
    except ValidationError as exc:
        return None, f"doesn't match the schema ({exc.error_count()} errors: {str(exc)[:200]})"


def schemaSketch(schema: type[BaseModel]) -> str:
    """A compact template of the answer's shape, e.g. {"keepRefs":["str"]}.

    Much shorter than a full JSON Schema (saves up to ~400 tokens per call); the answer is
    still validated against the real schema.
    """
    full = schema.model_json_schema()
    defs = full.get("$defs", {})

    def sketch(node: dict):
        if "$ref" in node:
            return sketch(defs[node["$ref"].split("/")[-1]])
        if "anyOf" in node:
            parts = [sketch(n) for n in node["anyOf"] if n.get("type") != "null"]
            return "|".join(str(p) for p in parts) + "|null"
        if "enum" in node:
            return "|".join(node["enum"])
        kind = node.get("type")
        if kind == "object":
            return {k: sketch(v) for k, v in node.get("properties", {}).items()}
        if kind == "array":
            return [sketch(node.get("items", {}))]
        names = {"string": "str", "integer": "int", "number": "num", "boolean": "bool"}
        return names.get(kind, "any")

    return json.dumps(sketch(full), separators=(",", ":"), ensure_ascii=False)


def estimateTokens(*texts: str) -> int:
    return sum(len(t) for t in texts) // 3 + 50


@dataclass
class LlmRouter:
    config: AgentsConfig
    budget: LlmBudget
    calls: list[CallRecord] = field(default_factory=list)
    pacer: TokenPacer = field(default_factory=TokenPacer)
    # Models that hit a hard failure (quota used up, still overloaded after retries) are
    # skipped for the rest of the run instead of being retried on every call.
    benched: set[str] = field(default_factory=set)

    def _apiKey(self, choice: ModelChoice) -> str:
        provider = self.config.providers[choice.provider]
        return env(provider.apiKeyEnv, "")

    def modelsFor(self, agent: str) -> list[ModelChoice]:
        return [m for m in self.config.models[agent] if self._apiKey(m)]

    def isAvailable(self) -> bool:
        return any(self.modelsFor(agent) for agent in self.config.models)

    def maxOutput(self, agent: str) -> int:
        return self.config.maxOutputTokens.get(agent, DEFAULT_MAX_OUTPUT)

    def inputBudget(
        self, agent: str, system: str, schema: type[BaseModel], maxOutput: int | None = None
    ) -> int | None:
        """Tokens the user message may use so the request fits EVERY model of `agent`,
        including those with a per-minute limit (Groq: 8k). None = no model has a limit.

        Agents trim what they send to this size, so a busy Gemini can always hand over to Groq
        instead of the request being "too large" for it.
        """
        limits = [self.config.providers[m.provider].tokensPerMinute for m in self.modelsFor(agent)]
        limits = [limit for limit in limits if limit]
        if not limits:
            return None
        overhead = estimateTokens(system, schemaSketch(schema)) + PROMPT_WRAPPER_TOKENS
        return min(limits) - (maxOutput or self.maxOutput(agent)) - overhead

    def _chat(self, agent: str, choice: ModelChoice, maxOutput: int | None = None) -> ChatOpenAI:
        return ChatOpenAI(
            model=choice.model,
            base_url=self.config.providers[choice.provider].baseUrl,
            api_key=self._apiKey(choice),
            temperature=TEMPERATURE.get(agent, 0.2),
            max_tokens=maxOutput or self.maxOutput(agent),
            reasoning_effort=choice.reasoningEffort,
            timeout=120,
            max_retries=0,  # retries are handled here, with the provider's suggested wait
        )

    async def structured(
        self,
        agent: str,
        schema: type[SchemaT],
        system: str,
        user: str,
        maxOutput: int | None = None,
    ) -> SchemaT:
        """Ask `agent`'s models in turn; return the first answer that fits `schema`."""
        choices = self.modelsFor(agent)
        if not choices:
            raise LlmUnavailableError(f"No API key set for any model of '{agent}'")
        prompt = (
            f"{user}\n\nReply with only a JSON object shaped like this:\n{schemaSketch(schema)}"
        )
        messages = [SystemMessage(system), HumanMessage(prompt)]
        traceMessages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        outputLimit = maxOutput or self.maxOutput(agent)
        needed = estimateTokens(system, prompt) + outputLimit

        for choice in choices:
            label = f"{choice.provider}/{choice.model}"
            provider = self.config.providers[choice.provider]
            perMinute = provider.tokensPerMinute
            if label in self.benched:
                continue
            if perMinute and needed > perMinute:
                log.info("%s: request too large for %s's per-minute limit; skipping", agent, label)
                continue
            if provider.tokensPerDay and (
                self.budget.modelTokens(label) + needed > provider.tokensPerDay
            ):
                log.info("%s: %s is near its daily token limit; skipping", agent, label)
                continue
            runnable = self._chat(agent, choice, outputLimit).bind(
                response_format={"type": "json_object"}
            )
            for attempt in range(1, ATTEMPTS_PER_MODEL + 1):
                try:
                    self.budget.check()
                except BudgetExceededError as exc:
                    raise LlmUnavailableError(str(exc)) from exc
                await self.pacer.reserve(label, needed, perMinute)
                with observeGeneration(agent, label, traceMessages, outputLimit) as gen:
                    try:
                        result = await runnable.ainvoke(messages)
                    except Exception as exc:
                        wait = retryAfterSeconds(exc) or 5 * attempt
                        retry = (
                            isWorthRetrying(exc)
                            and attempt < ATTEMPTS_PER_MODEL
                            and wait <= MAX_WAIT_SECONDS
                        )
                        endGeneration(gen, None, 0, 0, f"{type(exc).__name__}: {str(exc)[:300]}")
                        if retry:
                            log.info(
                                "%s via %s: %s; retrying in %.0fs",
                                agent,
                                label,
                                type(exc).__name__,
                                wait,
                            )
                            await asyncio.sleep(wait + 1)
                            continue
                        log.warning("%s via %s failed: %s", agent, label, str(exc)[:300])
                        self.calls.append(CallRecord(agent, label, False, error=type(exc).__name__))
                        if isWorthRetrying(exc) or "quota" in str(exc).lower():
                            self.benched.add(label)  # down for now: don't try it again this run
                        break

                    usage = getattr(result, "usage_metadata", None) or {}
                    tokensIn = usage.get("input_tokens", 0)
                    tokensOut = usage.get("output_tokens", 0)
                    self.budget.record(agent, label, tokensIn, tokensOut)
                    text = messageText(result)
                    parsed, reason = parseAnswer(text, schema)
                    endGeneration(gen, text, tokensIn, tokensOut, None if parsed else reason)
                if parsed is None:
                    log.warning("%s via %s gave an unusable answer: %s", agent, label, reason)
                    self.calls.append(
                        CallRecord(agent, label, False, tokensIn, tokensOut, "invalid JSON")
                    )
                    break
                self.calls.append(CallRecord(agent, label, True, tokensIn, tokensOut))
                return parsed
        raise LlmUnavailableError(f"Every model for '{agent}' failed")
