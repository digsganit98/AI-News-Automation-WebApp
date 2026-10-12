"""R&D Hub uploads: check an article added to hub/inbox, then publish it to the site.

An article is one .html or .pdf file (up to 5 MB) added in a pull request, with its details
(Title, Team, Author, Tags, Summary) in the pull request description. On the pull request,
`check` explains what to fix. After the merge, `publish` cleans the file and writes
  src/web/public/hub/<slug>.<html|pdf>   the article itself
  data/hub/<slug>.json                   its details, read by the website

    python -m digest.hub.hubUploads check   --details-file details.txt
    python -m digest.hub.hubUploads publish --details-file details.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, Comment

from digest.processing.contentSafety import blockedPattern, isBlocked

ROOT = Path(__file__).resolve().parents[3]
INBOX = ROOT / "hub" / "inbox"
SITE_FILES = ROOT / "src" / "web" / "public" / "hub"
DATA_DIR = ROOT / "data" / "hub"
SOURCES_FILE = ROOT / "config" / "sources.yaml"

SUFFIXES = {".html", ".pdf"}
MAX_BYTES = 5 * 1024 * 1024
REQUIRED = ("title", "team", "author")

# Tags that run code, embed other pages, submit data or change the page's address.
DROP_TAGS = ["script", "iframe", "frame", "frameset", "object", "embed", "applet", "form", "base"]
# Attributes that load something from another page. Links keep their href; the rest don't.
LOAD_ATTRS = {"src", "poster", "data", "srcset", "action", "formaction", "background"}
CSS_RISK = re.compile(r"url\s*\(|@import|expression\s*\(|javascript:", re.IGNORECASE)
DETAIL_LINE = re.compile(r"^\s*[-*]?\s*(title|team|author|tags|summary)\s*:\s*(.+?)\s*$", re.I)


def parseDetails(text: str) -> dict[str, str]:
    """Read 'Title: ...' style lines from a pull request description."""
    details: dict[str, str] = {}
    for line in text.splitlines():
        if match := DETAIL_LINE.match(line):
            details[match.group(1).lower()] = match.group(2)
    return details


def slugOf(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-") or "article"


def _isUnsafeAttribute(name: str, value: str) -> bool:
    """Event handlers, anything that loads from elsewhere, risky CSS, and non-web links."""
    lowered = value.strip().lower()
    if name.startswith("on") or name == "srcdoc":
        return True
    if name in LOAD_ATTRS:
        return not lowered.startswith("data:image/")
    if name == "style":
        return bool(CSS_RISK.search(value))
    if name == "href":
        return not lowered.startswith(("http://", "https://", "mailto:", "#"))
    return False


def sanitizeHtml(html: str) -> str:
    """Strip anything that runs code or loads from elsewhere; keep the readable article."""
    soup = BeautifulSoup(html, "html.parser")
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for tag in soup.find_all([*DROP_TAGS, "link"]):
        tag.decompose()
    for tag in soup.find_all("meta"):
        if tag.get("http-equiv"):
            tag.decompose()
    for tag in soup.find_all("style"):
        if CSS_RISK.search(tag.get_text()):
            tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            raw = tag.attrs[attr]
            if _isUnsafeAttribute(
                attr.lower(), " ".join(raw) if isinstance(raw, list) else str(raw)
            ):
                del tag.attrs[attr]
        if tag.name == "a" and tag.get("href"):
            tag["rel"] = "noopener noreferrer nofollow"
            tag["target"] = "_blank"
    return str(soup)


def _policy() -> re.Pattern[str] | None:
    with open(SOURCES_FILE, encoding="utf-8") as f:
        return blockedPattern(yaml.safe_load(f).get("settings", {}).get("blockedTerms", []))


def inboxFiles(inbox: Path = INBOX) -> list[Path]:
    return sorted(p for p in inbox.glob("*") if p.is_file() and p.name != ".gitkeep")


def checkUpload(files: list[Path], details: dict[str, str]) -> list[str]:
    """Everything wrong with an upload, in plain words. An empty list means it can be merged."""
    if len(files) != 1:
        return [f"Add exactly one .html or .pdf file per pull request (found {len(files)})."]
    path = files[0]
    suffix = path.suffix.lower()
    problems: list[str] = []
    if suffix not in SUFFIXES:
        problems.append(f"{path.name}: only .html and .pdf files are accepted.")
    elif path.stat().st_size > MAX_BYTES:
        problems.append(f"{path.name}: larger than {MAX_BYTES // (1024 * 1024)} MB.")
    elif suffix == ".pdf" and not path.read_bytes().startswith(b"%PDF-"):
        problems.append(f"{path.name}: this isn't a real PDF file.")
    for key in REQUIRED:
        if not details.get(key):
            problems.append(f"Add a '{key.title()}:' line to the pull request description.")
    text = " ".join(details.values())
    if suffix == ".html":
        text += " " + BeautifulSoup(path.read_text("utf-8", "replace"), "html.parser").get_text(" ")
    if isBlocked(text, _policy()):
        problems.append("The content policy check flagged some wording. Please revise the article.")
    return problems


def publishUpload(path: Path, details: dict[str, str], now: datetime | None = None) -> dict:
    """Clean the file, put it where the site reads it, write its details, remove the inbox copy."""
    now = now or datetime.now(UTC)
    slug = slugOf(path.name)
    suffix = path.suffix.lower()
    SITE_FILES.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = SITE_FILES / f"{slug}{suffix}"
    if suffix == ".html":
        target.write_text(sanitizeHtml(path.read_text("utf-8", "replace")), "utf-8")
    else:
        target.write_bytes(path.read_bytes())
    tags = [t.strip() for t in re.split(r"[,;]", details.get("tags", "")) if t.strip()][:6]
    record = {
        "id": slug,
        "title": details["title"],
        "summary": details.get("summary", ""),
        "author": details["author"],
        "team": details["team"],
        "tags": tags,
        "format": suffix.lstrip("."),
        "file": target.name,
        "publishedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (DATA_DIR / f"{slug}.json").write_text(json.dumps(record, indent=2) + "\n", "utf-8")
    path.unlink()
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R&D Hub upload checks and publishing")
    parser.add_argument("command", choices=["check", "publish"])
    parser.add_argument("--details-file", required=True, help="text file with the PR description")
    parser.add_argument("--inbox", default=str(INBOX))
    args = parser.parse_args(argv)

    details = parseDetails(Path(args.details_file).read_text("utf-8"))
    files = inboxFiles(Path(args.inbox))
    problems = checkUpload(files, details)
    if problems:
        print("R&D Hub upload needs changes:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    if args.command == "check":
        print(f"R&D Hub upload looks good: {files[0].name} by {details['author']}.")
        return 0
    record = publishUpload(files[0], details)
    print(f"Published {record['file']} ({record['title']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
