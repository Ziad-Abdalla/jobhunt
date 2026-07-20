"""Applicant-PII models for the Cowork handoff (P6).

These live in their OWN module — never in models.py — so the structural
PII-locality gate stays greppable: the scrape pipeline (scrapers/,
refresh.py, extract.py, dedup.py, apply_target.py, scoring.py,
salary_estimator.py) must NEVER import this module. Enforced by
tests/test_cowork_import_guard.py.

Minimal-PII policy (owner decision 2026-07-20): local plaintext SQLite in
data_dir, loopback-only access, and NO passport / national-ID fields —
the schema deliberately has nowhere to put them.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ApplicantProfile(Base):
    """Single-row table (id=1), cloned from the CVProfile pattern.

    Everything here stays on this machine: /profile and /api/cowork/* are
    loopback-gated, and the export endpoint additionally requires the
    default-OFF JOBHUNT_COWORK_EXPORT toggle.
    """

    __tablename__ = "applicant_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(256), default="")
    email: Mapped[str] = mapped_column(String(256), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    location: Mapped[str] = mapped_column(String(256), default="")
    linkedin_url: Mapped[str] = mapped_column(String(512), default="")
    github_url: Mapped[str] = mapped_column(String(512), default="")
    portfolio_url: Mapped[str] = mapped_column(String(512), default="")
    work_authorization: Mapped[str] = mapped_column(String(512), default="")
    salary_expectation: Mapped[str] = mapped_column(String(128), default="")
    cover_note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


APPLICATION_STATUSES = (
    "queued",      # human queued the job on /apply (gate 1)
    "drafted",     # Cowork reported what it WOULD fill (not a submit)
    "approved",    # human approved the draft (gate 2)
    "submitting",  # actuator CLAIMED the approved app (excluded from the
                   # approved poll) — a lock that stops a crash-then-rerun
                   # double-submit
    "submitted",   # actuator submitted + posted the receipt (msg-id only)
    "rejected",    # human rejected — re-queueable
    "failed",      # actuator failure (e.g. off-allowlist redirect) — re-queueable
)

# Server-enforced transitions. Nothing reaches 'submitted' without passing
# BOTH human gates (queue →queued, approve drafted→approved) AND a claim
# (approved→submitting). rejected/failed are recoverable: the human can
# re-queue. drafted→drafted lets the actuator improve a draft in place.
#
# submitting has NO path back to approved: a claimed (in-flight) application
# must NOT be un-claimed, or a second actuator could legitimately re-claim
# and double-submit. A stuck claim recovers via submitting→failed (the
# actuator or a human reports failure), then the human re-queues from failed.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"drafted", "rejected", "failed"}),
    "drafted": frozenset({"drafted", "approved", "rejected", "failed"}),
    "approved": frozenset({"submitting", "drafted", "rejected", "failed"}),
    "submitting": frozenset({"submitted", "failed"}),
    "submitted": frozenset(),
    "rejected": frozenset({"queued"}),
    "failed": frozenset({"queued"}),
}

# Statuses from which the human "Queue" button re-activates an application.
TERMINAL_REQUEUEABLE = frozenset({"rejected", "failed"})


def can_transition(current: str, new: str) -> bool:
    return new in _TRANSITIONS.get(current, frozenset())


class Application(Base):
    """One queued application per job. State machine above."""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    # Cowork's draft report: {canonical_or_page_field: value}. Rendered in
    # the /apply queue view so a human sees exactly what would be submitted
    # (the audit surface that makes prompt-injected drafts visible).
    fields_filled: Mapped[dict] = mapped_column(JSON, default=dict)
    agent_notes: Mapped[str] = mapped_column(Text, default="")
    # Post-hoc proof only — a mail/ATS message id. Never a credential.
    receipt: Mapped[str] = mapped_column(String(512), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
