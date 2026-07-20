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
from .cowork_models import ApplicantProfile, Application
from .models import CVProfile, Job

# Fixed field vocabulary — jobhunt generates the mapping; the actuator must
# never invent values for fields outside it (unknown page fields stay blank
# and get flagged in agent_notes).
FIELD_MAPPING_KEYS = (
    "full_name", "email", "phone", "location", "linkedin_url", "github_url",
    "portfolio_url", "work_authorization", "salary_expectation", "cover_note",
)


def build_export_document(session: Session, status: str) -> dict:
    p = session.get(ApplicantProfile, 1)
    profile = {k: (getattr(p, k, "") or "") for k in FIELD_MAPPING_KEYS} if p \
        else {k: "" for k in FIELD_MAPPING_KEYS}
    cv = session.get(CVProfile, 1)
    cv_text = (cv.text or "") if cv else ""
    rows = session.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.status == status)
        .order_by(Application.created_at)
    ).all()

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
        applications.append({
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
            },
            "jd": {"__untrusted_data__": True, "text": j.description or ""},
            "field_mapping": dict(profile),
            "allowed_domains": allowed,
        })

    return {
        "profile": profile,
        "cv_text": cv_text,
        "applications": applications,
        "contract": "docs/cowork-handoff.md",
    }
