"""Unit tests for jobhunt.sources_admin."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobhunt import sources_admin
from jobhunt.config import settings


@pytest.fixture
def local_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect settings.local_sources_file to a temp path."""
    target = tmp_path / "local_sources.yaml"
    monkeypatch.setattr(settings, "local_sources_file", target)
    return target


@pytest.fixture
def empty_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect settings.sources_file to a temp empty defaults file."""
    defaults = tmp_path / "sources.yaml"
    defaults.write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(settings, "sources_file", defaults)
    return defaults


def test_add_source_rejects_unknown_source_type(local_yaml: Path, empty_defaults: Path) -> None:
    with pytest.raises(ValueError, match="Unknown source type"):
        sources_admin.add_source("bogus_ats", "stripe", "Stripe")
    assert not local_yaml.exists()


def test_add_source_rejects_bad_board_chars(local_yaml: Path, empty_defaults: Path) -> None:
    with pytest.raises(ValueError, match="Board slug"):
        sources_admin.add_source("greenhouse", "bad slug!", "Test")
    with pytest.raises(ValueError, match="Board slug"):
        sources_admin.add_source("greenhouse", "x" * 200, "Test")
    with pytest.raises(ValueError, match="Board slug is required"):
        sources_admin.add_source("greenhouse", "", "Test")


def test_add_source_accepts_jsearch_query_board(local_yaml: Path, empty_defaults: Path) -> None:
    saved = sources_admin.add_source("jsearch", "software engineer|Egypt", "JSearch Egypt")
    assert saved["board"] == "software engineer|Egypt"
    # Aggregator labels are auto-parenthesized so they never override the
    # real employer names in refresh._persist.
    assert saved["company"] == "(JSearch Egypt)"
    saved = sources_admin.add_source("jsearch", "c# developer|remote", "(JSearch C#)")
    assert saved["board"] == "c# developer|remote"
    assert saved["company"] == "(JSearch C#)"  # already wrapped — left alone


def test_add_source_rejects_bad_jsearch_board(local_yaml: Path, empty_defaults: Path) -> None:
    with pytest.raises(ValueError, match="JSearch search"):
        sources_admin.add_source("jsearch", "query<script>", "Bad")
    with pytest.raises(ValueError, match="JSearch search"):
        sources_admin.add_source("jsearch", "x" * 200, "Bad")


def test_add_source_still_rejects_query_chars_for_slug_sources(
    local_yaml: Path, empty_defaults: Path
) -> None:
    with pytest.raises(ValueError, match="Board slug"):
        sources_admin.add_source("greenhouse", "software engineer|Egypt", "Bad")


def test_add_source_rejects_empty_company(local_yaml: Path, empty_defaults: Path) -> None:
    with pytest.raises(ValueError, match="Company"):
        sources_admin.add_source("greenhouse", "stripe", "")


def test_add_source_rejects_duplicate_local(local_yaml: Path, empty_defaults: Path) -> None:
    sources_admin.add_source("greenhouse", "stripe", "Stripe")
    with pytest.raises(ValueError, match="already in"):
        sources_admin.add_source("greenhouse", "stripe", "Stripe Duplicate")
    # Different source type with same board slug is fine.
    sources_admin.add_source("lever", "stripe", "Stripe-Lever")
    entries = sources_admin.read_local_sources()
    assert len(entries) == 2


def test_add_source_rejects_duplicate_against_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    defaults = tmp_path / "sources.yaml"
    defaults.write_text(
        "- {source: greenhouse, board: stripe, company: Stripe}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "sources_file", defaults)
    monkeypatch.setattr(settings, "local_sources_file", tmp_path / "local_sources.yaml")

    with pytest.raises(ValueError, match="already in default"):
        sources_admin.add_source("greenhouse", "stripe", "Stripe")


def test_add_then_remove_roundtrip(local_yaml: Path, empty_defaults: Path) -> None:
    saved = sources_admin.add_source("workday", "acme/wd5/jobs", "Acme")
    assert saved == {"source": "workday", "board": "acme/wd5/jobs", "company": "Acme"}
    assert local_yaml.exists()

    entries = sources_admin.read_local_sources()
    assert entries == [{"source": "workday", "board": "acme/wd5/jobs", "company": "Acme"}]

    all_entries = sources_admin.list_all_sources()
    assert {"source": "workday", "board": "acme/wd5/jobs", "company": "Acme", "origin": "local"} in all_entries

    assert sources_admin.remove_source("workday", "acme/wd5/jobs") is True
    assert sources_admin.read_local_sources() == []

    # Removing again is a no-op.
    assert sources_admin.remove_source("workday", "acme/wd5/jobs") is False


def test_available_source_types_sorted() -> None:
    types = sources_admin.available_source_types()
    assert types == sorted(types)
    assert "greenhouse" in types
    assert "workday" in types


def test_read_local_sources_returns_empty_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "local_sources_file", tmp_path / "does_not_exist.yaml")
    assert sources_admin.read_local_sources() == []
