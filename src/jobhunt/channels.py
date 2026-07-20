"""Off-machine alert channels (P7): Telegram + email, plus the desktop
notifier. Every sender is best-effort — it logs and returns False on any
failure, never raises — so one broken channel never blocks the others or
the scrape pipeline that triggers alerts.

Credentials (Telegram bot token, SMTP password) live in the user's local
.env and are redacted from `jobhunt backup` by default (see cli._redact_env).
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from html import escape

import httpx

from .config import settings
from .notifications import notify

log = logging.getLogger(__name__)


def _send_telegram(title: str, body: str, url: str | None) -> bool:
    """Send via the Telegram Bot API. Enabled when both bot token + chat id
    are configured. HTML-escaped so parse_mode=HTML can't be broken or
    injected by a job title."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return False
    text = f"<b>{escape(title)}</b>\n{escape(body)}"
    if url:
        text += f"\n{escape(url)}"
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=5.0,
        )
        if r.status_code // 100 == 2:
            return True
        log.debug("telegram send returned %s", r.status_code)
    except Exception as exc:  # noqa: BLE001
        # Log the exception TYPE only — the bot token is in the request URL
        # and str(exc) for a transport error can echo it.
        log.debug("telegram send failed: %s", type(exc).__name__)
    return False


def _send_email(title: str, body: str, url: str | None) -> bool:
    """Send via SMTP (STARTTLS). Enabled when smtp_host + smtp_to are set;
    user/password are optional (local MTAs / open relays)."""
    host = settings.smtp_host
    to = settings.smtp_to
    if not host or not to:
        return False
    try:
        # Build inside the try too: header assignment can raise on an odd
        # config value, and this module's contract is "never raises".
        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = settings.smtp_from or settings.smtp_user or to
        msg["To"] = to
        msg.set_content(f"{body}\n\n{url}" if url else body)
        with smtplib.SMTP(host, settings.smtp_port or 587, timeout=10) as smtp:
            try:
                smtp.starttls()
            except Exception:  # noqa: BLE001 — server may not support TLS
                log.debug("smtp starttls unavailable; sending without")
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("email send failed: %s", exc)
    return False


def send_all(title: str, body: str, url: str | None = None) -> dict[str, bool]:
    """Fan out one alert to every channel. Desktop always attempted; the
    off-machine channels self-gate on their config, so a user who sets no
    P7 config keeps exactly the pre-P7 desktop behavior."""
    return {
        "desktop": bool(notify(title, body, url=url)),
        "telegram": _send_telegram(title, body, url),
        "email": _send_email(title, body, url),
    }
