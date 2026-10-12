"""Sends email through Gmail (SMTP over TLS) with an app password. One message per person."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from digest.envSettings import env


def buildMessage(
    sender: str, senderName: str, to: str, subject: str, text: str, html: str
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((senderName, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg["List-Unsubscribe"] = f"<mailto:{sender}?subject=unsubscribe>"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def sendAll(messages: list[EmailMessage]) -> dict[str, str | None]:
    """Send over one connection. Returns {address: None if sent, else the error text}.

    A failure for one person never stops the others.
    """
    host, port = env("SMTP_HOST", "smtp.gmail.com"), int(env("SMTP_PORT", "465"))
    user, password = env("GMAIL_ADDRESS"), env("GMAIL_APP_PASSWORD")
    results: dict[str, str | None] = {}
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(user, password)
        for msg in messages:
            to = str(msg["To"])
            try:
                smtp.send_message(msg)
                results[to] = None
            except (smtplib.SMTPException, OSError) as e:
                results[to] = f"{type(e).__name__}: {e}"
    return results
