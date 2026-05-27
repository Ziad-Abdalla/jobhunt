"""Fetch bug bounty program data from bounty-targets-data (GitHub)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from .config import settings

log = logging.getLogger(__name__)

_SOURCES = {
    "hackerone": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/hackerone_data.json",
    "bugcrowd": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/bugcrowd_data.json",
    "intigriti": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/intigriti_data.json",
    "yeswehack": "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/yeswehack_data.json",
}


@dataclass
class BountyProgram:
    """A single bug bounty program."""

    name: str
    url: str
    platform: str
    domains: list[str] = field(default_factory=list)


def _cache_path() -> Path:
    """Cache bounty data in the data directory."""
    return settings.data_dir / "bounties.json"


def fetch_programs() -> list[BountyProgram]:
    """Fetch all bounty programs from GitHub. Caches locally."""
    programs: list[BountyProgram] = []
    cache = _cache_path()

    for platform, url in _SOURCES.items():
        try:
            resp = httpx.get(url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()

            for entry in data:
                name = entry.get("name", "")
                if not name:
                    continue

                prog_url = entry.get("url", "")
                targets = entry.get("targets", {})
                in_scope = targets.get("in_scope", [])
                domains = []
                for t in in_scope:
                    asset = t.get("asset_identifier", "") or t.get("endpoint", "")
                    if asset and "." in asset:
                        domains.append(asset)

                programs.append(BountyProgram(
                    name=name,
                    url=prog_url,
                    platform=platform,
                    domains=domains[:10],
                ))
        except Exception as exc:  # noqa: BLE001
            log.warning("bounty fetch failed for %s: %s", platform, exc)

    programs.sort(key=lambda p: p.name.lower())

    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(
            [{"name": p.name, "url": p.url, "platform": p.platform, "domains": p.domains}
             for p in programs],
            indent=2,
        ))
    except OSError:
        pass

    return programs


def load_cached_programs() -> list[BountyProgram]:
    """Load from cache if available."""
    cache = _cache_path()
    if not cache.exists():
        return []
    try:
        data = json.loads(cache.read_text())
        return [
            BountyProgram(
                name=d["name"], url=d["url"],
                platform=d["platform"], domains=d.get("domains", []),
            )
            for d in data
        ]
    except (json.JSONDecodeError, KeyError, OSError):
        return []
