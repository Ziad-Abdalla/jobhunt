"""In-UI source management for `local_sources.yaml`.

Reads default sources from `settings.sources_file` (read-only in the UI) and
merges them with user-editable entries from `settings.local_sources_file`.

All validation is server-side; never trust client input.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .config import settings
from .scrapers import SCRAPER_REGISTRY

# Allow letters, digits, underscore, slash, dot, dash. Workday boards look like
# "tenant/wd5/site" so the slash is intentional.
_BOARD_RE = re.compile(r"^[A-Za-z0-9_/.\-]{1,128}$")
# jsearch "boards" are search queries ("<query>|<location>"), so spaces, '|',
# and stack tokens like "c#"/"c++" are legal there — but nowhere else.
_QUERY_BOARD_SOURCES = {"jsearch"}
_QUERY_BOARD_RE = re.compile(r"^[A-Za-z0-9_/.\-|+# ]{1,128}$")
_MAX_COMPANY = 128


def _load_yaml_list(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or []
    if not isinstance(loaded, list):
        return []
    out: list[dict] = []
    for item in loaded:
        if isinstance(item, dict) and item.get("source") and item.get("board") is not None:
            out.append(
                {
                    "source": str(item.get("source")),
                    "board": str(item.get("board")),
                    "company": str(item.get("company") or ""),
                }
            )
    return out


def _write_yaml_list(path: Path, entries: list[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        if not entries:
            f.write("[]\n")
            return
        yaml.safe_dump(
            entries,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )


def read_local_sources() -> list[dict]:
    """Return entries from `local_sources.yaml` (empty list if missing)."""
    return _load_yaml_list(Path(settings.local_sources_file))


def _read_default_sources() -> list[dict]:
    return _load_yaml_list(Path(settings.sources_file))


def available_source_types() -> list[str]:
    """Sorted SCRAPER_REGISTRY keys for the dropdown."""
    return sorted(SCRAPER_REGISTRY.keys())


def _validate(source: str, board: str, company: str) -> tuple[str, str, str]:
    source = (source or "").strip()
    board = (board or "").strip()
    company = (company or "").strip()

    if source not in SCRAPER_REGISTRY:
        valid = ", ".join(sorted(SCRAPER_REGISTRY.keys()))
        raise ValueError(f"Unknown source type {source!r}. Valid: {valid}.")
    if not board:
        raise ValueError("Board slug is required.")
    if source in _QUERY_BOARD_SOURCES:
        if not _QUERY_BOARD_RE.match(board):
            raise ValueError(
                "JSearch search may only contain letters, digits, spaces and "
                "'|', '_', '/', '.', '-', '+', '#' (max 128 chars)."
            )
    elif not _BOARD_RE.match(board):
        raise ValueError(
            "Board slug may only contain letters, digits, '_', '/', '.', '-' "
            "(max 128 chars)."
        )
    if not company:
        raise ValueError("Company name is required.")
    if len(company) > _MAX_COMPANY:
        raise ValueError(f"Company name must be {_MAX_COMPANY} characters or fewer.")
    return source, board, company


def add_source(source: str, board: str, company: str) -> dict:
    """Validate and append a new entry to `local_sources.yaml`.

    Raises ValueError for invalid input or a duplicate (source, board).
    """
    source, board, company = _validate(source, board, company)

    existing = read_local_sources()
    defaults = _read_default_sources()

    for entry in (*existing, *defaults):
        if entry["source"] == source and entry["board"] == board:
            origin = "your sources" if entry in existing else "default sources"
            raise ValueError(
                f"{source}/{board} is already in {origin}."
            )

    saved = {"source": source, "board": board, "company": company}
    existing.append(saved)
    _write_yaml_list(Path(settings.local_sources_file), existing)
    return saved


def remove_source(source: str, board: str) -> bool:
    """Remove a matching entry from `local_sources.yaml`. Return True if removed."""
    source = (source or "").strip()
    board = (board or "").strip()
    if not source or not board:
        return False

    existing = read_local_sources()
    kept: list[dict] = []
    removed = False
    for entry in existing:
        if not removed and entry["source"] == source and entry["board"] == board:
            removed = True
            continue
        kept.append(entry)

    if removed:
        _write_yaml_list(Path(settings.local_sources_file), kept)
    return removed


def list_all_sources() -> list[dict[str, Any]]:
    """Return defaults + local entries tagged with origin."""
    out: list[dict[str, Any]] = []
    for entry in _read_default_sources():
        out.append({**entry, "origin": "default"})
    for entry in read_local_sources():
        out.append({**entry, "origin": "local"})
    return out
