"""Langfuse monitoring: every run is a trace, every agent a span, every LLM call a generation.

Turned on by setting LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY (free keys at
https://cloud.langfuse.com). Without them every function here quietly does nothing, and
if Langfuse is unreachable the pipeline carries on: monitoring must never break a run.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from functools import cache
from typing import Any

from digest.envSettings import CONFIG_DIR, env

log = logging.getLogger(__name__)
PROMPT_DIR = CONFIG_DIR.parent / "src" / "digest" / "agents" / "prompts"


@cache
def langfuseClient() -> Any | None:
    """The Langfuse client, or None when monitoring isn't set up."""
    publicKey, secretKey = env("LANGFUSE_PUBLIC_KEY", ""), env("LANGFUSE_SECRET_KEY", "")
    if not (publicKey and secretKey):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=publicKey,
            secret_key=secretKey,
            base_url=env("LANGFUSE_BASE_URL"),
            environment=env("LANGFUSE_ENVIRONMENT", "production"),
        )
    except Exception as exc:  # never let monitoring stop the pipeline
        log.warning("Langfuse disabled: %s", exc)
        return None


def isEnabled() -> bool:
    return langfuseClient() is not None


def promptVersion() -> str:
    """A short fingerprint of the prompts and model config, to compare runs and evals."""
    digest = hashlib.sha1()
    for path in sorted(PROMPT_DIR.glob("*.md")) + [CONFIG_DIR / "agents.yaml"]:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:8]


class RunTrace:
    """Handle for the current run's trace: add scores, read its URL."""

    def __init__(self, client: Any | None, span: Any | None):
        self.client, self.span = client, span

    def score(self, name: str, value: float | bool | str, comment: str | None = None) -> None:
        if not self.span:
            return
        dataType = (
            "BOOLEAN"
            if isinstance(value, bool)
            else ("CATEGORICAL" if isinstance(value, str) else "NUMERIC")
        )
        try:
            self.span.score_trace(
                name=name,
                value=float(value) if isinstance(value, bool) else value,
                data_type=dataType,
                comment=comment,
            )
        except Exception as exc:
            log.debug("Langfuse score failed: %s", exc)

    def output(self, value: Any) -> None:
        if self.span:
            try:
                self.span.update(output=value)
            except Exception as exc:
                log.debug("Langfuse update failed: %s", exc)

    @property
    def url(self) -> str | None:
        if not self.span:
            return None
        try:
            return self.client.get_trace_url(trace_id=self.span.trace_id)
        except Exception:
            return None


@contextmanager
def traceRun(
    name: str, tags: list[str], input: Any = None, sessionId: str | None = None
) -> Iterator[RunTrace]:
    """One trace for a whole pipeline run (or eval)."""
    client = langfuseClient()
    if client is None:
        yield RunTrace(None, None)
        return
    from langfuse import propagate_attributes

    try:
        with (
            client.start_as_current_observation(name=name, as_type="chain", input=input) as span,
            propagate_attributes(
                trace_name=name, tags=tags, session_id=sessionId, version=promptVersion()
            ),
        ):
            yield RunTrace(client, span)
    finally:
        try:
            client.flush()
        except Exception as exc:
            log.debug("Langfuse flush failed: %s", exc)


def observeAgent(name: str, input: Any = None):
    """A span for one agent step (scout, analyst, writer/editor)."""
    client = langfuseClient()
    if client is None:
        return nullcontext(None)
    return client.start_as_current_observation(name=name, as_type="agent", input=input)


def observeGeneration(agent: str, model: str, messages: list[dict], maxTokens: int):
    """A generation for one LLM call; update it with the answer and token counts."""
    client = langfuseClient()
    if client is None:
        return nullcontext(None)
    return client.start_as_current_observation(
        name=agent,
        as_type="generation",
        model=model,
        input=messages,
        model_parameters={"max_tokens": maxTokens},
    )


def endGeneration(
    generation: Any, output: str | None, tokensIn: int, tokensOut: int, error: str | None = None
) -> None:
    if generation is None:
        return
    try:
        generation.update(
            output=output,
            usage_details={"input": tokensIn, "output": tokensOut},
            level="ERROR" if error else "DEFAULT",
            status_message=error,
        )
    except Exception as exc:
        log.debug("Langfuse generation update failed: %s", exc)


def syncEvalDataset(name: str, cases: list[dict], description: str) -> bool:
    """Mirror the eval test set as a Langfuse dataset (items are upserted by case id)."""
    client = langfuseClient()
    if client is None:
        return False
    try:
        try:
            client.get_dataset(name)
        except Exception:
            client.create_dataset(name=name, description=description)
        for case in cases:
            client.create_dataset_item(
                dataset_name=name,
                id=f"{name}-{case['id']}",
                input={k: case[k] for k in ("title", "url", "excerpt", "sourceName") if k in case},
                expected_output={"expect": case["expect"], "forbidden": case.get("forbidden", [])},
                metadata={
                    "caseId": case["id"],
                    "trap": case.get("trap"),
                    "group": case.get("group"),
                },
            )
        return True
    except Exception as exc:
        log.warning("Could not sync the eval dataset to Langfuse: %s", exc)
        return False
