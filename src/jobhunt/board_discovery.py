"""Board-discovery generator (P7): harvest ATS board slugs from public
GitHub company directories (remoteintech/remote-jobs, awesome-remote-job).

Offensive maintenance — pairs with the source-maintenance skill. It NEVER
writes into sources.yaml directly (the CLAUDE.md rule: `jobhunt doctor` must
verify a source before it ships). It writes candidates to a review file for
a human / the skill to doctor-check then merge.

These directories carry MENA-founded companies (Paymob, Instabug, Swvl,
Halan, …), so discovery widens Egypt + remote coverage as a side effect.
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger(__name__)

# ATS URL shapes → (source, slug). Anchored to the known apply hosts (the
# same domains apply_target classifies as 'ats'). Slug = the org token.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("greenhouse", re.compile(r"https?://(?:job-)?boards\.greenhouse\.io/([A-Za-z0-9_-]+)")),
    ("greenhouse", re.compile(r"https?://boards\.eu\.greenhouse\.io/([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"https?://jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_-]+)")),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)")),
    ("workable", re.compile(r"https?://apply\.workable\.com/([A-Za-z0-9_-]+)")),
    ("smartrecruiters", re.compile(r"https?://jobs\.smartrecruiters\.com/([A-Za-z0-9_-]+)")),
    ("recruitee", re.compile(r"https?://([A-Za-z0-9_-]+)\.recruitee\.com")),
]

# Path tokens that are never a real org slug.
_NOT_A_SLUG = frozenset({"jobs", "careers", "job", "o", "embed", "en", "www"})


def extract_board_slugs(text: str) -> list[dict]:
    """Extract (source, board) candidates from a blob of directory text.
    Deduped within the blob, order-stable."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for source, pat in _PATTERNS:
        for m in pat.finditer(text):
            board = m.group(1)
            if board.lower() in _NOT_A_SLUG:
                continue
            key = (source, board)
            if key in seen:
                continue
            seen.add(key)
            out.append({"source": source, "board": board})
    return out


def dedupe_against_existing(found: list[dict], existing: list[dict]) -> list[dict]:
    """Drop candidates already present in the current sources config
    (case-insensitive on the board slug)."""
    have = {
        (e.get("source"), str(e.get("board", "")).lower())
        for e in existing
    }
    return [
        f for f in found
        if (f["source"], f["board"].lower()) not in have
    ]


# Public GitHub directories (raw markdown). One fetch each, no auth.
DIRECTORY_URLS = (
    "https://raw.githubusercontent.com/remoteintech/remote-jobs/main/README.md",
    "https://raw.githubusercontent.com/lukasz-madon/awesome-remote-job/master/README.md",
)


def fetch_directories(urls: tuple[str, ...] = DIRECTORY_URLS) -> str:
    """Fetch + concatenate the directory sources. Best-effort per URL."""
    import httpx

    blobs: list[str] = []
    for url in urls:
        try:
            r = httpx.get(url, timeout=20.0, follow_redirects=True)
            if r.status_code // 100 == 2:
                blobs.append(r.text)
            else:
                log.warning("discover: %s returned %s", url, r.status_code)
        except Exception as exc:  # noqa: BLE001
            log.warning("discover: %s failed: %s", url, exc)
    return "\n".join(blobs)


def discover(existing: list[dict], urls: tuple[str, ...] = DIRECTORY_URLS) -> list[dict]:
    """End-to-end: fetch directories, extract slugs, dedupe against existing."""
    text = fetch_directories(urls)
    return dedupe_against_existing(extract_board_slugs(text), existing)
