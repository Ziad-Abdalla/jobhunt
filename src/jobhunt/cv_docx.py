"""Per-job tailored CV generation (2026-07-25 spec).

Applicant-side module — the scrape pipeline must NEVER import it
(tests/test_cowork_import_guard.py). Operates only on COPIES of the CV
docx masters; masters are never written.

Never-fabricate, by construction: content comes exclusively from the CV
itself plus owner-attested keywords (AttestedSkill rows, human-entered).
This module decides placement and order, never content.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

SEP = " · "                     # the CV's list separator
_EM_DASHES = ("—", "–")  # — and – : owner rule, never generated

# Section headings that delimit calibration parsing (lowercased, exact).
_HEADINGS = {
    "professional profile", "how i build with ai", "professional experience",
    "key projects", "technical skills", "education", "languages",
}

# A project header: "Name   (Stack · Stack · Stack)" — full line, no bullets.
_PROJECT_RE = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<stack>[^()]+)\)$")


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text or "").strip("_")
    return s or "CV"


def split_items(body: str) -> list[str]:
    return [s.strip() for s in body.split("·") if s.strip()]


def order_for_jd(items: list[str], jd: set[str]) -> list[str]:
    hits = [s for s in items if s.lower() in jd]
    rest = [s for s in items if s.lower() not in jd]
    return hits + rest


def merged_skills_body(
    body: str, attested: list[dict], label: str, jd: set[str]
) -> str:
    """One skills-category line's new body: attested keywords whose
    category_target is `label` inserted (display form), then JD-relevant
    items moved to the front (stable otherwise)."""
    items = split_items(body)
    have = {s.lower() for s in items}
    for a in attested:
        if a.get("category_target") == label and a["keyword_norm"] not in have:
            items.append(a.get("display") or a["keyword_norm"])
            have.add(a["keyword_norm"])
    return SEP.join(order_for_jd(items, jd))


def stack_addition(project_name: str, attested: list[dict], jd: set[str]) -> list[str]:
    """Attested keywords placed in this project AND asked for by the JD —
    stacks must not bloat on jobs that don't care."""
    return [
        (a.get("display") or a["keyword_norm"])
        for a in attested
        if project_name in (a.get("project_targets") or [])
        and a["keyword_norm"] in jd
    ]


def render_summary(template: str, top_skills: list[str]) -> str:
    out = template.replace("{skills}", ", ".join(top_skills))
    if any(ch in out for ch in _EM_DASHES):
        raise ValueError("em/en dash in generated summary (owner rule)")
    return out


def top_skills_for(
    jd_keywords: list[str], matched: list[str], attested: list[dict],
    limit: int = 3,
) -> list[str]:
    """The summary slot: first `limit` JD keywords the applicant actually
    has (CV-matched or attested), display-cased where attested."""
    display = {a["keyword_norm"]: (a.get("display") or a["keyword_norm"])
               for a in attested}
    have = {m.lower() for m in matched} | set(display)
    out: list[str] = []
    for kw in jd_keywords:
        if kw in have:
            out.append(display.get(kw, kw))
        if len(out) == limit:
            break
    return out
