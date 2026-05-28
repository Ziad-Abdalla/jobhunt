"""Fetch bug bounty program data from bounty-targets-data (GitHub).

Each upstream provider exposes a slightly different schema. We extract only
the fields we can quote directly — minimum/maximum payouts, whether cash is
on the table, and the program's submission state. We never *estimate*
rewards or difficulty: the user explicitly wants accuracy-first display, so
unknown fields stay unknown.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
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
    """A single bug bounty program.

    Reward fields are populated only when the upstream provider lists a
    concrete value. We never compose synthetic ranges.
    """

    name: str
    url: str
    platform: str
    domains: list[str] = field(default_factory=list)
    # Optional, only set when upstream actually publishes the value.
    min_bounty: int | None = None
    max_bounty: int | None = None
    currency: str = ""
    # 'cash' (offers real bounties), 'swag' (T-shirts / kudos), 'unknown'.
    pays: str = "unknown"
    # 'open', 'closed', 'invite_only', or '' when not published.
    state: str = ""
    # HackerOne-only signals — useful for hunters picking active programs.
    response_efficiency_pct: int | None = None
    avg_days_to_resolve: int | None = None


def _cache_path() -> Path:
    """Cache bounty data in the data directory."""
    return settings.data_dir / "bounties.json"


def _coerce_int(val: object) -> int | None:
    """Best-effort int coercion. Returns None when value is missing / invalid.

    Handles both raw numbers (YesWeHack/Bugcrowd) and Intigriti's
    ``{value, currency}`` wrapper.
    """
    if val is None:
        return None
    if isinstance(val, dict):
        val = val.get("value")
    try:
        i = int(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return i if i >= 0 else None


def _currency_of(val: object, default: str = "") -> str:
    """Extract the currency code if upstream uses a structured payload."""
    if isinstance(val, dict):
        cur = val.get("currency")
        if isinstance(cur, str):
            return cur
    return default


def _extract_domains(targets: object) -> list[str]:
    """Pull the in-scope asset identifiers out of the upstream targets blob."""
    if not isinstance(targets, dict):
        return []
    in_scope = targets.get("in_scope", []) or []
    domains: list[str] = []
    if isinstance(in_scope, list):
        for t in in_scope:
            if not isinstance(t, dict):
                continue
            asset = t.get("asset_identifier") or t.get("endpoint") or ""
            if isinstance(asset, str) and asset and "." in asset:
                domains.append(asset)
    return domains[:10]


def _parse_hackerone(entry: dict) -> BountyProgram | None:
    name = entry.get("name") or entry.get("handle")
    if not name:
        return None
    offers_bounties = bool(entry.get("offers_bounties"))
    offers_swag = bool(entry.get("offers_swag"))
    pays = "cash" if offers_bounties else ("swag" if offers_swag else "unknown")
    resp_eff = entry.get("response_efficiency_percentage")
    try:
        resp_eff_int: int | None = int(resp_eff) if resp_eff is not None else None
    except (TypeError, ValueError):
        resp_eff_int = None
    avg_days = entry.get("average_time_to_report_resolved")
    try:
        avg_days_int: int | None = int(avg_days) if avg_days is not None else None
    except (TypeError, ValueError):
        avg_days_int = None
    return BountyProgram(
        name=str(name),
        url=str(entry.get("url") or ""),
        platform="hackerone",
        domains=_extract_domains(entry.get("targets")),
        pays=pays,
        state=str(entry.get("submission_state") or ""),
        response_efficiency_pct=resp_eff_int,
        avg_days_to_resolve=avg_days_int,
    )


def _parse_bugcrowd(entry: dict) -> BountyProgram | None:
    name = entry.get("name")
    if not name:
        return None
    max_payout = _coerce_int(entry.get("max_payout"))
    pays = "cash" if max_payout and max_payout > 0 else "unknown"
    return BountyProgram(
        name=str(name),
        url=str(entry.get("url") or ""),
        platform="bugcrowd",
        domains=_extract_domains(entry.get("targets")),
        max_bounty=max_payout,
        currency="USD" if max_payout else "",
        pays=pays,
    )


def _parse_intigriti(entry: dict) -> BountyProgram | None:
    name = entry.get("name")
    if not name:
        return None
    min_b = _coerce_int(entry.get("min_bounty"))
    max_b = _coerce_int(entry.get("max_bounty"))
    currency = _currency_of(entry.get("max_bounty")) or _currency_of(entry.get("min_bounty"))
    pays = "cash" if (min_b or max_b) else "unknown"
    return BountyProgram(
        name=str(name),
        url=str(entry.get("url") or ""),
        platform="intigriti",
        domains=_extract_domains(entry.get("targets")),
        min_bounty=min_b,
        max_bounty=max_b,
        currency=currency,
        pays=pays,
        state=str(entry.get("status") or ""),
    )


def _parse_yeswehack(entry: dict) -> BountyProgram | None:
    name = entry.get("name")
    if not name:
        return None
    min_b = _coerce_int(entry.get("min_bounty"))
    max_b = _coerce_int(entry.get("max_bounty"))
    pays = "cash" if (min_b or max_b) else "unknown"
    return BountyProgram(
        name=str(name),
        url=str(entry.get("id") and f"https://yeswehack.com/programs/{entry['id']}" or ""),
        platform="yeswehack",
        domains=_extract_domains(entry.get("targets")),
        min_bounty=min_b,
        max_bounty=max_b,
        currency="EUR",
        pays=pays,
        state="closed" if entry.get("disabled") else "open",
    )


_PARSERS = {
    "hackerone": _parse_hackerone,
    "bugcrowd": _parse_bugcrowd,
    "intigriti": _parse_intigriti,
    "yeswehack": _parse_yeswehack,
}


def fetch_programs() -> list[BountyProgram]:
    """Fetch all bounty programs from GitHub. Caches locally."""
    programs: list[BountyProgram] = []
    cache = _cache_path()

    for platform, url in _SOURCES.items():
        try:
            resp = httpx.get(url, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("bounty fetch failed for %s: %s", platform, exc)
            continue

        parser = _PARSERS[platform]
        for entry in data:
            if not isinstance(entry, dict):
                continue
            try:
                prog = parser(entry)
            except Exception as exc:  # noqa: BLE001
                log.debug("bounty parse failed for %s: %s", platform, exc)
                prog = None
            if prog is not None:
                programs.append(prog)

    programs.sort(key=lambda p: p.name.lower())

    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps([asdict(p) for p in programs], indent=2))
    except OSError:
        pass

    return programs


def load_cached_programs() -> list[BountyProgram]:
    """Load from cache if available. Tolerates older cache schemas."""
    cache = _cache_path()
    if not cache.exists():
        return []
    try:
        data = json.loads(cache.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    out: list[BountyProgram] = []
    for d in data:
        if not isinstance(d, dict):
            continue
        # Older caches only had name/url/platform/domains — supply defaults.
        out.append(BountyProgram(
            name=d.get("name", ""),
            url=d.get("url", ""),
            platform=d.get("platform", ""),
            domains=list(d.get("domains") or []),
            min_bounty=d.get("min_bounty"),
            max_bounty=d.get("max_bounty"),
            currency=d.get("currency", ""),
            pays=d.get("pays", "unknown"),
            state=d.get("state", ""),
            response_efficiency_pct=d.get("response_efficiency_pct"),
            avg_days_to_resolve=d.get("avg_days_to_resolve"),
        ))
    return out
