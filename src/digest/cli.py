"""Command-line entry point:  uv run digest <command>

Commands
  sources   list the configured sources
  collect   fetch every enabled source and save data/raw/<date>.json
  run       collect, then run the AI agents (stories every run; digest + op-ed in dailyEdition mode)
  eval      score how well the agents stick to their sources (uses real LLM calls)
  mcp       start the MCP server (stdio) that exposes the news tools to agents
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from digest.collectors.feedCache import saveFeedCache
from digest.dataModels import CollectionResult
from digest.processing.removeDuplicates import SeenStore, dedupe
from digest.publish.saveDataFiles import SEEN_FILE, writeCollection
from digest.runCollectors import collectSources
from digest.sourcesConfig import loadConfig

log = logging.getLogger("digest")


def summaryTable(result: CollectionResult) -> str:
    lines = ["| Source | Status | Items |", "|---|---|---|"]
    for h in result.health:
        status = "✅ ok" if h.ok else f"❌ {h.error}"
        lines.append(f"| {h.sourceName} | {status} | {h.items} |")
    lines.append(f"\n**{len(result.items)} new items** after removing duplicates.")
    return "\n".join(lines)


def writeGithubSummary(markdown: str) -> None:
    """Show the summary on the GitHub Actions run page, when running there."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def commandSources(_: argparse.Namespace) -> int:
    for s in loadConfig().sources:
        print(f"{'on ' if s.enabled else 'off'}  {s.id:24} {s.type:16} {s.url or ''}")
    return 0


def collectNewItems(args: argparse.Namespace) -> tuple[CollectionResult, SeenStore]:
    """Fetch every source and keep only items not seen before."""
    seen = SeenStore(SEEN_FILE)
    result = asyncio.run(collectSources(loadConfig(), hours=args.hours))
    result.items = dedupe(result.items, seen)
    table = summaryTable(result)
    print(table)
    writeGithubSummary("## Collection\n\n" + table)
    return result, seen


def saveCollected(result: CollectionResult, seen: SeenStore, args: argparse.Namespace) -> None:
    path = writeCollection(result, Path(args.out) if args.out else None)
    print(f"Saved {path}")
    if args.markSeen:
        # Remember what was saved so the next run doesn't save it again.
        seen.add(result.items)
        seen.prune()
        seen.save()
        saveFeedCache()  # and when slow feeds (arXiv) were last fetched


def commandCollect(args: argparse.Namespace) -> int:
    result, seen = collectNewItems(args)
    if args.dryRun:
        for item in result.items[:50]:
            print(f"- [{item.sourceName}] {item.title}\n  {item.url}")
        return 0
    saveCollected(result, seen, args)
    # Fail the run only if every source failed; one broken source is expected now and then.
    return 0 if any(h.ok for h in result.health) else 1


def agentSummary(outcome, traceUrl: str | None = None) -> str:
    if not outcome.ran:
        return f"## AI agents\n\nSkipped: {outcome.skippedReason}."
    from digest.agents.groundingStats import LABELS

    lines = [
        "## AI agents",
        "",
        f"**{len(outcome.stories)} stories**"
        + (", digest + op-ed written" if outcome.edition else "")
        + f", {len(outcome.calls)} LLM calls.",
        "",
        "| Agent | Model | Result | Tokens in / out |",
        "|---|---|---|---|",
    ]
    for c in outcome.calls:
        result = "✅" if c.ok else f"❌ {c.error}"
        lines.append(f"| {c.agent} | {c.model} | {result} | {c.tokensIn} / {c.tokensOut} |")
    catches = {k: v for k, v in outcome.grounding.items() if v}
    removed = "; ".join(f"{v} {LABELS.get(k, k)}" for k, v in catches.items()) or "nothing"
    lines += ["", f"Grounding checks removed: {removed}."]
    if outcome.errors:
        lines += ["", "Problems: " + "; ".join(outcome.errors)]
    if traceUrl:
        lines += ["", f"[Full trace in Langfuse]({traceUrl})"]
    return "\n".join(lines)


def scoreRun(trace, result: CollectionResult, outcome) -> None:
    """Quality and health scores on the run's Langfuse trace."""
    from digest.agents.groundingStats import totalCatches

    trace.score("itemsCollected", len(result.items))
    trace.score("sourcesFailing", sum(not h.ok for h in result.health))
    if not outcome.ran:
        return
    trace.score("stories", len(outcome.stories))
    trace.score("llmCalls", len(outcome.calls))
    trace.score("llmCallsFailed", sum(not c.ok for c in outcome.calls))
    trace.score("hallucinationCatches", totalCatches(), "links/sources removed by grounding checks")
    if outcome.edition:
        trace.score("editorApproved", outcome.edition.review.approved)
        trace.score("editorIssues", len(outcome.edition.review.issues))
        trace.score("originalsChecked", outcome.edition.originalsChecked)
    trace.output(
        {
            "stories": [f"[{s.importance}] {s.headline}" for s in outcome.stories],
            "digest": outcome.edition.digest.headline if outcome.edition else None,
            "errors": outcome.errors,
        }
    )


