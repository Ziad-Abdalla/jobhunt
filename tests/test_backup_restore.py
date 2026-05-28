"""Tests for `jobhunt backup` + `jobhunt restore`.

Round-trip: seed a saved search, backup, wipe, restore, verify the
saved search came back. Plus negative cases — bad zip, wrong schema."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jobhunt.cli import app as cli_app
from jobhunt.db import db_session
from jobhunt.models import SavedSearch

runner = CliRunner()


def _clear_searches() -> None:
    with db_session() as s:
        s.query(SavedSearch).delete()


def test_backup_creates_valid_zip(tmp_path: Path) -> None:
    """`jobhunt backup -o file` produces a zip with the expected JSON inside."""
    _clear_searches()
    with db_session() as s:
        s.add(SavedSearch(name="alpha", query_json={"q": "python"}, notify=True, notified_job_ids=[]))

    out = tmp_path / "backup.zip"
    result = runner.invoke(cli_app, ["backup", "-o", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()

    with zipfile.ZipFile(out) as z:
        with z.open("jobhunt-backup.json") as f:
            payload = json.load(f)
    assert payload["schema"] == 1
    assert any(r["name"] == "alpha" for r in payload["saved_searches"])
    _clear_searches()


def test_restore_round_trips_saved_searches(tmp_path: Path) -> None:
    _clear_searches()
    with db_session() as s:
        s.add(SavedSearch(name="beta", query_json={"q": "react"}, notify=False, notified_job_ids=[]))

    out = tmp_path / "round.zip"
    result = runner.invoke(cli_app, ["backup", "-o", str(out)])
    assert result.exit_code == 0

    _clear_searches()
    with db_session() as s:
        assert s.query(SavedSearch).count() == 0

    result = runner.invoke(cli_app, ["restore", str(out), "--force"])
    assert result.exit_code == 0, result.stdout

    with db_session() as s:
        rows = list(s.query(SavedSearch).filter(SavedSearch.name == "beta").all())
    assert len(rows) == 1
    assert rows[0].query_json["q"] == "react"
    assert rows[0].notify is False
    _clear_searches()


def test_restore_rejects_non_zip(tmp_path: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"this is not a zip file")
    result = runner.invoke(cli_app, ["restore", str(bad), "--force"])
    assert result.exit_code == 1
    assert "not a valid jobhunt backup" in result.stdout + result.stderr


def test_restore_rejects_zip_without_payload(tmp_path: Path) -> None:
    bad = tmp_path / "empty.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("something-else.txt", "x")
    result = runner.invoke(cli_app, ["restore", str(bad), "--force"])
    assert result.exit_code == 1


def test_restore_rejects_wrong_schema(tmp_path: Path) -> None:
    bad = tmp_path / "wrong-schema.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("jobhunt-backup.json", json.dumps({"schema": 99}))
    result = runner.invoke(cli_app, ["restore", str(bad), "--force"])
    assert result.exit_code == 1
    assert "schema 99" in result.stdout + result.stderr


def test_restore_missing_file() -> None:
    result = runner.invoke(cli_app, ["restore", "/tmp/this-file-does-not-exist-xyz.zip", "--force"])
    assert result.exit_code == 1


# ---- security hardening (added v0.11.2 after fan-out audit) ----


def test_redact_env_strips_api_key_values() -> None:
    """A backup must not leak API keys verbatim unless --include-secrets."""
    from jobhunt.cli import _redact_env

    env = (
        "JOBHUNT_JOOBLE_API_KEY=abc123secret\n"
        "JOBHUNT_REED_API_KEY=def456\n"
        "JOBHUNT_USER_LOCATION=London, UK\n"
    )
    redacted = _redact_env(env)
    assert "abc123secret" not in redacted
    assert "def456" not in redacted
    # Non-key values must survive.
    assert "London, UK" in redacted
    # Sentinel is present so a future restore can detect redaction.
    assert "__REDACTED_BY_BACKUP__" in redacted


def test_backup_default_redacts_secrets(tmp_path: Path) -> None:
    """The default backup should never carry plaintext keys."""
    # Seed an .env so the backup has something to redact.
    from jobhunt.config import settings

    env_path = settings.data_dir / ".env"
    original = env_path.read_text() if env_path.exists() else ""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "JOBHUNT_JOOBLE_API_KEY=DO_NOT_LEAK_THIS_PLEASE\n"
        "JOBHUNT_USER_LOCATION=Manchester\n"
    )
    try:
        out = tmp_path / "redacted.zip"
        result = runner.invoke(cli_app, ["backup", "-o", str(out)])
        assert result.exit_code == 0
        with zipfile.ZipFile(out) as z, z.open("jobhunt-backup.json") as f:
            payload = json.load(f)
        env_in_backup = payload.get("env", "")
        assert "DO_NOT_LEAK_THIS_PLEASE" not in env_in_backup
        assert "Manchester" in env_in_backup
        assert payload.get("secrets_included") is False
    finally:
        # Restore the prior .env contents so we don't disturb the dev box.
        env_path.write_text(original)


def test_restore_rejects_unknown_env_keys(tmp_path: Path) -> None:
    """A hostile backup that injects JOBHUNT_DATA_DIR or anything outside
    the allowlist must NOT take effect on restore."""
    from jobhunt.config import settings

    env_path = settings.data_dir / ".env"
    original_env = env_path.read_text() if env_path.exists() else ""

    bad = tmp_path / "hostile.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("jobhunt-backup.json", json.dumps({
            "schema": 1,
            "saved_searches": [],
            "cv_profile": None,
            "local_sources_yaml": "",
            "env": (
                "JOBHUNT_JOOBLE_API_KEY=legit-key\n"
                "JOBHUNT_DATA_DIR=/etc\n"          # hostile injection
                "JOBHUNT_WEBHOOK_URL=http://evil\n"  # hostile injection
            ),
            "secrets_included": True,
        }))
    try:
        result = runner.invoke(cli_app, ["restore", str(bad), "--force"])
        assert result.exit_code == 0
        written = env_path.read_text() if env_path.exists() else ""
        # Allowlisted key survives.
        assert "JOBHUNT_JOOBLE_API_KEY=legit-key" in written
        # Hostile keys must be filtered out.
        assert "JOBHUNT_DATA_DIR" not in written
        assert "JOBHUNT_WEBHOOK_URL" not in written
    finally:
        env_path.write_text(original_env)


def test_restore_drops_unknown_scraper_kinds(tmp_path: Path) -> None:
    """A hostile backup pointing local_sources at unknown scraper kinds
    (or attacker-controlled targets) should be dropped before write."""
    from jobhunt.config import settings

    ls_path = Path(settings.local_sources_file)
    original = ls_path.read_text() if ls_path.exists() else None

    bad = tmp_path / "hostile-sources.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("jobhunt-backup.json", json.dumps({
            "schema": 1,
            "saved_searches": [],
            "cv_profile": None,
            "local_sources_yaml": (
                "- source: greenhouse\n  board: legit-board\n"
                "- source: attacker-pwn\n  board: http://evil.com/exfil\n"
            ),
            "env": "",
            "secrets_included": True,
        }))
    try:
        result = runner.invoke(cli_app, ["restore", str(bad), "--force"])
        assert result.exit_code == 0
        written = ls_path.read_text() if ls_path.exists() else ""
        assert "greenhouse" in written  # allowed
        assert "attacker-pwn" not in written  # rejected
        assert "evil.com" not in written
    finally:
        if original is None:
            ls_path.unlink(missing_ok=True)
        else:
            ls_path.write_text(original)
