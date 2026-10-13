"""Email digest: recipients, story selection, rendering, the sent log and the run."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from digest.mailer import runMailer
from digest.mailer.recipients import Recipient, RecipientsError, parseRecipients
from digest.mailer.renderEmail import renderHtml, renderText, subjectLine
from digest.mailer.selectStories import selectStories
from digest.mailer.sentLog import SentLog, personKey


def story(id: str, importance: int = 3, **over) -> dict:
    base = {
        "id": id,
        "createdAt": f"2026-10-12T0{importance}:00:00+00:00",
        "headline": f"Headline {id}",
        "summary": "A plain summary.",
        "whyItMatters": "It matters.",
        "category": "Agentic Systems",
        "importance": importance,
        "cloudPlatform": "AWS",
        "industryVertical": "BFSI",
        "sources": [{"name": "Source", "url": "https://example.com/a"}],
    }
    return {**base, **over}


def test_parseRecipientsValidatesAndDropsDuplicates():
    entries = [{"email": "a@x.com"}, {"email": "A@x.com", "name": "dup"}, {"email": "b@x.com"}]
    people = parseRecipients(json.dumps(entries))
    assert [p.email for p in people] == ["a@x.com", "b@x.com"]


def test_parseRecipientsRejectsBadInput():
    with pytest.raises(RecipientsError):
        parseRecipients("not json")
    with pytest.raises(RecipientsError):
        parseRecipients('{"email": "a@x.com"}')
    with pytest.raises(ValueError):
        parseRecipients('[{"email": "nope"}]')


def test_selectionFollowsPreferencesAndRanksByImportance():
    stories = [
        story("a", 2),
        story("b", 5),
        story("c", 4, category="Research"),
        story("d", 4, cloudPlatform="GCP"),
    ]
    person = Recipient(email="a@x.com", categories=["agentic systems"], clouds=["AWS"])
    assert [s["id"] for s in selectStories(stories, person)] == ["b", "a"]
    important = Recipient(email="a@x.com", minImportance=4)
    assert [s["id"] for s in selectStories(stories, important)] == ["b", "d", "c"]


def test_selectionSkipsAlreadySentAndCapsCount():
    stories = [story(str(n), importance=1 + n % 5) for n in range(10)]
    person = Recipient(email="a@x.com", maxStories=3)
    picked = selectStories(stories, person, alreadySent={"4"})
    assert len(picked) == 3 and "4" not in {s["id"] for s in picked}


def test_renderEscapesAndOnlyLinksHttp():
    s = story("a", headline="<script>x</script>", sources=[{"name": "Bad", "url": "javascript:x"}])
    html = renderHtml(Recipient(email="a@x.com", name="Priya"), [s], "https://site", "STOP")
    assert "<script>" not in html and "javascript:" not in html and "Hi Priya" in html
    text = renderText(Recipient(email="a@x.com"), [s], "https://site", "STOP")
    assert "Hi there" in text and "javascript:" not in text


def test_subjectCountsStories():
    day = datetime(2026, 10, 12, tzinfo=UTC).date()
    assert subjectLine("GenAI Daily", day, 1) == "GenAI Daily · 12 Oct: 1 story for you"
    assert subjectLine("GenAI Daily", day, 5).endswith("5 stories for you")


def test_sentLogStoresOnlyHashes(tmp_path):
    path = tmp_path / "emailSent.json"
    log = SentLog(path)
    log.record("Priya@Example.com", ["s1", "s2"])
    log.save()
    assert "priya" not in path.read_text(encoding="utf-8").lower()
    again = SentLog(path)
    assert again.sentIds("priya@example.com") == {"s1", "s2"}
    assert personKey("priya@example.com") == personKey(" PRIYA@example.com ")


def _setup(monkeypatch, tmp_path, stories):
    monkeypatch.setenv("EMAIL_RECIPIENTS", json.dumps([{"name": "Priya", "email": "p@x.com"}]))
    monkeypatch.setenv("GMAIL_ADDRESS", "digest@x.com")
    monkeypatch.setattr(runMailer, "loadRecentStories", lambda days: stories)
    monkeypatch.setattr(runMailer, "SentLog", lambda: SentLog(tmp_path / "emailSent.json"))
    sent: list[str] = []

    def fakeSend(messages):
        sent.extend(str(m["To"]) for m in messages)
        return {str(m["To"]): None for m in messages}

    monkeypatch.setattr(runMailer, "sendAll", fakeSend)
    return sent


def test_dryRunSendsAndLogsNothing(monkeypatch, tmp_path):
    sent = _setup(monkeypatch, tmp_path, [story("a")])
    outcome = runMailer.runEmailDigest(dryRun=True, previewDir=tmp_path / "out")
    assert outcome.sent == ["p@x.com"] and not sent
    assert (tmp_path / "out" / "priya.html").exists()
    assert not (tmp_path / "emailSent.json").exists()


def test_secondRunDoesNotResendTheSameStories(monkeypatch, tmp_path):
    sent = _setup(monkeypatch, tmp_path, [story("a")])
    assert runMailer.runEmailDigest().sent == ["p@x.com"]
    second = runMailer.runEmailDigest()
    assert second.sent == [] and second.skipped == ["p@x.com"] and sent == ["p@x.com"]


def test_testMailToAddressIsNotLogged(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [story("a")])
    runMailer.runEmailDigest(onlyTo="me@x.com")
    assert not (tmp_path / "emailSent.json").exists()


def test_blockedTermsKeepStoryOutOfEmail(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, [story("a", headline="A blockedword story")])
    monkeypatch.setattr(
        runMailer,
        "loadConfig",
        lambda: type("C", (), {"settings": type("S", (), {"blockedTerms": ["blockedword"]})()})(),
    )
    assert runMailer.runEmailDigest().skipped == ["p@x.com"]
