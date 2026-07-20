"""Filter query builder. Keeps the FastAPI route free of SQL."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from .models import Job


@dataclass(slots=True)
class JobQuery:
    q: str = ""                   # free text in title/company/description
    company: str = ""
    location: str = ""
    remote: str = ""              # remote | hybrid | onsite | ""
    level: str = ""               # intern | entry | junior | mid | senior | staff | principal | lead
    degree: str = ""              # none | bachelors | masters | phd | ""
    max_years: int | None = None  # exclude jobs whose min_years > this
    languages: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    posted_within_days: int | None = None
    employment_type: str = ""        # full-time | part-time | contract | internship
    min_salary: int | None = None     # minimum annual salary
    visa_sponsorship: str = ""        # yes | no | ""
    # us-only | uk-only | eu-only | restricted-other | unrestricted | unknown
    geo: str = ""
    min_cv_match: float | None = None  # 0..1
    limit: int = 50
    offset: int = 0
    sort: str = "score"           # score | posted | seen | cv
    # User's own region ('us'|'uk'|'eu'|'other'|''), from settings.user_location.
    # '' = unknown -> reachability never penalizes. Set by main._query_from_request.
    home_region: str = ""


_FTS_SAFE_TERM = re.compile(r"[^A-Za-z0-9À-￿#+]+")


def _fts_query(q: str) -> str | None:
    """Convert a free-text user query into a safe FTS5 expression.

    Strategy: split on whitespace, strip FTS5 metacharacters from each term
    (FTS5 treats `-` `:` `^` etc. as operators which can blow up on user
    input), quote each remaining term to make it a phrase, AND them
    together. Returns None if nothing usable remains.
    """
    parts: list[str] = []
    for raw in (q or "").split():
        # Drop anything that isn't alphanumeric / safe punctuation. Keeps
        # `#` and `+` so terms like `c++` survive.
        cleaned = _FTS_SAFE_TERM.sub("", raw)
        if len(cleaned) >= 2:
            parts.append(f'"{cleaned}"')
    if not parts:
        return None
    return " ".join(parts)


def _apply(stmt: Select[tuple[Job]], q: JobQuery) -> Select[tuple[Job]]:
    if q.q:
        # Prefer FTS5 when available — 10-100× faster than triple-LIKE at
        # 24k+ rows. Falls back to LIKE if the SQLite build lacks FTS5 or
        # the cleaned query is empty.
        from .db import has_fts5
        from sqlalchemy import literal

        fts_q = _fts_query(q.q) if has_fts5() else None
        if fts_q:
            # `jobs_fts` is the virtual index; rowid maps back to jobs.id.
            stmt = stmt.where(
                Job.id.in_(
                    __import__("sqlalchemy").text(
                        "SELECT rowid FROM jobs_fts WHERE jobs_fts MATCH :fts"
                    ).bindparams(fts=fts_q)
                )
            )
        else:
            like = f"%{q.q.lower()}%"
            stmt = stmt.where(
                or_(
                    Job.title.ilike(like),
                    Job.company.ilike(like),
                    Job.description.ilike(like),
                )
            )
    if q.company:
        stmt = stmt.where(Job.company.ilike(f"%{q.company}%"))
    if q.location:
        stmt = stmt.where(Job.location.ilike(f"%{q.location}%"))
    if q.remote:
        stmt = stmt.where(Job.remote == q.remote)
    if q.level:
        stmt = stmt.where(Job.level == q.level)
    if q.degree:
        stmt = stmt.where(Job.degree == q.degree)
    if q.max_years is not None:
        stmt = stmt.where(or_(Job.min_years.is_(None), Job.min_years <= q.max_years))
    if q.employment_type:
        stmt = stmt.where(Job.employment_type.ilike(f"%{q.employment_type}%"))
    if q.min_salary is not None:
        stmt = stmt.where(Job.salary_max.is_not(None), Job.salary_max >= q.min_salary)
    if q.visa_sponsorship:
        stmt = stmt.where(Job.visa_sponsorship == q.visa_sponsorship)
    if q.geo:
        stmt = stmt.where(Job.geo_restrict == q.geo)
    if q.posted_within_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=q.posted_within_days)
        stmt = stmt.where(or_(Job.posted_at.is_(None), Job.posted_at >= cutoff))

    if q.min_cv_match is not None:
        stmt = stmt.where(Job.cv_match.is_not(None), Job.cv_match >= q.min_cv_match)

    # Language and skill filters are JSON-array contains. SQLite stores them as JSON
    # text, so we use a LIKE on the serialized representation — fine at this scale.
    for lang in q.languages:
        stmt = stmt.where(Job.languages.cast(type_=__import__("sqlalchemy").Text).ilike(f'%"{lang}"%'))
    for skill in q.skills:
        stmt = stmt.where(Job.skills.cast(type_=__import__("sqlalchemy").Text).ilike(f'%"{skill}"%'))

    # P4: relevance/CV sorts demote known-unreachable geo buckets and blend
    # the CV match into the default score. Chronological sorts stay pure.
    if q.sort == "posted":
        stmt = stmt.order_by(Job.posted_at.desc().nullslast(), Job.score.desc())
    elif q.sort == "seen":
        stmt = stmt.order_by(Job.last_seen_at.desc())
    else:
        from sqlalchemy import case, func

        from .scoring import CV_BLEND_WEIGHT, reachability_weights

        penalties = {
            bucket: w
            for bucket, w in reachability_weights(q.home_region).items()
            if w != 1.0
        }
        reach = case(penalties, value=Job.geo_restrict, else_=1.0) if penalties else 1.0
        if q.sort == "cv":
            rank = func.coalesce(Job.cv_match, 0.0) * reach
            stmt = stmt.order_by(rank.desc(), Job.score.desc())
        else:
            rank = (
                Job.score
                * (1.0 + CV_BLEND_WEIGHT * func.coalesce(Job.cv_match, 0.0))
                * reach
            )
            stmt = stmt.order_by(rank.desc(), Job.posted_at.desc().nullslast())
    return stmt


def search(session: Session, q: JobQuery) -> list[Job]:
    stmt = _apply(select(Job), q).limit(q.limit).offset(q.offset)
    return list(session.execute(stmt).scalars().all())


def count(session: Session, q: JobQuery) -> int:
    from sqlalchemy import func

    stmt = _apply(select(func.count()).select_from(Job), q)
    return session.execute(stmt).scalar_one()


import time as _time

_facet_cache: dict[str, object] = {"data": None, "expires": 0.0}
_FACET_TTL = 60


def facets(session: Session) -> dict[str, list[tuple[str, int]]]:
    """Return value counts for facet filters. Cached for 60 seconds."""
    from sqlalchemy import func

    now = _time.monotonic()
    if _facet_cache["data"] and now < _facet_cache["expires"]:
        return _facet_cache["data"]  # type: ignore[return-value]

    out: dict[str, list[tuple[str, int]]] = {}
    for col, key in (
        (Job.remote, "remote"),
        (Job.level, "level"),
    ):
        rows = session.execute(
            select(col, func.count()).group_by(col).order_by(func.count().desc())
        ).all()
        out[key] = [(r[0] or "unknown", r[1]) for r in rows]
    _facet_cache["data"] = out
    _facet_cache["expires"] = now + _FACET_TTL
    return out
