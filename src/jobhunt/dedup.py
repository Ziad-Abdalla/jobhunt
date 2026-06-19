from __future__ import annotations

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def normalize_title(title: str) -> str:
    """Strip seniority/department noise so 'Sr. Backend Engineer (Remote)' == 'Backend Engineer'.

    Conservative: only strips noise we are confident about. Real differences in the
    job's role are preserved.
    """
    t = title.lower()
    t = re.sub(r"\(.*?\)", " ", t)              # drop parenthetical noise
    t = re.sub(r"\[.*?\]", " ", t)
    # Strip only formatting noise — NOT staff/principal/lead, which denote
    # genuinely distinct roles (collapsing them loses real listings).
    t = re.sub(
        r"\b(sr\.?|senior|jr\.?|junior|intern|internship|new grad|entry[- ]level)\b",
        " ",
        t,
    )
    t = re.sub(r"\b(remote|hybrid|onsite|on[- ]site)\b", " ", t)
    t = _NON_ALNUM.sub(" ", t)
    t = _WHITESPACE.sub(" ", t).strip()
    return t


def normalize_company(company: str) -> str:
    c = company.lower()
    c = re.sub(r"\b(inc|llc|ltd|gmbh|sa|sas|plc|corp|corporation)\b\.?", "", c)
    c = _NON_ALNUM.sub(" ", c)
    return _WHITESPACE.sub(" ", c).strip()


# Trailing country qualifier on a city ("London, UK" / "London, England").
# Stripped before fingerprinting so the same job from different sources collapses
# to one row instead of inflating the count.
_COUNTRY_SUFFIX = re.compile(
    r",\s*(uk|u\.k\.|united kingdom|great britain|gb|england|scotland|wales|"
    r"usa|u\.s\.?a?\.?|united states|deutschland|germany)\.?\s*$",
    re.I,
)


def normalize_location(location: str) -> str:
    loc = _COUNTRY_SUFFIX.sub("", location.lower().strip())
    loc = _NON_ALNUM.sub(" ", loc)
    return _WHITESPACE.sub(" ", loc).strip()


def fingerprint(company: str, title: str, location: str) -> str:
    key = f"{normalize_company(company)}|{normalize_title(title)}|{normalize_location(location)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def description_hash(text: str) -> str:
    """Hash a normalized form of the JD for near-duplicate detection across sources."""
    norm = _NON_ALNUM.sub(" ", text.lower())
    norm = _WHITESPACE.sub(" ", norm).strip()
    # Use a chunk — full hash is overkill and full text is sometimes truncated by sources.
    return hashlib.sha256(norm[:4000].encode("utf-8")).hexdigest()[:32]
