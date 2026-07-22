"""Full-auto apply policy (2026-07-22 spec): pure functions computing the
CV variant, derived per-job answers, draft annotations, and answer-bank
question normalization. Cowork-side helpers — stdlib only, no DB, no PII
storage — consumed by cowork_export and the queue endpoints.

Every rule here follows the house don't-guess ethos: an unresolvable
location or unknown remote status derives NOTHING rather than risking a
false work-authorization claim on a real application form.
"""

from __future__ import annotations

import re

# Egypt tokens: country (en + ar) + the city vocabulary the /local region
# map already recognizes for Egypt. Token-level matching (same
# normalization as scoring._has_token) so "Gizatown" never matches "giza".
EGYPT_TOKENS = (
    "egypt", "مصر",
    "cairo", "القاهرة", "new cairo", "nasr city", "heliopolis", "maadi",
    "giza", "الجيزة", "6th of october", "sheikh zayed",
    "alexandria", "الإسكندرية", "mansoura", "tanta",
)


def _norm_text(text: str) -> str:
    return " ".join(
        "".join(ch if ch.isalnum() else " " for ch in (text or "").lower()).split()
    )


def _has_token(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def is_egypt_location(location: str) -> bool:
    text = _norm_text(location)
    if not text:
        return False
    return any(_has_token(text, _norm_text(t)) for t in EGYPT_TOKENS)


def cv_variant_for_job(location: str, source: str) -> tuple[str, str]:
    """CV selection rule A (location-first). Returns (variant, reason)."""
    if source == "wuzzuf":
        return "egypt", "wuzzuf listings are Egypt-based"
    if is_egypt_location(location):
        return "egypt", f"location {location!r} resolves to Egypt"
    if _norm_text(location):
        return "remote", f"location {location!r} is not Egypt"
    return "remote", "location unresolved; defaulted to remote"


def derived_answers(location: str, remote: str, source: str) -> dict[str, str]:
    """Work-authorization answers derived from the job's location vs the
    owner's situation (Egypt-based). Unknown location AND unknown remote
    status -> {} (never guess on a legal question)."""
    if source == "wuzzuf" or is_egypt_location(location):
        return {"authorized_to_work": "yes", "needs_sponsorship": "no"}
    if remote == "remote":
        return {
            "authorized_to_work": "yes (remote contractor / EOR basis)",
            "needs_sponsorship": "no",
        }
    if _norm_text(location) and remote in ("onsite", "hybrid", "unknown"):
        return {"needs_sponsorship": "yes"}
    return {}


# Draft-annotation deny vocabulary (spec P-C item 3).
_SENSITIVE_RE = re.compile(
    r"salary|compensation|visa|sponsor|relocat|clearance|eeo|gender|race"
    r"|veteran|disability|cover.?letter",
    re.IGNORECASE,
)
_LONG_VALUE_CHARS = 200


def compute_annotations(
    fields_filled: dict,
    agent_notes: str,
    mapping_keys: set[str],
    profile_values: set[str],
) -> dict:
    """Annotations that make the universal approve tap a 3-second glance.

    - clean_mapping: no NON-BLANK value sits under a key outside the fixed
      field mapping (blank unknowns are contract-rule-2 behavior, not a
      violation).
    - unanswered: blank unmapped fields — the questions the approve form
      offers to the answer bank. A blank MAPPED field means the profile
      field itself is empty, which the bank must not shadow.
    - sensitive_fields: name matches the deny vocabulary, or a filled value
      longer than 200 chars that is not profile-derived (essay heuristic).
    - agent_flags: any agent note — the injection tripwire.
    """
    unmapped = [
        k for k, v in fields_filled.items()
        if k not in mapping_keys and str(v).strip()
    ]
    unanswered = [
        k for k, v in fields_filled.items()
        if k not in mapping_keys and not str(v).strip()
    ]
    sensitive = [
        k for k, v in fields_filled.items()
        if _SENSITIVE_RE.search(k)
        or (len(str(v)) > _LONG_VALUE_CHARS and str(v) not in profile_values)
    ]
    return {
        "clean_mapping": not unmapped,
        "unmapped_fields": unmapped,
        "agent_flags": bool(agent_notes.strip()),
        "sensitive_fields": sensitive,
        "unanswered": unanswered,
    }


def normalize_question(q: str) -> str:
    """Answer-bank key: lowercase, strip punctuation, collapse whitespace."""
    return " ".join(
        "".join(ch for ch in (q or "").lower() if ch.isalnum() or ch.isspace()).split()
    )
