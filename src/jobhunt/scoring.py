"""Simple, transparent ranking score so 'Top N' can be meaningful by default.

Designed for filter UIs where 'sort by relevance' should reward recent, well-described,
clearly-tagged postings — not a black-box ML score the user can't reason about.
"""

from __future__ import annotations

import functools
from datetime import UTC, datetime


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
            posted_at = posted_at.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - posted_at).total_seconds() / 86400
        score += max(0.0, 1.0 - age_days / 30.0)

    # Description quality: longer JD is usually a sign the company actually wrote it.
    desc_len = len(description)
    score += min(1.0, desc_len / 2000.0)

    # Tagged signals — caps avoid one keyword-spamming source dominating.
    score += min(1.0, len(skills) / 8.0)
    score += min(1.0, len(languages) / 4.0)

    return round(score, 4)


# --- P4: reachability -------------------------------------------------------
# Ranking weight per geo_restrict bucket, given the user's own region.
# Stored cv_match stays a PURE fit score; reachability is applied only at
# rank time (see filters._apply) so the match-% badge never lies.

CV_BLEND_WEIGHT = 1.5      # perfect CV match multiplies quality score by 2.5x
UNREACHABLE_WEIGHT = 0.35  # demote, never hide: extractor may false-positive

GEO_BUCKETS = (
    "us-only", "uk-only", "eu-only",
    "restricted-other", "unrestricted", "unknown",
)

_US_TOKENS = ("united states", "u s a", "u s", "usa", "us")
_UK_TOKENS = (
    "united kingdom", "northern ireland", "great britain", "britain",
    "england", "scotland", "wales", "uk", "gb",
)
# EU-27 (English + common native names) plus EEA members — "EU only" postings
# routinely say EU/EEA, so Norway/Iceland/Liechtenstein count as reachable.
_EU_TOKENS = (
    "austria", "belgium", "bulgaria", "croatia", "cyprus", "czechia",
    "czech republic", "denmark", "estonia", "finland", "france", "germany",
    "greece", "hungary", "ireland", "italy", "latvia", "lithuania",
    "luxembourg", "malta", "netherlands", "poland", "portugal", "romania",
    "slovakia", "slovenia", "spain", "sweden",
    "deutschland", "österreich", "oesterreich", "españa", "espana",
    "italia", "polska", "nederland", "belgië", "belgie", "belgique",
    "sverige", "suomi", "danmark", "česko", "cesko", "slovensko",
    "hrvatska", "magyarország", "magyarorszag", "éire", "eire",
    "norway", "norge", "iceland", "liechtenstein",
)
# Recognized non-US/UK/EU countries -> 'other' (all three X-only buckets are
# unreachable). Deliberately conservative: anything NOT in one of these lists
# (e.g. "New York, NY", "Atlantis") returns '' so ranking never penalizes on a
# guess — same don't-guess ethos as the P3 extractor. "Georgia" is omitted on
# purpose (US state / country homograph).
_OTHER_TOKENS = (
    "egypt", "مصر",
    "australia", "new zealand", "canada",
    "india", "pakistan", "bangladesh", "sri lanka", "nepal",
    "china", "japan", "south korea", "korea", "singapore", "hong kong",
    "taiwan", "philippines", "indonesia", "vietnam", "thailand", "malaysia",
    "turkey", "türkiye", "turkiye", "ukraine", "serbia", "bosnia",
    "albania", "moldova", "belarus", "russia", "switzerland",
    "brazil", "argentina", "chile", "colombia", "peru", "mexico", "uruguay",
    "south africa", "nigeria", "kenya", "ghana", "ethiopia",
    "morocco", "tunisia", "algeria", "libya", "sudan",
    "jordan", "lebanon", "iraq", "israel", "palestine",
    "saudi arabia", "united arab emirates", "uae", "qatar", "kuwait",
    "bahrain", "oman", "yemen",
)


def _has_token(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


@functools.lru_cache(maxsize=8)
def home_region_from_location(user_location: str) -> str:
    """Map the JOBHUNT_USER_LOCATION setting to 'us'|'uk'|'eu'|'other'|''.

    Token/phrase match on country names ("Cairo, Egypt", "Berlin, Germany").
    UK is checked before EU so "Northern Ireland" never matches "Ireland".
    Empty OR unrecognized input -> '' (unknown: never penalize) — "New York,
    NY" must not demote us-only jobs for a US user; only a *recognized*
    non-US/UK/EU country returns 'other'.
    """
    text = " ".join(
        "".join(ch if ch.isalnum() else " " for ch in (user_location or "").lower()).split()
    )
    if not text:
        return ""
    if any(_has_token(text, t) for t in _US_TOKENS):
        return "us"
    if any(_has_token(text, t) for t in _UK_TOKENS):
        return "uk"
    if any(_has_token(text, t) for t in _EU_TOKENS):
        return "eu"
    if any(_has_token(text, t) for t in _OTHER_TOKENS):
        return "other"
    return ""


def reachability_weights(home_region: str) -> dict[str, float]:
    """Rank weight for every geo_restrict bucket, given the user's region.

    Only a *known mismatch* is penalized: an 'X-only' bucket when the user's
    region is known and != X. 'unknown' (most jobs — the extractor is
    deliberately conservative) and 'restricted-other' (could be the user's
    own country) always stay 1.0.
    """
    weights = {bucket: 1.0 for bucket in GEO_BUCKETS}
    if not home_region:
        return weights
    for bucket, region in (("us-only", "us"), ("uk-only", "uk"), ("eu-only", "eu")):
        if home_region != region:
            weights[bucket] = UNREACHABLE_WEIGHT
    return weights