def commandRun(args: argparse.Namespace) -> int:
    from digest.agents.runAgents import runAgents
    from digest.monitoring.langfuseTracing import traceRun
    from digest.publish.saveDataFiles import digestDate
    from digest.publish.saveStories import saveEdition, saveStories

    tags = [args.mode] + (["dryRun"] if args.dryRun else [])
    session = digestDate(datetime.now(UTC)).isoformat()
    with traceRun("news-pipeline", tags, {"mode": args.mode}, session) as trace:
        result, seen = collectNewItems(args)
        if not args.dryRun:
            saveCollected(result, seen, args)
        outcome = asyncio.run(runAgents(result.items, args.mode, saveUsage=not args.dryRun))
        scoreRun(trace, result, outcome)
        summary = agentSummary(outcome, trace.url)
    print(summary)
    writeGithubSummary(summary)

    if args.dryRun:
        for s in outcome.stories:
            print(f"- [{s.category} · {s.importance}] {s.headline}\n  {s.summary}")
        if outcome.edition:
            print(f"\n# {outcome.edition.digest.headline}\n{outcome.edition.digest.dek}")
            print(
                f"\n## Op-ed: {outcome.edition.opEd.title}\n"
                + "\n\n".join(outcome.edition.opEd.paragraphs)
            )
        return 0

    if path := saveStories(outcome.stories):
        print(f"Saved {path}")
    if outcome.edition:
        models: dict[str, int] = {}
        for c in outcome.calls:
            if c.ok:
                models[c.model] = models.get(c.model, 0) + 1
        print(f"Saved {saveEdition(outcome.edition, models)}")
    return 0 if any(h.ok for h in result.health) else 1


def commandEval(_: argparse.Namespace) -> int:
    from digest.evaluation.groundingEval import EVAL_FILE, PASS_SCORE, runGroundingEval
    from digest.monitoring.langfuseTracing import promptVersion, syncEvalDataset, traceRun

    cases = json.loads(EVAL_FILE.read_text(encoding="utf-8"))["cases"]
    dataset = "genai-digest-grounding"
    synced = syncEvalDataset(dataset, cases, "Test set for `digest eval` (evals/groundingSet.json)")
    evalInput = {"cases": len(cases), "prompts": promptVersion()}
    with traceRun("grounding-eval", ["eval"], evalInput) as trace:
        report = asyncio.run(runGroundingEval())
        for name, value in report.checks.items():
            trace.score(f"eval: {name}", value, report.details.get(name))
        trace.score("eval: overall", report.score)
        trace.score("eval: rougeL", report.rougeLAverage, "information only")
        trace.output(report.markdown())
        markdown = report.markdown()
        if trace.url:
            markdown += f"\n\n[Eval trace in Langfuse]({trace.url})"
            markdown += f" · dataset `{dataset}` synced" if synced else ""
    print(markdown)
    writeGithubSummary(markdown)
    return 0 if report.score >= PASS_SCORE else 1


def commandMcp(_: argparse.Namespace) -> int:
    from digest.newsToolsServer import runServer

    runServer()
    return 0


def addCollectOptions(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hours", type=int, help="look back this many hours (default: config)")
    parser.add_argument(
        "--dry-run", dest="dryRun", action="store_true", help="print results, save nothing"
    )
    parser.add_argument("--out", help="folder to save collected items into (default: data/raw)")
    parser.add_argument(
        "--no-mark-seen",
        dest="markSeen",
        action="store_false",
        help="don't add saved items to state/seen.json (for test runs)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="digest", description="GenAI Daily Digest pipeline")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logs")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sources", help="list configured sources").set_defaults(func=commandSources)

    collect = sub.add_parser("collect", help="fetch all sources and save the raw items")
    addCollectOptions(collect)
    collect.set_defaults(func=commandCollect)

    run = sub.add_parser("run", help="collect, then run the AI agents")
    addCollectOptions(run)
    run.add_argument(
        "--mode",
        choices=["update", "dailyEdition"],
        default="update",
        help="update = stories only (every 3 h); dailyEdition = also digest + op-ed (10:00 IST)",
    )
    run.set_defaults(func=commandRun)

    sub.add_parser("eval", help="score the agents on the saved test set").set_defaults(
        func=commandEval
    )
    sub.add_parser("mcp", help="start the MCP news-tools server").set_defaults(func=commandMcp)

    args = parser.parse_args(argv)
    # Windows consoles default to a legacy encoding that can't print emoji/non-English titles.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    # MCP uses stdout for its protocol, so logs always go to stderr.
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not args.verbose:
        for noisy in ("httpx", "mcp", "langchain_mcp_adapters"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
