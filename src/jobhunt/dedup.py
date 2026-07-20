from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
# Keep letters/digits in ANY script — with the old ASCII-only class, an
# all-Arabic title normalized to "" and every same-company Arabic job collided.
# \w is Unicode-aware; underscores (part of \w) are folded to spaces after.
_NON_ALNUM = re.compile(r"[^\w ]+")
_UNDERSCORE = re.compile(r"_+")


def normalize_title(title: str) -> str:
    """Strip seniority/department noise so 'Sr. Backend Engineer (Remote)' == 'Backend Engineer'.

    Conservative: only strips noise we are confident about. Real differences in the
    job's role are preserved.
    """
    t = unicodedata.normalize("NFC", title).lower()
    t = re.sub(r"\(.*?\)", " ", t)              # drop parenthetical noise
    t = re.sub(r"\[.*?\]", " ", t)
    t = re.sub(
        r"\b(sr\.?|senior|jr\.?|junior|staff|principal|lead|"
        r"intern|internship|new grad|entry[- ]level)\b",
        " ",
        t,
    )
    t = re.sub(r"\b(remote|hybrid|onsite|on[- ]site)\b", " ", t)
    t = _NON_ALNUM.sub(" ", t)
    t = _UNDERSCORE.sub(" ", t)
    t = _WHITESPACE.sub(" ", t).strip()
    return t


def normalize_company(company: str) -> str:
    c = unicodedata.normalize("NFC", company).lower()
    c = re.sub(r"\b(inc|llc|ltd|gmbh|sa|sas|plc|corp|corporation)\b\.?", "", c)
    c = _NON_ALNUM.sub(" ", c)
    c = _UNDERSCORE.sub(" ", c)
    return _WHITESPACE.sub(" ", c).strip()


# Pure-remote location phrases (normalized) that all mean the same thing. Collapsing
# them stops one remote opening arriving from several aggregators as "Remote" /
# "Worldwide" / "Anywhere" / "100% Remote" from splitting into several DB rows.
# Region-qualified remotes ("Remote, US", "Remote — Europe") are deliberately NOT in
# this set: they carry a geography we must keep distinct.
_REMOTE_SYNONYMS = frozenset({
    "remote", "anywhere", "worldwide", "global", "distributed",
    "fully remote", "remote worldwide", "remote global", "remote anywhere",
    "anywhere in the world", "fully distributed", "remote first",
    "remote friendly", "work from home", "wfh", "100 remote", "100 remote worldwide",
})


def normalize_location(location: str) -> str:
    loc = unicodedata.normalize("NFC", location).lower()
    loc = _NON_ALNUM.sub(" ", loc)
    loc = _UNDERSCORE.sub(" ", loc)
    loc = _WHITESPACE.sub(" ", loc).strip()
    if loc in _REMOTE_SYNONYMS:
        return "remote"
    return loc


def fingerprint(company: str, title: str, location: str, salt: str = "") -> str:
    key = f"{normalize_company(company)}|{normalize_title(title)}|{normalize_location(location)}"
    if salt:
        # A salt keeps genuinely-distinct openings that share company/title/location
        # (e.g. two different reqs from the same source) from collapsing into one row.
        key = f"{key}|{salt}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def description_hash(text: str) -> str:
    """Hash a normalized form of the JD for near-duplicate detection across sources."""
    norm = _NON_ALNUM.sub(" ", text.lower())
    norm = _WHITESPACE.sub(" ", norm).strip()
    # Use a chunk — full hash is overkill and full text is sometimes truncated by sources.
    return hashlib.sha256(norm[:4000].encode("utf-8")).hexdigest()[:32]
