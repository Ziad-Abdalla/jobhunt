"""Simple, transparent ranking score so 'Top N' can be meaningful by default.

Designed for filter UIs where 'sort by relevance' should reward recent, well-described,
clearly-tagged postings — not a black-box ML score the user can't reason about.
"""

from __future__ import annotations

from datetime import datetime, timezone


def score_job(
    *,
    posted_at: datetime | None,
    description: str,
    skills: list[str],
    languages: list[str],
) -> float:
    score = 0.0

    # Recency: 1.0 today, 0 at 30 days, linear.
    if posted_at:
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - posted_at).total_seconds() / 86400
        score += max(0.0, 1.0 - age_days / 30.0)

    # Description quality: longer JD is usually a sign the company actually wrote it.
    desc_len = len(description)
    score += min(1.0, desc_len / 2000.0)

    # Tagged signals — caps avoid one keyword-spamming source dominating.
    score += min(1.0, len(skills) / 8.0)
    score += min(1.0, len(languages) / 4.0)

    return round(score, 4)
