"""Audit follow-up: the settings page must not render raw API keys, and a
blank save must keep the stored key (masking never wipes it)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from jobhunt.config import settings
from jobhunt.main import app

client = TestClient(app, headers={"origin": "http://testserver"})


def test_settings_page_does_not_render_raw_key(monkeypatch):
    monkeypatch.setattr(settings, "jooble_api_key", "SUPERSECRET-JOOBLE")
    monkeypatch.setattr(settings, "reed_api_key", "SUPERSECRET-REED")
    body = client.get("/settings").text
    assert "SUPERSECRET-JOOBLE" not in body
    assert "SUPERSECRET-REED" not in body
    assert "key set" in body  # the "✓ key set" indicator still shows


def test_blank_save_keeps_existing_key(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "jooble_api_key", "KEEPME-JOOBLE")
    monkeypatch.setattr(settings, "reed_api_key", "KEEPME-REED")
    # Save with blank key fields (as the masked form submits) — keys must survive.
    monkeypatch.setattr("jobhunt.main._load_user_env", lambda: {})
    saved = {}
    monkeypatch.setattr("jobhunt.main._save_user_env", lambda d: saved.update(d))
    r = client.post("/api/settings/save", data={
        "jooble_api_key": "", "reed_api_key": "", "user_location": "Cairo, Egypt",
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert settings.jooble_api_key == "KEEPME-JOOBLE"
    assert settings.reed_api_key == "KEEPME-REED"
    assert settings.user_location == "Cairo, Egypt"


def test_discord_webhook_save_and_mask(monkeypatch):
    monkeypatch.setattr(settings, "discord_webhook_url", "")
    monkeypatch.setattr("jobhunt.main._load_user_env", lambda: {})
    saved = {}
    monkeypatch.setattr("jobhunt.main._save_user_env", lambda d: saved.update(d))
    r = client.post("/api/settings/save", data={
        "discord_webhook_url": "https://discord.com/api/webhooks/1/tok",
        "user_location": "",
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert settings.discord_webhook_url == "https://discord.com/api/webhooks/1/tok"
    assert saved["JOBHUNT_DISCORD_WEBHOOK_URL"].endswith("/tok")
    # The page never renders the raw webhook; blank re-save keeps it.
    body = client.get("/settings").text
    assert "webhooks/1/tok" not in body
    assert "webhook set" in body
    client.post("/api/settings/save", data={
        "discord_webhook_url": "", "user_location": "",
    }, follow_redirects=False)
    assert settings.discord_webhook_url == "https://discord.com/api/webhooks/1/tok"


def test_nonblank_save_updates_key(monkeypatch):
    monkeypatch.setattr(settings, "jooble_api_key", "OLD")
    monkeypatch.setattr("jobhunt.main._load_user_env", lambda: {})
    monkeypatch.setattr("jobhunt.main._save_user_env", lambda d: None)
    client.post("/api/settings/save", data={
        "jooble_api_key": "NEWKEY", "reed_api_key": "", "user_location": "",
    }, follow_redirects=False)
    assert settings.jooble_api_key == "NEWKEY"
