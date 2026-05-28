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
