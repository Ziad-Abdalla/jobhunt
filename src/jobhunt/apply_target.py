"""Classify a job's apply URL into an application-flow bucket (P5).

Buckets:
- ``ats`` — the URL is a hosted form on a known ATS (Greenhouse, Lever, …).
  NOTE for P6: 'ats' means "hosted ATS", NOT "auto-submittable". The bucket
  includes login-gated enterprise ATSs (Taleo, SuccessFactors, iCIMS,
  Workday, Oracle) where naive form submission would fail. Anything keying
  assisted submission MUST use the narrower ``AUTO_SUBMIT_DOMAINS`` subset.
- ``aggregator_relay`` — the URL lands on a job board / aggregator. This
  covers BOTH true one-hop relays (Remotive, Working Nomads — the listing
  links out to the real form) AND apply-on-platform boards (Wuzzuf,
  LinkedIn, Reed — you apply on the board itself, often behind a board
  account). P6 must NOT assume the relay is mechanically followable.
- ``company_site`` — anything else with a real host: an arbitrary,
  unclassified web form that needs a human or the Cowork actuator. A niche
  job board we don't know lands here too — conservative and correct for
  routing, even if the label reads "own site".
- ``unknown`` — no URL, no host, or a non-http(s) scheme.

Pure module: curated allow-lists + suffix matching only. No host-token
guessing ("careers." → company) — same don't-guess ethos as the P3/P4
extractors: a wrong 'ats' label would mis-route the P6 assisted-apply path.

Known precision/recall trade-off: companies that serve a Greenhouse form on
a custom careers domain (stripe.com, databricks.com …) classify as
``company_site``. That costs P6 auto-submit opportunity but never mislabels;
P6 may upgrade the bucket at fetch time by detecting the embedded ATS.
"""

from __future__ import annotations

import re
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
    "successfactors.eu",   # EU SuccessFactors tenants
    "fa.oraclecloud.com",  # Oracle Recruiting Cloud career sites
})

# The subset of _ATS_DOMAINS with simple, un-gated hosted forms that the P6
# assisted-apply path may target (owner decision: Greenhouse/Lever-class
# only, behind a human-confirm gate). Everything else in _ATS_DOMAINS is
# display/routing metadata, never an auto-submit license.
AUTO_SUBMIT_DOMAINS = frozenset({
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
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


# A classified host must be plain DNS. Anything else (percent-escapes,
# unicode, stray bytes) falls to 'unknown' — never a trusted bucket.
_DNS_HOST = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")


def classify_apply(url: str) -> ApplyTarget:
    """Classify an apply URL. Pure, cheap (one urlsplit), never raises."""
    if not url or not url.strip():
        return ApplyTarget("unknown", "")
    # WHATWG-align before parsing: browsers treat "\" as "/" in http(s)
    # URLs, urlsplit does not — without this, "https://evil.com\\@ats.com/"
    # classifies by the decoy host while the browser navigates to evil.com
    # (parser differential, caught in the P5 review).
    try:
        parts = urlsplit(url.strip().replace("\\", "/"))
    except ValueError:
        return ApplyTarget("unknown", "")
    if parts.scheme not in ("http", "https"):
        return ApplyTarget("unknown", "")
    host = (parts.hostname or "").lower().strip(".")
    if not _DNS_HOST.fullmatch(host):
        return ApplyTarget("unknown", "")
    domain = host.removeprefix("www.")
    if _matches(host, _ATS_DOMAINS):
        return ApplyTarget("ats", domain)
    if _matches(host, _AGGREGATOR_DOMAINS):
        return ApplyTarget("aggregator_relay", domain)
    return ApplyTarget("company_site", domain)
