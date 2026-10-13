"""Builds the HTML and plain-text bodies. Everything from the data is escaped."""

from __future__ import annotations

from datetime import date
from html import escape

from digest.mailer.recipients import Recipient

ACCENT = "#4f46e5"


def _safeUrl(url: str | None) -> str | None:
    return url if url and url.startswith(("https://", "http://")) else None


def _sourceLinks(story: dict) -> list[tuple[str, str]]:
    return [(s["name"], u) for s in story.get("sources", []) if (u := _safeUrl(s.get("url")))]


def subjectLine(prefix: str, day: date, count: int) -> str:
    noun = "story" if count == 1 else "stories"
    return f"{prefix} · {day.strftime('%d %b')}: {count} {noun} for you"


def renderText(person: Recipient, stories: list[dict], siteUrl: str, unsubscribe: str) -> str:
    lines = [f"Hi {person.greetingName}, here is what is new in GenAI.", ""]
    for n, s in enumerate(stories, 1):
        lines.append(f"{n}. {s['headline']}  [{s['category']} · importance {s['importance']}/5]")
        lines.append(s["summary"])
        if s.get("whyItMatters"):
            lines.append(f"Why it matters: {s['whyItMatters']}")
        lines += [f"{name}: {url}" for name, url in _sourceLinks(s)]
        lines.append("")
    lines += [f"All stories: {siteUrl}", "", unsubscribe]
    return "\n".join(lines)


def renderHtml(person: Recipient, stories: list[dict], siteUrl: str, unsubscribe: str) -> str:
    cards = []
    for s in stories:
        links = " · ".join(
            f'<a href="{escape(u)}" style="color:{ACCENT}">{escape(name)}</a>'
            for name, u in _sourceLinks(s)
        )
        why = (
            '<p style="margin:6px 0 0;color:#444"><b>Why it matters:</b> '
            f"{escape(s['whyItMatters'])}</p>"
            if s.get("whyItMatters")
            else ""
        )
        cards.append(
            '<div style="padding:16px 0;border-top:1px solid #e5e7eb">'
            f'<div style="font-size:12px;color:#6b7280">{escape(s["category"])} · '
            f"importance {int(s['importance'])}/5</div>"
            f'<h2 style="margin:4px 0;font-size:18px">{escape(s["headline"])}</h2>'
            f'<p style="margin:6px 0 0">{escape(s["summary"])}</p>{why}'
            f'<p style="margin:8px 0 0;font-size:14px">{links}</p></div>'
        )
    return (
        '<!doctype html><html><body style="margin:0;background:#f3f4f6">'
        '<div style="max-width:620px;margin:0 auto;padding:24px 16px;'
        'font-family:Inter,Segoe UI,Arial,sans-serif;color:#111;background:#fff">'
        f'<h1 style="margin:0 0 4px;font-size:22px;color:{ACCENT}">GenAI Daily</h1>'
        f"<p>Hi {escape(person.greetingName)}, here is what is new in GenAI.</p>"
        f"{''.join(cards)}"
        '<p style="margin-top:24px;font-size:13px;color:#6b7280;border-top:1px solid #e5e7eb;'
        f'padding-top:12px"><a href="{escape(siteUrl)}" style="color:{ACCENT}">All stories on '
        f"the site</a><br>{escape(unsubscribe)}</p></div></body></html>"
    )
