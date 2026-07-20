"""Classify a job's apply URL into an application-flow bucket (P5).

Buckets:
- ``ats`` — the URL is a hosted form on a known ATS (Greenhouse, Lever, …):
  structured, predictable, the safest target for later assisted submission.
- ``aggregator_relay`` — the URL lands on a job board / aggregator listing;
  the real application target is one hop away.
- ``company_site`` — anything else with a real host: an arbitrary,
  unclassified web form that needs a human or the Cowork actuator. A niche
  job board we don't know lands here too — conservative and correct for
  routing, even if the label reads "own site".
- ``unknown`` — no URL, no host, or a non-http(s) scheme.

Pure module: curated allow-lists + suffix matching only. No host-token
guessing ("careers." → company) — same don't-guess ethos as the P3/P4
extractors: a wrong 'ats' label would mis-route the P6 assisted-apply path.
"""

from __future__ import annotations

from typing import NamedTuple
from urllib.parse import urlsplit

APPLY_KINDS = ("ats", "aggregator_relay", "company_site", "unknown")

# Hosted-application ATS platforms (matched as host == entry or
# host endswith "." + entry). Keep curated + verified — this table feeds
# the P6 assisted-apply routing, so precision beats recall.
_ATS_DOMAINS = frozenset({
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "recruitee.com",
    "myworkdayjobs.com",
    "bamboohr.com",
    "jobvite.com",
    "icims.com",
    "breezy.hr",
    "applytojob.com",   # JazzHR hosted apply
    "teamtailor.com",
    "personio.de",
    "personio.com",
    "join.com",
    "taleo.net",
    "successfactors.com",
})

# Job boards / aggregators: every board jobhunt scrapes plus the big
# generic boards a source may relay through.
_AGGREGATOR_DOMAINS = frozenset({
    # jobhunt's own sources
    "wuzzuf.net",
    "remotive.com",
    "workingnomads.com",
    "weworkremotely.com",
    "python.org",
    "arbeitnow.com",
    "arbeitsagentur.de",
    "himalayas.app",
    "jobicy.com",
    "remoteok.com",
    "themuse.com",
    "news.ycombinator.com",
    "reed.co.uk",
    "jooble.org",
    # big generic boards
    "indeed.com",
    "linkedin.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "stepstone.de",
    "xing.com",
    "totaljobs.com",
    "cv-library.co.uk",
    "talent.com",
})


class ApplyTarget(NamedTuple):
    kind: str
    domain: str


def _matches(host: str, table: frozenset[str]) -> bool:
    """True when host is an entry or a subdomain of an entry. Never a
    substring match — "boards.greenhouse.io.evil.com" must not count."""
    if host in table:
        return True
    return any(host.endswith("." + entry) for entry in table)


def classify_apply(url: str) -> ApplyTarget:
    """Classify an apply URL. Pure, cheap (one urlsplit), never raises."""
    if not url or not url.strip():
        return ApplyTarget("unknown", "")
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ApplyTarget("unknown", "")
    if parts.scheme not in ("http", "https"):
        return ApplyTarget("unknown", "")
    host = (parts.hostname or "").lower().strip(".")
    if not host or "." not in host:
        return ApplyTarget("unknown", "")
    domain = host.removeprefix("www.")
    if _matches(host, _ATS_DOMAINS):
        return ApplyTarget("ats", domain)
    if _matches(host, _AGGREGATOR_DOMAINS):
        return ApplyTarget("aggregator_relay", domain)
    return ApplyTarget("company_site", domain)
