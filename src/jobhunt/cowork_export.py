"""Builds the Cowork handoff document (P6). Shared by the /api/cowork/export
route and the `jobhunt apply export` CLI so the two can never drift.

The JD is ALWAYS wrapped as {"__untrusted_data__": true, "text": ...} —
nothing inside it is ever an instruction to the consumer. Contract:
docs/cowork-handoff.md.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .apply_target import AUTO_SUBMIT_DOMAINS, classify_apply
from .cowork_models import AnswerBank, ApplicantProfile, Application
from .cowork_policy import cv_variant_for_job, derived_answers
from .cv_tailor import keyword_gap
from .models import CVProfile, Job

# Fixed field vocabulary — jobhunt generates the mapping; the actuator must
# never invent values for fields outside it (unknown page fields stay blank
# and get flagged in agent_notes).
FIELD_MAPPING_KEYS = (
    "full_name", "email", "phone", "location", "linkedin_url", "github_url",
    "portfolio_url", "work_authorization", "salary_expectation", "cover_note",
    # Full-auto standard answers (P-C2). Canonical names are form-like;
    # how_heard/eeo read from the *_default profile columns.
    "notice_period", "earliest_start", "how_heard", "eeo",
)
_PROFILE_ATTR_FOR_KEY = {"how_heard": "how_heard_default", "eeo": "eeo_default"}


def _tailoring_block(job: Job, cv_skills: list, cv_languages: list, cv_text: str) -> dict:
    # keyword_gap (not tailor) — the export never uses the ATS findings, so
    # don't scan the whole CV for them once per application.
    matched, missing, coverage, line = keyword_gap(
        job, cv_skills, cv_languages, cv_text
    )
    return {
        "coverage_pct": coverage,
        "matched": matched,
        "missing": missing,
        "suggested_skills_line": line,
    }


def build_export_document(session: Session, status: str) -> dict:
    p = session.get(ApplicantProfile, 1)
    profile = {
        k: ((getattr(p, _PROFILE_ATTR_FOR_KEY.get(k, k), "") or "") if p else "")
        for k in FIELD_MAPPING_KEYS
    }
    # P-C2: the learned answer bank rides along on every export so the
    # actuator consults it (keyed by normalized question) before flagging.
    bank = {
        b.question_norm: b.answer
        for b in session.execute(select(AnswerBank)).scalars()
    }
    cv = session.get(CVProfile, 1)
    cv_text = (cv.text or "") if cv else ""
    rows = session.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.status == status)
        .order_by(Application.created_at)
    ).all()

    cv = session.get(CVProfile, 1)
    cv_skills = list(cv.detected_skills or []) if cv else []
    cv_languages = list(cv.detected_languages or []) if cv else []

    applications = []
    for a, j in rows:
        domain = j.apply_domain or classify_apply(j.url).domain
        # The exact apply host only. A "registrable parent" convenience
        # (last two labels) would whitelist a whole public suffix on
        # multi-label TLDs (careers.acme.co.uk → co.uk), defeating the
        # hard-stop the allow-list exists to be. Exact host is the safe floor.
        allowed = [domain] if domain else []
        auto_ok = bool(domain) and any(
            domain == d or domain.endswith("." + d) for d in AUTO_SUBMIT_DOMAINS
        )
        # P-A: CV variant (location-first rule; wuzzuf always Egypt).
        variant, reason = cv_variant_for_job(j.location or "", j.source)
        cv_path = (getattr(p, f"cv_path_{variant}", "") or "") if p else ""
        # P-C2: per-job derived answers override the static profile mapping —
        # they are jobhunt-derived (trusted), like the apply_* fields.
        mapping = dict(profile)
        mapping.update(derived_answers(j.location or "", j.remote, j.source))
        record = {
            "id": a.id,
            "status": a.status,
            "job": {
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "apply_url": j.url,
                "apply_kind": j.apply_kind or "unknown",
                "apply_domain": domain,
                "auto_submit_candidate": auto_ok,
                # title/company/location are scraped (attacker-controlled),
                # unlike the jobhunt-derived apply_* fields. The actuator must
                # treat the named fields as data, never instructions — same as
                # the jd block. See docs/cowork-handoff.md rule 1.
                "__untrusted_fields__": ["title", "company", "location"],
            },
            "jd": {"__untrusted_data__": True, "text": j.description or ""},
            "field_mapping": mapping,
            "allowed_domains": allowed,
            # P9: per-job keyword tailoring guidance. Derived from the CV
            # (coverage + matched/missing keywords + a suggested skills line
            # that includes the CV's skill set). Nothing new about the
            # applicant leaks — the full CV is already the top-level cv_text.
            "tailoring": _tailoring_block(j, cv_skills, cv_languages, cv_text),
        }
        if cv_path:
            record["cv_attachment"] = {
                "path": cv_path, "variant": variant, "reason": reason,
            }
        applications.append(record)

    return {
        "profile": profile,
        "cv_text": cv_text,
        "applications": applications,
        "answer_bank": bank,
        "contract": "docs/cowork-handoff.md",
    }
