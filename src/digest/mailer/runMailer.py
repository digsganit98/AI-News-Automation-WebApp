"""The `digest email` command: select, render, send and log, one person at a time."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from digest.envSettings import env
from digest.mailer.recipients import Recipient, RecipientsError, loadRecipients
from digest.mailer.renderEmail import renderHtml, renderText, subjectLine
from digest.mailer.selectStories import selectStories
from digest.mailer.sendEmail import buildMessage, sendAll
from digest.mailer.sentLog import SentLog
from digest.processing.contentSafety import blockedPattern, isBlocked
from digest.publish.saveDataFiles import digestDate
from digest.publish.saveStories import loadRecentStories
from digest.sourcesConfig import loadConfig


@dataclass
class MailerOutcome:
    sent: list[str] = field(default_factory=list)  # with --dry-run: who would get one
    skipped: list[str] = field(default_factory=list)  # nothing new for them
    failed: dict[str, str] = field(default_factory=dict)
    previews: list[Path] = field(default_factory=list)

    def markdown(self, dryRun: bool) -> str:
        verb = "Would send" if dryRun else "Sent"
        lines = [
            "## Email digest",
            "",
            f"{verb}: {len(self.sent)} · nothing new: {len(self.skipped)} · "
            f"failed: {len(self.failed)}",
        ]
        lines += [f"- ❌ {who}: {why}" for who, why in self.failed.items()]
        return "\n".join(lines)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "recipient"


def _safeStories(stories: list[dict]) -> list[dict]:
    """The site's content policy, applied once more to what goes out by email."""
    pattern = blockedPattern(loadConfig().settings.blockedTerms)
    return [
        s
        for s in stories
        if not isBlocked(f"{s['headline']} {s['summary']} {s.get('whyItMatters', '')}", pattern)
    ]


def _forAddress(address: str) -> list[Recipient]:
    """`--to`: use the person's saved preferences if they are listed, else the defaults."""
    try:
        listed = [p for p in loadRecipients() if p.email.lower() == address.lower()]
    except RecipientsError:  # nothing configured yet: a bare test mail is still useful
        listed = []
    return listed or [Recipient(email=address)]


def runEmailDigest(
    dryRun: bool = False,
    onlyTo: str | None = None,
    previewDir: Path | None = None,
    now: datetime | None = None,
) -> MailerOutcome:
    day = digestDate(now or datetime.now(UTC))
    people = _forAddress(onlyTo) if onlyTo else loadRecipients()
    stories = _safeStories(loadRecentStories(int(env("EMAIL_WINDOW_DAYS", "2"))))
    log = SentLog()
    siteUrl = env("SITE_URL") + env("SITE_BASE_PATH", "")
    sender = env("GMAIL_ADDRESS", "digest@example.com")
    unsubscribe = f"To stop these emails, reply STOP to {sender}."
    prefix = env("EMAIL_SUBJECT_PREFIX", "GenAI Daily")

    outcome, messages, storyIds = MailerOutcome(), [], {}
    for person in people:
        chosen = selectStories(stories, person, log.sentIds(person.email))
        if not chosen:
            outcome.skipped.append(person.email)
            continue
        text = renderText(person, chosen, siteUrl, unsubscribe)
        html = renderHtml(person, chosen, siteUrl, unsubscribe)
        subject = subjectLine(prefix, day, len(chosen))
        if previewDir:
            previewDir.mkdir(parents=True, exist_ok=True)
            path = previewDir / f"{_slug(person.name or person.email.split('@')[0])}.html"
            path.write_text(html, encoding="utf-8")
            outcome.previews.append(path)
        name = env("EMAIL_FROM_NAME", "GenAI Daily")
        messages.append(buildMessage(sender, name, person.email, subject, text, html))
        storyIds[person.email] = [s["id"] for s in chosen]

    if dryRun or not messages:
        outcome.sent = [str(m["To"]) for m in messages]
        return outcome

    for to, error in sendAll(messages).items():
        if error:
            outcome.failed[to] = error
        else:
            outcome.sent.append(to)
            if not onlyTo:  # a one-off test mail must not use up the person's real stories
                log.record(to, storyIds[to])
    if not onlyTo:
        log.save()
    return outcome
