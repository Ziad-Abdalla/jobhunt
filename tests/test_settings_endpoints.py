"""Smoke tests for the settings endpoints that the new UI relies on."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jobhunt import main as main_mod
from jobhunt.main import app


def test_save_user_env_atomic_and_roundtrips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_mod, "_env_file_path", lambda: tmp_path / ".env")
    main_mod._save_user_env({"JOBHUNT_A": "1", "JOBHUNT_EMPTY": ""})
    assert (tmp_path / ".env").read_text() == "JOBHUNT_A=1\n"
    # No temp-file droppings, and a re-load sees exactly what was saved.
    assert not list(tmp_path.glob("*.tmp"))
    assert main_mod._load_user_env() == {"JOBHUNT_A": "1"}


def test_settings_page_renders() -> None:
    client = TestClient(app)
    resp = client.get("/settings")
    assert resp.status_code == 200
    body = resp.text
    # New UI: separate Check and Install buttons.
    assert 'id="check-btn"' in body
    assert 'id="install-btn"' in body
    # New one-click uninstall button (when not a binary install).
    # In CI the install method may be "uv" or "pip" — both expose the button.
    assert 'id="uninstall-btn"' in body or "Delete the jobhunt file" in body


def test_check_update_endpoint_responds() -> None:
    """The passive check should always return a JSON body and never 5xx,
    even when GitHub is unreachable from the test runner."""
    client = TestClient(app)
    resp = client.get("/api/check-update")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    # "message" is always set, either for success or failure.
    assert "message" in data


def test_sources_page_does_not_500() -> None:
    """Regression: previously a missing sources file after `uv tool install`
    would 500. The route now serves a graceful "no sources" view instead."""
    client = TestClient(app)
    resp = client.get("/sources")
    assert resp.status_code == 200


def test_cv_page_always_loads() -> None:
    """CV page must render even when sentence-transformers isn't installed."""
    client = TestClient(app)
    resp = client.get("/cv")
    assert resp.status_code == 200
