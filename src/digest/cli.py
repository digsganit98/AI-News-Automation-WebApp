"""Command-line entry point:  uv run digest <command>

Commands
  sources   list the configured sources
  collect   fetch every enabled source and save data/raw/<date>.json
  mcp       start the MCP server (stdio) that exposes the news tools to agents
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

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


def commandCollect(args: argparse.Namespace) -> int:
    config = loadConfig()
    seen = SeenStore(SEEN_FILE)
    result = asyncio.run(collectSources(config, hours=args.hours))
    result.items = dedupe(result.items, seen)

    table = summaryTable(result)
    print(table)
    writeGithubSummary("## Collection\n\n" + table)

    if args.dryRun:
        for item in result.items[:50]:
            print(f"- [{item.sourceName}] {item.title}\n  {item.url}")
        return 0

    path = writeCollection(result, Path(args.out) if args.out else None)
    print(f"Saved {path}")
    if args.markSeen:
        # Remember what was saved so tomorrow's run doesn't save it again.
        seen.add(result.items)
        seen.prune()
        seen.save()
    # Fail the run only if every source failed; one broken source is expected now and then.
    return 0 if any(h.ok for h in result.health) else 1


def commandMcp(_: argparse.Namespace) -> int:
    from digest.newsToolsServer import runServer

    runServer()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="digest", description="GenAI Daily Digest pipeline")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug logs")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sources", help="list configured sources").set_defaults(func=commandSources)

    collect = sub.add_parser("collect", help="fetch all sources and save the raw items")
    collect.add_argument("--hours", type=int, help="look back this many hours (default: config)")
    collect.add_argument(
        "--dry-run", dest="dryRun", action="store_true", help="print results, save nothing"
    )
    collect.add_argument("--out", help="folder to save into (default: data/raw)")
    collect.add_argument(
        "--no-mark-seen",
        dest="markSeen",
        action="store_false",
        help="don't add saved items to state/seen.json (for test runs)",
    )
    collect.set_defaults(func=commandCollect)

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
        logging.getLogger("httpx").setLevel(logging.WARNING)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
