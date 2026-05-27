"""Salary estimation for jobs without published compensation.

Uses a two-layer approach:
1. Baseline ranges from public market data (BLS, aggregated surveys)
2. Refined ranges from our own collected salary data (improves over time)

Estimates are clearly flagged — they are NOT the employer's stated range.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Job

log = logging.getLogger(__name__)

# Baseline salary ranges (USD, annual) from publicly available aggregated data.
# Sources: US BLS (2024-2025), Levels.fyi aggregated, Stack Overflow surveys.
# These are conservative middle-of-market ranges for software/tech roles.
_BASELINE_USD: dict[str, tuple[int, int]] = {
    "intern":    (50_000, 90_000),
    "entry":     (65_000, 100_000),
    "junior":    (75_000, 115_000),
    "mid":       (100_000, 150_000),
    "senior":    (130_000, 200_000),
    "staff":     (170_000, 270_000),
    "principal": (200_000, 350_000),
    "lead":      (140_000, 220_000),
    "unknown":   (80_000, 150_000),
}

# Region multipliers relative to US market.
_REGION_MULTIPLIER: dict[str, float] = {
    "us":     1.0,
    "uk":     0.70,
    "eu":     0.65,
    "canada": 0.75,
    "remote": 0.90,
    "apac":   0.55,
    "latam":  0.40,
    "other":  0.60,
}

_REGION_CURRENCY: dict[str, str] = {
    "us": "USD", "uk": "GBP", "eu": "EUR", "canada": "CAD",
    "remote": "USD", "apac": "USD", "latam": "USD", "other": "USD",
}


@dataclass(slots=True)
class SalaryEstimate:
    """An estimated salary range, clearly marked as not from the employer."""

    min_salary: int
    max_salary: int
    currency: str
    confidence: str  # "high" (from our data, n>=10), "medium" (n>=3), "low" (baseline)


def infer_region(location: str) -> str:
    """Infer a broad region from the location string."""
    loc = location.lower()

    us_signals = (
        "united states", ", us", "usa", "new york", "san francisco",
        "california", "seattle", "austin", "boston", "chicago",
        "los angeles", "denver", "miami", "dallas", "atlanta",
        "washington", "virginia", "texas", "colorado", "massachusetts",
        ", ca", ", ny", ", wa", ", tx", ", il", ", ma", ", co",
        ", ga", ", fl", ", nc", ", pa", ", oh", ", mn", ", az",
        ", or", ", va", ", md", ", dc",
    )
    if any(s in loc for s in us_signals):
        return "us"

    uk_signals = (
        "united kingdom", ", uk", "london", "manchester", "birmingham",
        "edinburgh", "bristol", "cambridge", "oxford", "leeds",
    )
    if any(s in loc for s in uk_signals):
        return "uk"

    ca_signals = (
        "canada", "toronto", "vancouver", "montreal", "ottawa",
        ", on", ", bc", ", qc", ", ab",
    )
    if any(s in loc for s in ca_signals):
        return "canada"

    eu_signals = (
        "germany", "france", "netherlands", "spain", "italy",
        "berlin", "munich", "paris", "amsterdam", "dublin",
        "stockholm", "copenhagen", "zurich", "vienna", "warsaw",
        "prague", "lisbon", "barcelona", "europe",
    )
    if any(s in loc for s in eu_signals):
        return "eu"

    apac_signals = (
        "india", "singapore", "japan", "australia", "korea",
        "bangalore", "mumbai", "tokyo", "sydney", "melbourne",
    )
    if any(s in loc for s in apac_signals):
        return "apac"

    latam_signals = ("brazil", "mexico", "argentina", "colombia", "chile")
    if any(s in loc for s in latam_signals):
        return "latam"

    remote_signals = ("remote", "anywhere", "worldwide", "distributed", "global")
    if any(s in loc for s in remote_signals):
        return "remote"

    return "other"


def compute_ranges_from_db(session: Session) -> dict[tuple[str, str], tuple[int, int, int]]:
    """Compute median salary ranges from our own collected data, by (level, region).

    Returns {(level, region): (median_min, median_max, sample_count)}.
    Only includes combos with at least 3 data points.
    """
    rows = session.execute(
        select(Job.level, Job.location, Job.salary_min, Job.salary_max)
        .where(Job.salary_min.is_not(None))
        .where(Job.salary_max.is_not(None))
        .where(Job.salary_min > 10_000)
        .where(Job.salary_max < 1_000_000)
    ).all()

    from collections import defaultdict
    buckets: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for level, location, smin, smax in rows:
        region = infer_region(location or "")
        buckets[(level, region)].append((smin, smax))

    result: dict[tuple[str, str], tuple[int, int, int]] = {}
    for key, pairs in buckets.items():
        if len(pairs) < 3:
            continue
        mins = sorted(p[0] for p in pairs)
        maxs = sorted(p[1] for p in pairs)
        mid = len(mins) // 2
        result[key] = (mins[mid], maxs[mid], len(pairs))

    return result


def estimate_salary(
    level: str,
    location: str,
    db_ranges: dict[tuple[str, str], tuple[int, int, int]] | None = None,
) -> SalaryEstimate:
    """Estimate a salary range for a job based on level and location.

    Uses our own collected data when available (higher confidence),
    falls back to public baseline ranges (lower confidence).
    """
    region = infer_region(location)
    currency = _REGION_CURRENCY.get(region, "USD")

    # Try our own data first.
    if db_ranges:
        key = (level, region)
        if key in db_ranges:
            med_min, med_max, n = db_ranges[key]
            conf = "high" if n >= 10 else "medium"
            return SalaryEstimate(med_min, med_max, currency, conf)
        # Fall back to same level, any region.
        for r in _REGION_MULTIPLIER:
            if (level, r) in db_ranges:
                med_min, med_max, n = db_ranges[(level, r)]
                mult = _REGION_MULTIPLIER.get(region, 0.6) / _REGION_MULTIPLIER.get(r, 1.0)
                return SalaryEstimate(
                    int(med_min * mult), int(med_max * mult), currency, "medium",
                )

    # Fall back to baseline.
    base = _BASELINE_USD.get(level, _BASELINE_USD["unknown"])
    mult = _REGION_MULTIPLIER.get(region, 0.6)
    return SalaryEstimate(
        int(base[0] * mult), int(base[1] * mult), currency, "low",
    )
