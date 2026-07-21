"""Settings persistence: the data-dir .env saved by the Settings page must
actually load back into Settings (it silently never did before)."""

from __future__ import annotations

from pathlib import Path

from jobhunt.config import Settings


def test_env_file_loads_saved_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "JOBHUNT_JSEARCH_API_KEY=abc123\nJOBHUNT_USER_LOCATION=Egypt\n",
        encoding="utf-8",
    )
    s = Settings(_env_file=(str(env),))
    assert s.jsearch_api_key == "abc123"
    assert s.user_location == "Egypt"


def test_later_env_file_wins(tmp_path: Path) -> None:
    a = tmp_path / "a.env"
    b = tmp_path / "b.env"
    a.write_text("JOBHUNT_USER_LOCATION=UK\n", encoding="utf-8")
    b.write_text("JOBHUNT_USER_LOCATION=Egypt\n", encoding="utf-8")
    s = Settings(_env_file=(str(a), str(b)))
    assert s.user_location == "Egypt"
