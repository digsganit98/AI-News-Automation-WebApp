"""R&D Hub uploads: checks, HTML clean-up and publishing."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from digest.hub import hubUploads
from digest.hub.hubUploads import checkUpload, parseDetails, publishUpload, sanitizeHtml, slugOf

DETAILS = {"title": "RAG latency", "team": "Platform", "author": "Priya N.", "tags": "RAG, latency"}


def test_parseDetailsReadsLabelledLines():
    text = "Hello\nTitle: A title\n- Team: Platform\nAuthor: Priya N.\nTags: RAG, latency\n"
    assert parseDetails(text) == {
        "title": "A title",
        "team": "Platform",
        "author": "Priya N.",
        "tags": "RAG, latency",
    }


def test_slugIsSafeForFileNames():
    assert slugOf("My Article (final).HTML") == "my-article-final"


def test_sanitizeRemovesScriptsAndExternalLoads():
    html = (
        '<html><body onload="x()"><script>alert(1)</script><h1>Hi</h1>'
        '<iframe src="https://evil"></iframe><img src="https://t.example/p.gif">'
        '<a href="javascript:alert(1)">bad</a><a href="https://ok.example">ok</a>'
        '<p style="background:url(https://t.example/a)">text</p></body></html>'
    )
    clean = sanitizeHtml(html)
    assert "<script" not in clean and "<iframe" not in clean and "onload" not in clean
    assert "t.example" not in clean and "javascript:" not in clean
    assert 'href="https://ok.example"' in clean and "Hi" in clean


def test_checkRejectsWrongTypeAndMissingDetails(tmp_path: Path):
    bad = tmp_path / "notes.docx"
    bad.write_text("x")
    problems = checkUpload([bad], {})
    assert any("only .html and .pdf" in p for p in problems)
    assert any("Title" in p for p in problems)


def test_checkRejectsFakePdfAndMultipleFiles(tmp_path: Path):
    fake = tmp_path / "a.pdf"
    fake.write_text("not a pdf")
    assert any("real PDF" in p for p in checkUpload([fake], DETAILS))
    other = tmp_path / "b.html"
    other.write_text("<p>x</p>")
    assert any("exactly one" in p for p in checkUpload([fake, other], DETAILS))


def test_checkAcceptsGoodHtml(tmp_path: Path):
    good = tmp_path / "rag.html"
    good.write_text("<h1>RAG latency</h1><p>We cached embeddings.</p>")
    assert checkUpload([good], DETAILS) == []


def test_publishWritesSiteFileAndDetails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hubUploads, "SITE_FILES", tmp_path / "site")
    monkeypatch.setattr(hubUploads, "DATA_DIR", tmp_path / "data")
    src = tmp_path / "rag.html"
    src.write_text("<h1>RAG</h1><script>x()</script>")
    record = publishUpload(src, DETAILS, datetime(2026, 10, 12, 8, 0, tzinfo=UTC))
    assert not src.exists()
    assert "<script" not in (tmp_path / "site" / "rag.html").read_text()
    saved = json.loads((tmp_path / "data" / "rag.json").read_text())
    assert saved == record and saved["tags"] == ["RAG", "latency"] and saved["format"] == "html"


def test_checkRefusesWhenTheHubFolderIsFull(tmp_path: Path, monkeypatch):
    site = tmp_path / "site"
    site.mkdir()
    (site / "old.pdf").write_bytes(b"%PDF-" + b"0" * 100)
    monkeypatch.setattr(hubUploads, "SITE_FILES", site)
    monkeypatch.setattr(hubUploads, "MAX_FOLDER_BYTES", 150)
    new = tmp_path / "new.html"
    new.write_text("<p>" + "x" * 100 + "</p>")
    assert any("folder is full" in p for p in checkUpload([new], DETAILS))


def test_publishKeepsDomainCloudAndVertical(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hubUploads, "SITE_FILES", tmp_path / "site")
    monkeypatch.setattr(hubUploads, "DATA_DIR", tmp_path / "data")
    src = tmp_path / "notes.pdf"
    src.write_bytes(b"%PDF-1.7 test")
    details = {**DETAILS, "domain": "GenAI", "cloud": "AWS", "vertical": "BFSI"}
    record = publishUpload(src, details)
    assert (record["techDomain"], record["cloudPlatform"], record["industryVertical"]) == (
        "GenAI",
        "AWS",
        "BFSI",
    )
    assert (tmp_path / "site" / "notes.pdf").exists() and record["format"] == "pdf"


def test_wordFilesAreNotAccepted(tmp_path: Path):
    word = tmp_path / "report.docx"
    word.write_bytes(b"PK")
    assert any("only .html and .pdf" in p for p in checkUpload([word], DETAILS))
