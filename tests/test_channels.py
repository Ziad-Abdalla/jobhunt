"""P7: off-machine alert channels (telegram + email) + backup redaction."""

from __future__ import annotations

import respx
from httpx import Response

from jobhunt import channels
from jobhunt.cli import _redact_env


class TestTelegram:
    @respx.mock
    def test_sends_when_configured(self, monkeypatch):
        monkeypatch.setattr(channels.settings, "telegram_bot_token", "T:tok")
        monkeypatch.setattr(channels.settings, "telegram_chat_id", "42")
        route = respx.post("https://api.telegram.org/botT:tok/sendMessage").mock(
            return_value=Response(200, json={"ok": True})
        )
        ok = channels._send_telegram("Title", "Body & <stuff>", "https://x.com/1")
        assert ok is True
        assert route.called
        sent = route.calls[0].request
        body = sent.content.decode()
        assert "42" in body
        # HTML-escaped so Telegram HTML parse_mode can't choke / inject.
        assert "%3C" in body or "&lt;" in body or "<stuff>" not in body

    def test_disabled_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(channels.settings, "telegram_bot_token", "")
        monkeypatch.setattr(channels.settings, "telegram_chat_id", "")
        assert channels._send_telegram("T", "B", None) is False

    @respx.mock
    def test_failure_swallowed(self, monkeypatch):
        monkeypatch.setattr(channels.settings, "telegram_bot_token", "T:tok")
        monkeypatch.setattr(channels.settings, "telegram_chat_id", "42")
        respx.post("https://api.telegram.org/botT:tok/sendMessage").mock(
            return_value=Response(500)
        )
        # Never raises; returns False on a non-2xx.
        assert channels._send_telegram("T", "B", None) is False


class TestEmail:
    def test_sends_via_smtp(self, monkeypatch):
        sent = {}

        class _FakeSMTP:
            def __init__(self, host, port, timeout=None):
                sent["host"] = host
                sent["port"] = port

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self):
                sent["tls"] = True

            def login(self, u, p):
                sent["login"] = (u, p)

            def send_message(self, msg):
                sent["to"] = msg["To"]
                sent["subject"] = msg["Subject"]

        monkeypatch.setattr(channels.smtplib, "SMTP", _FakeSMTP)
        monkeypatch.setattr(channels.settings, "smtp_host", "smtp.x.com")
        monkeypatch.setattr(channels.settings, "smtp_to", "me@x.com")
        monkeypatch.setattr(channels.settings, "smtp_user", "u")
        monkeypatch.setattr(channels.settings, "smtp_password", "p")
        ok = channels._send_email("Title", "Body", "https://x.com/1")
        assert ok is True
        assert sent["host"] == "smtp.x.com"
        assert sent["tls"] is True
        assert sent["to"] == "me@x.com"

    def test_disabled_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(channels.settings, "smtp_host", "")
        monkeypatch.setattr(channels.settings, "smtp_to", "")
        assert channels._send_email("T", "B", None) is False

    def test_failure_swallowed(self, monkeypatch):
        def _boom(*a, **k):
            raise OSError("no route to host")

        monkeypatch.setattr(channels.smtplib, "SMTP", _boom)
        monkeypatch.setattr(channels.settings, "smtp_host", "smtp.x.com")
        monkeypatch.setattr(channels.settings, "smtp_to", "me@x.com")
        assert channels._send_email("T", "B", None) is False


class TestSendAll:
    def test_desktop_only_when_nothing_configured(self, monkeypatch):
        calls = []
        monkeypatch.setattr(channels, "notify", lambda *a, **k: calls.append("desktop") or True)
        monkeypatch.setattr(channels, "_send_telegram", lambda *a: calls.append("tg") or False)
        monkeypatch.setattr(channels, "_send_email", lambda *a: calls.append("email") or False)
        monkeypatch.setattr(channels.settings, "telegram_bot_token", "")
        monkeypatch.setattr(channels.settings, "smtp_host", "")
        channels.send_all("T", "B", "https://x/1")
        # send_all always attempts every channel; each self-gates on config.
        assert "desktop" in calls


class TestBackupRedaction:
    def test_redacts_telegram_and_smtp_secrets(self):
        env = (
            "JOBHUNT_JOOBLE_API_KEY=abc\n"
            "JOBHUNT_TELEGRAM_BOT_TOKEN=123:secretpart\n"
            "JOBHUNT_SMTP_PASSWORD=hunter2\n"
            "JOBHUNT_USER_LOCATION=Cairo, Egypt\n"
        )
        out = _redact_env(env)
        assert "secretpart" not in out
        assert "hunter2" not in out
        assert "abc" not in out
        # Non-secret config is preserved.
        assert "Cairo, Egypt" in out
