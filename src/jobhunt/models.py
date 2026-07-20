from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024))

    company: Mapped[str] = mapped_column(String(256), index=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    location: Mapped[str] = mapped_column(String(256), default="", index=True)

    remote: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    level: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    min_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    degree: Mapped[str] = mapped_column(String(16), default="unknown", index=True)
    employment_type: Mapped[str] = mapped_column(String(32), default="unknown", index=True)

    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(8), default="")
    salary_estimated: Mapped[bool] = mapped_column(Boolean, default=False)

    visa_sponsorship: Mapped[str] = mapped_column(String(32), default="unknown", index=True)

    # Coarse classification for the /local page: 'tech' | 'nontech' | 'other'.
    # Computed by extract.classify_category during persistence.
    category: Mapped[str] = mapped_column(String(16), default="other", index=True)

    # Geo-eligibility for remote roles (P3): us-only | uk-only | eu-only |
    # restricted-other | unrestricted | unknown. Computed by extract.extract_geo.
    geo_restrict: Mapped[str] = mapped_column(String(24), default="unknown", index=True)

    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages: Mapped[list[str]] = mapped_column(JSON, default=list)

    description: Mapped[str] = mapped_column(Text, default="")
    description_hash: Mapped[str] = mapped_column(String(64), default="")

    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    score: Mapped[float] = mapped_column(default=0.0, index=True)

    # When a CV is loaded, this gets filled in with cosine similarity (0..1).
    cv_match: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    __table_args__ = (
        Index("ix_jobs_company_title", "company", "title"),
        Index("ix_jobs_remote_level", "remote", "level"),
        Index("ix_jobs_etype_level", "employment_type", "level"),
        Index("ix_jobs_score_posted", "score", "posted_at"),
        Index("ix_jobs_location_level", "location", "level"),
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    board: Mapped[str] = mapped_column(String(128), default="", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    jobs_seen: Mapped[int] = mapped_column(Integer, default=0)
    jobs_added: Mapped[int] = mapped_column(Integer, default=0)
    jobs_removed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class SavedSearch(Base):
    """A named filter set that the user wants alerts for."""

    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    # Serialized JobQuery (everything except limit/offset/sort).
    query_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # IDs of jobs we've already alerted on, so we don't double-notify.
    notified_job_ids: Mapped[list[int]] = mapped_column(JSON, default=list)


class CVProfile(Base):
    """Stores the embedding of an uploaded CV. Single-row table (id=1).

    The raw text is kept for transparency ("did the matcher see my Python?") but
    nothing here ever leaves the machine.
    """

    __tablename__ = "cv_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(256), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    # Embedding stored as list of floats in JSON. Small (~384 dims).
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list)
    model: Mapped[str] = mapped_column(String(128), default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Skills/languages extracted from the CV — used to suggest pre-set filters.
    detected_skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    detected_languages: Mapped[list[str]] = mapped_column(JSON, default=list)
