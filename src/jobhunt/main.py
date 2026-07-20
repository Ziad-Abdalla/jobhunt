from __future__ import annotations

import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import func, select

from . import __version__
from . import scheduler as sched_module
from .alerts import check_alerts
from .config import settings
from .db import db_session, init_db
from .filters import JobQuery, count, facets, search
from .models import CVProfile, Job, SavedSearch, ScrapeRun
from .refresh import scrape_all
from .scoring import home_region_from_location
from .sources_admin import (
    add_source as sources_add,
)
from .sources_admin import (
    available_source_types,
    list_all_sources,
)
from .sources_admin import (
    remove_source as sources_remove,
)

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _localdate(dt: datetime | None, fmt: str = "%b %d, %Y") -> str:
    """Render a stored UTC datetime in the user's local timezone."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().strftime(fmt)


templates.env.filters["localdate"] = _localdate
templates.env.globals["version"] = __version__

@asynccontextmanager
async def _lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    """Lifespan context: initialise DB + start the scheduler on boot, stop
    the scheduler on shutdown. Replaces the deprecated @app.on_event hooks."""
    init_db()
    if settings.refresh_interval_minutes > 0:
        sched_module.start()
    try:
        yield
    finally:
        sched_module.stop()


app = FastAPI(title="jobhunt", version=__version__, lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _allowed_origin(host: str) -> str:
    """Build the same-origin URL we expect requests to come from."""
    return f"http://{host}"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # Localhost-CSRF defence: any state-changing request must come from a same-origin
    # context. A malicious website cannot set the Origin header via fetch(), so this
    # blocks the "evil site POSTs to your running localhost" class of attack.
    if request.method not in _SAFE_METHODS:
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")
        host = request.headers.get("host", "")
        expected = _allowed_origin(host)
        ok = False
        if origin and origin == expected:
            ok = True
        elif not origin and referer and referer.startswith(expected + "/"):
            ok = True  # Some browsers omit Origin on same-origin form POSTs.
        elif not origin and not referer and request.url.path.startswith("/api/"):
            # CLI / curl scripts hitting our API explicitly — allow only on /api/*.
            # Browser cross-site fetch always sends an Origin, so this is safe.
            ok = True
        if not ok:
            return JSONResponse({"error": "cross-origin request blocked"}, status_code=403)

    resp = await call_next(request)
    resp.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'",
    )
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


def _today() -> str:
    return datetime.now(UTC).strftime("%A, %B %d, %Y").upper()


def _last_updated_str() -> str:
    """Get the most recent scrape run time as a readable string."""
    with db_session() as s:
        row = s.execute(
            select(ScrapeRun.started_at)
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    if row:
        return _localdate(row, "%b %d, %H:%M")
    return ""


def _safe_int(val: str | int | None) -> int | None:
    """Convert a query param that might be an empty string to int or None."""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: str | float | None) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _query_from_request(
    q: str,
    company: str,
    location: str,
    remote: str,
    level: str,
    degree: str,
    max_years: str | int | None,
    languages: list[str] | None,
    skills: list[str] | None,
    posted_within_days: str | int | None,
    sort: str,
    limit: str | int,
    offset: str | int,
    min_cv_match: str | float | None = None,
    employment_type: str = "",
    min_salary: str | int | None = None,
    visa_sponsorship: str = "",
    geo: str = "",
) -> JobQuery:
    return JobQuery(
        q=q.strip(),
        company=company.strip(),
        location=location.strip(),
        remote=remote.strip(),
        level=level.strip(),
        degree=degree.strip(),
        max_years=_safe_int(max_years),
        languages=tuple(s.lower() for s in (languages or []) if s),
        skills=tuple(s.lower() for s in (skills or []) if s),
        posted_within_days=_safe_int(posted_within_days),
        employment_type=employment_type.strip(),
        min_salary=_safe_int(min_salary),
        visa_sponsorship=visa_sponsorship.strip(),
        geo=geo.strip(),
        min_cv_match=_safe_float(min_cv_match),
        sort=sort or "score",
        home_region=home_region_from_location(settings.user_location),
        limit=max(1, min(_safe_int(limit) or 50, 200)),
        offset=max(0, _safe_int(offset) or 0),
    )


# ---------- main job search ----------


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    with db_session() as s:
        f = facets(s)
        total = count(s, JobQuery())
        cv_loaded = bool(s.execute(select(func.count()).select_from(CVProfile)).scalar_one())
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "facets": f,
            "total": total,
            "cv_loaded": cv_loaded,
            "home_region": home_region_from_location(settings.user_location),
            "nav": "search",
            "today": _today(),
            "last_updated": _last_updated_str(),
        },
    )


@app.get("/jobs", response_class=HTMLResponse)
def jobs(
    request: Request,
    q: str = "",
    company: str = "",
    location: str = "",
    remote: str = "",
    level: str = "",
    degree: str = "",
    max_years: str = "",
    languages: list[str] = Query(default=[]),
    skills: list[str] = Query(default=[]),
    posted_within_days: str = "",
    min_cv_match: str = "",
    employment_type: str = "",
    min_salary: str = "",
    visa_sponsorship: str = "",
    geo: str = "",
    sort: str = "score",
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    query = _query_from_request(
        q, company, location, remote, level, degree, max_years,
        languages, skills, posted_within_days, sort, limit, offset,
        min_cv_match=min_cv_match,
        employment_type=employment_type,
        min_salary=min_salary,
        visa_sponsorship=visa_sponsorship,
        geo=geo,
    )
    with db_session() as s:
        rows = search(s, query)
        total = count(s, query)
        db_total = s.execute(select(func.count()).select_from(Job)).scalar_one()
    return templates.TemplateResponse(
        request,
        "_jobs.html",
        {
            "jobs": rows,
            "total": total,
            "limit": query.limit,
            "offset": query.offset,
            "db_empty": db_total == 0,
            "default_source_count": 130,
        },
    )


@app.get("/api/jobs")
def api_jobs(
    q: str = "",
    company: str = "",
    location: str = "",
    remote: str = "",
    level: str = "",
    degree: str = "",
    max_years: str = "",
    languages: list[str] = Query(default=[]),
    skills: list[str] = Query(default=[]),
    posted_within_days: str = "",
    min_cv_match: str = "",
    employment_type: str = "",
    min_salary: str = "",
    visa_sponsorship: str = "",
    geo: str = "",
    sort: str = "score",
    limit: int = 50,
    offset: int = 0,
) -> JSONResponse:
    query = _query_from_request(
        q, company, location, remote, level, degree, max_years,
        languages, skills, posted_within_days, sort, limit, offset,
        min_cv_match=min_cv_match,
        employment_type=employment_type,
        min_salary=min_salary,
        visa_sponsorship=visa_sponsorship,
        geo=geo,
    )
    with db_session() as s:
        rows = search(s, query)
        total = count(s, query)
    return JSONResponse(
        {
            "total": total,
            "results": [
                {
                    "id": j.id,
                    "title": j.title,
                    "company": j.company,
                    "location": j.location,
                    "url": j.url,
                    "remote": j.remote,
                    "geo_restrict": j.geo_restrict,
                    "level": j.level,
                    "degree": j.degree,
                    "min_years": j.min_years,
                    "languages": j.languages,
                    "skills": j.skills,
                    "source": j.source,
                    "posted_at": j.posted_at.isoformat() if j.posted_at else None,
                    "employment_type": j.employment_type,
                    "salary_min": j.salary_min,
                    "salary_max": j.salary_max,
                    "salary_currency": j.salary_currency,
                    "salary_estimated": j.salary_estimated,
                    "visa_sponsorship": j.visa_sponsorship,
                    "score": j.score,
                    "cv_match": j.cv_match,
                    "apply_kind": j.apply_kind or "unknown",
                    "apply_domain": j.apply_domain or "",
                }
                for j in rows
            ],
        }
    )


# ---------- local jobs page ----------


_REGION_MAP: dict[str, list[str]] = {
    # UK areas → broader search terms
    "whitechapel": ["whitechapel", "london", "tower hamlets", "east london"],
    "canary wharf": ["canary wharf", "london", "tower hamlets"],
    "shoreditch": ["shoreditch", "london", "hackney"],
    "soho": ["soho", "london", "westminster"],
    "city of london": ["city of london", "london"],
    "london": ["london", "uk", "united kingdom", "england"],
    "manchester": ["manchester", "uk", "united kingdom", "england"],
    "birmingham": ["birmingham", "uk", "united kingdom", "england"],
    "leeds": ["leeds", "uk", "united kingdom", "england"],
    "bristol": ["bristol", "uk", "united kingdom", "england"],
    "edinburgh": ["edinburgh", "uk", "united kingdom", "scotland"],
    "glasgow": ["glasgow", "uk", "united kingdom", "scotland"],
    "cambridge": ["cambridge", "uk", "united kingdom", "england"],
    "oxford": ["oxford", "uk", "united kingdom", "england"],
    "reading": ["reading", "uk", "united kingdom", "england"],
    "cardiff": ["cardiff", "uk", "united kingdom", "wales"],
    "belfast": ["belfast", "uk", "united kingdom", "northern ireland"],
    "liverpool": ["liverpool", "uk", "united kingdom", "england"],
    "sheffield": ["sheffield", "uk", "united kingdom", "england"],
    "newcastle": ["newcastle", "uk", "united kingdom", "england"],
    "nottingham": ["nottingham", "uk", "united kingdom", "england"],
    "brighton": ["brighton", "uk", "united kingdom", "england"],
    "uk": ["uk", "united kingdom", "england", "london"],
    # German areas
    "stuttgart": ["stuttgart", "baden-württemberg", "germany", "deutschland"],
    "berlin": ["berlin", "germany", "deutschland"],
    "munich": ["munich", "münchen", "bavaria", "bayern", "germany"],
    "münchen": ["münchen", "munich", "bavaria", "bayern", "germany"],
    "hamburg": ["hamburg", "germany", "deutschland"],
    "frankfurt": ["frankfurt", "hessen", "germany", "deutschland"],
    "cologne": ["cologne", "köln", "nordrhein-westfalen", "germany"],
    "köln": ["köln", "cologne", "nordrhein-westfalen", "germany"],
    "düsseldorf": ["düsseldorf", "nordrhein-westfalen", "germany"],
    "dortmund": ["dortmund", "nordrhein-westfalen", "germany"],
    "leipzig": ["leipzig", "sachsen", "germany", "deutschland"],
    "dresden": ["dresden", "sachsen", "germany", "deutschland"],
    "hannover": ["hannover", "niedersachsen", "germany", "deutschland"],
    "nürnberg": ["nürnberg", "nuremberg", "bavaria", "bayern", "germany"],
    "germany": ["germany", "deutschland", "berlin", "münchen"],
    "deutschland": ["deutschland", "germany", "berlin", "münchen"],
    # Egypt areas (P3) — Wuzzuf locations look like "Cairo, Egypt".
    "cairo": ["cairo", "egypt", "new cairo", "nasr city", "heliopolis", "maadi"],
    "giza": ["giza", "egypt", "6th of october", "sheikh zayed"],
    "alexandria": ["alexandria", "egypt"],
    "new cairo": ["new cairo", "cairo", "egypt"],
    "6th of october": ["6th of october", "giza", "egypt"],
    "maadi": ["maadi", "cairo", "egypt"],
    "nasr city": ["nasr city", "cairo", "egypt"],
    "heliopolis": ["heliopolis", "cairo", "egypt"],
    "mansoura": ["mansoura", "egypt"],
    "tanta": ["tanta", "egypt"],
    "egypt": ["egypt", "cairo", "giza", "alexandria"],
    "القاهرة": ["القاهرة", "cairo", "egypt"],
    "الجيزة": ["الجيزة", "giza", "egypt"],
    "الإسكندرية": ["الإسكندرية", "alexandria", "egypt"],
    "مصر": ["مصر", "egypt", "cairo"],
}


@app.get("/local", response_class=HTMLResponse)
def local_jobs(
    request: Request,
    location: str = "",
    level: str = "",
    employment_type: str = "",
    min_salary: str = "",
    max_experience: str = "",
    category: str = "nontech",
) -> HTMLResponse:
    """Zero-experience jobs near a location.

    Defaults to ``category=nontech`` (cleaning, retail, warehouse, hospitality,
    care, customer service, driving …) — the kind of work anyone can start
    without prior experience or a degree. Flip ``category=tech`` for the
    entry-level software / IT path, or ``category=any`` for everything.
    """
    jobs: list[Job] = []
    total = 0
    nontech_total = 0
    tech_total = 0
    loc_input = location.strip()
    cat = (category or "nontech").lower()
    if cat not in {"nontech", "tech", "any"}:
        cat = "nontech"

    if loc_input:
        from sqlalchemy import or_

        loc = loc_input.lower()
        search_terms = [loc]
        if loc in _REGION_MAP:
            search_terms.extend(_REGION_MAP[loc])
        search_terms = list(dict.fromkeys(search_terms))

        with db_session() as s:
            loc_filters = [Job.location.ilike(f"%{t}%") for t in search_terms]
            base = select(Job).where(or_(*loc_filters))

            if cat == "nontech":
                base = base.where(Job.category == "nontech")
            elif cat == "tech":
                base = base.where(Job.category == "tech")

            if level:
                base = base.where(Job.level == level)

            max_exp = _safe_int(max_experience)
            if max_exp is not None:
                base = base.where(
                    or_(Job.min_years.is_(None), Job.min_years <= max_exp)
                )
            else:
                base = base.where(
                    or_(Job.min_years.is_(None), Job.min_years <= 2)
                )

            if employment_type:
                base = base.where(Job.employment_type == employment_type)
            sal = _safe_int(min_salary)
            if sal:
                base = base.where(
                    Job.salary_max.is_not(None), Job.salary_max >= sal
                )
            base = base.order_by(
                Job.posted_at.desc().nullslast(), Job.score.desc()
            )
            total = s.execute(
                select(func.count()).select_from(base.subquery())
            ).scalar_one()
            jobs = list(s.execute(base.limit(200)).scalars().all())

            # Counts for the category switcher — only against the location filter
            # + the same max-experience / employment-type / salary stack, so the
            # numbers shown next to each option mean "if I picked this".
            count_base = select(func.count()).select_from(Job).where(or_(*loc_filters))
            if max_exp is not None:
                count_base = count_base.where(
                    or_(Job.min_years.is_(None), Job.min_years <= max_exp)
                )
            else:
                count_base = count_base.where(
                    or_(Job.min_years.is_(None), Job.min_years <= 2)
                )
            nontech_total = s.execute(
                count_base.where(Job.category == "nontech")
            ).scalar_one()
            tech_total = s.execute(
                count_base.where(Job.category == "tech")
            ).scalar_one()

    return templates.TemplateResponse(
        request,
        "local.html",
        {
            "nav": "local",
            "today": _today(),
            "jobs": jobs,
            "total": total,
            "location": loc_input,
            "level": level,
            "employment_type": employment_type,
            "min_salary": min_salary,
            "max_experience": max_experience,
            "category": cat,
            "nontech_total": nontech_total,
            "tech_total": tech_total,
        },
    )


# ---------- freelance page ----------


@app.get("/freelance", response_class=HTMLResponse)
def freelance_page(
    request: Request,
    q: str = "",
    remote: str = "",
    min_salary: str = "",
) -> HTMLResponse:
    """Contract and freelance roles, sorted by most recent."""
    from sqlalchemy import or_

    with db_session() as s:
        stmt = select(Job).where(
            Job.employment_type.in_(["Contract", "Freelance"])
        )
        if q.strip():
            like = f"%{q.strip().lower()}%"
            stmt = stmt.where(or_(
                Job.title.ilike(like),
                Job.company.ilike(like),
                Job.description.ilike(like),
            ))
        if remote:
            stmt = stmt.where(Job.remote == remote)
        sal = _safe_int(min_salary)
        if sal:
            stmt = stmt.where(Job.salary_max.is_not(None), Job.salary_max >= sal)
        stmt = stmt.order_by(Job.posted_at.desc().nullslast(), Job.score.desc())
        total = s.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()
        jobs = list(s.execute(stmt.limit(200)).scalars().all())

    return templates.TemplateResponse(
        request,
        "freelance.html",
        {
            "nav": "freelance",
            "today": _today(),
            "jobs": jobs,
            "total": total,
            "q": q.strip(),
            "remote": remote,
            "min_salary": min_salary,
        },
    )


# ---------- P6: loopback gate + applicant profile ----------

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})
_LOOPBACK_HOSTNAMES = frozenset({"127.0.0.1", "localhost", "::1"})


def _normalize_peer(host: str) -> str:
    # Dual-stack (HOST=::) reports an IPv4 client as ::ffff:127.0.0.1 — treat
    # only that exact mapped-loopback form as loopback (never broaden to
    # arbitrary mapped addresses).
    return host[7:] if host.startswith("::ffff:") else host


def _host_header_hostname(host_header: str) -> str:
    """Hostname portion of a Host header, port + IPv6 brackets stripped."""
    h = host_header.strip()
    if h.startswith("["):  # [::1] or [::1]:8765
        end = h.find("]")
        return h[1:end] if end != -1 else h[1:]
    return h.split(":")[0]


def _require_loopback(request: Request) -> None:
    """PII endpoints answer the local machine only, INDEPENDENT of the bind
    host: with HOST=0.0.0.0 (phone-on-LAN browsing) /profile and
    /api/cowork/* still refuse remote peers.

    Two checks, both required: (1) the socket peer is loopback (unspoofable),
    and (2) the Host header names a loopback hostname. The Host check defeats
    DNS rebinding — a malicious site that rebinds its name to 127.0.0.1 has a
    loopback *peer* but an attacker-controlled *Host*, which this rejects."""
    client = request.client
    peer = _normalize_peer(client.host) if client else ""
    host_ok = _host_header_hostname(request.headers.get("host", "")) in _LOOPBACK_HOSTNAMES
    if peer not in _LOOPBACK_HOSTS or not host_ok:
        raise HTTPException(
            status_code=403,
            detail="This page holds applicant data and only answers loopback "
                   "(local machine) requests.",
        )


# Accidental credential paste must never land in the PII store. Concrete,
# low-false-positive patterns only (an over-eager filter would block real
# cover letters).
_SECRET_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                 # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),              # generic sk- API key
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),              # GitHub PAT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),    # PEM
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+"),  # JWT (header.payload)
)


def _find_secret(value: str) -> bool:
    return any(p.search(value) for p in _SECRET_PATTERNS)


_PROFILE_FIELD_CAPS = {
    "full_name": 256, "email": 256, "phone": 64, "location": 256,
    "linkedin_url": 512, "github_url": 512, "portfolio_url": 512,
    "work_authorization": 512, "salary_expectation": 128, "cover_note": 4000,
}


def _get_or_create_profile(s):
    from .cowork_models import ApplicantProfile

    p = s.get(ApplicantProfile, 1)
    if p is None:
        p = ApplicantProfile(id=1)
        s.add(p)
    return p


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, _: None = Depends(_require_loopback)) -> HTMLResponse:
    from .cowork_models import ApplicantProfile

    with db_session() as s:
        p = s.get(ApplicantProfile, 1)
        fields = {k: getattr(p, k, "") or "" for k in _PROFILE_FIELD_CAPS} if p else \
                 {k: "" for k in _PROFILE_FIELD_CAPS}
    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "nav": "profile",
            "today": _today(),
            "fields": fields,
            "saved": request.query_params.get("saved") == "1",
            "cowork_export_on": settings.cowork_export,
        },
    )


@app.post("/profile", response_model=None)
def profile_save(
    request: Request,
    _: None = Depends(_require_loopback),
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    location: str = Form(""),
    linkedin_url: str = Form(""),
    github_url: str = Form(""),
    portfolio_url: str = Form(""),
    work_authorization: str = Form(""),
    salary_expectation: str = Form(""),
    cover_note: str = Form(""),
):
    values = {
        "full_name": full_name, "email": email, "phone": phone,
        "location": location, "linkedin_url": linkedin_url,
        "github_url": github_url, "portfolio_url": portfolio_url,
        "work_authorization": work_authorization,
        "salary_expectation": salary_expectation, "cover_note": cover_note,
    }
    for key, raw in values.items():
        if _find_secret(raw):
            return HTMLResponse(
                "<h1>That looks like a secret/API key.</h1>"
                "<p>The applicant profile is for contact details only — it must "
                "never hold credentials. Remove the key-like text from "
                f"<strong>{key}</strong> and save again.</p>"
                '<p><a href="/profile">Back to profile</a></p>',
                status_code=400,
            )
        values[key] = _trim(raw, _PROFILE_FIELD_CAPS[key])
    with db_session() as s:
        p = _get_or_create_profile(s)
        for key, val in values.items():
            setattr(p, key, val)
        p.updated_at = datetime.now(UTC)
    return RedirectResponse("/profile?saved=1", status_code=303)


# ---------- apply-target collection page (P5) ----------


@app.get("/apply", response_class=HTMLResponse)
def apply_page(
    request: Request,
    kind: str = "",
    q: str = "",
    remote: str = "",
    view: str = "",
    limit: int = 50,
    offset: int = 0,
) -> HTMLResponse:
    """Where does applying actually happen? Groups jobs by application-flow
    bucket (known ATS form / board relay / company own-site) so the user —
    and later the Cowork handoff (P6) — can pick targets by effort."""
    from dataclasses import replace

    if view == "queue":
        # The queue view renders drafted PII (fields_filled) — loopback only,
        # like /profile, independent of the bind host.
        _require_loopback(request)
        from .cowork_models import Application

        with db_session() as s:
            apps = list(
                s.execute(
                    select(Application, Job)
                    .join(Job, Job.id == Application.job_id)
                    .order_by(Application.updated_at.desc())
                ).all()
            )
            queue_rows = [
                {"app": a, "job": j} for a, j in apps
            ]
        return templates.TemplateResponse(
            request,
            "apply_queue.html",
            {
                "nav": "apply",
                "today": _today(),
                "last_updated": _last_updated_str(),
                "rows": queue_rows,
                "cowork_export_on": settings.cowork_export,
            },
        )

    if kind not in ("ats", "aggregator_relay", "company_site", "unknown"):
        kind = ""
    query = JobQuery(
        q=q.strip(),
        remote=remote.strip(),
        apply_kind=kind,
        sort="score",
        home_region=home_region_from_location(settings.user_location),
        limit=max(1, min(_safe_int(limit) or 50, 200)),
        offset=max(0, _safe_int(offset) or 0),
    )
    with db_session() as s:
        rows = search(s, query)
        # Per-bucket counts under the SAME q/remote filters (so the toggle
        # numbers always agree with what clicking them shows), in ONE grouped
        # query — 3× cheaper than four count() calls at 32k rows. NULL
        # (pre-backfill) folds into 'unknown'; total falls out of the sum.
        from .filters import _apply as _apply_filters

        grouped_stmt = _apply_filters(
            select(Job.apply_kind, func.count()).select_from(Job),
            replace(query, apply_kind=""),
            order=False,
        ).group_by(Job.apply_kind)
        grouped = dict(s.execute(grouped_stmt).all())
        kind_counts = {
            k: grouped.get(k, 0)
            for k in ("ats", "aggregator_relay", "company_site", "unknown")
        }
        kind_counts["unknown"] += grouped.get(None, 0)
        total = kind_counts[kind] if kind else sum(kind_counts.values())
        db_total = s.execute(select(func.count()).select_from(Job)).scalar_one()
        from .cowork_models import Application
        queue_count = s.execute(
            select(func.count()).select_from(Application)
        ).scalar_one()
    return templates.TemplateResponse(
        request,
        "apply.html",
        {
            "nav": "apply",
            "today": _today(),
            "last_updated": _last_updated_str(),
            "jobs": rows,
            "total": total,
            "limit": query.limit,
            "offset": query.offset,
            "db_empty": db_total == 0,
            "default_source_count": 130,
            "show_apply_badge": True,
            "show_queue_button": True,
            "kind": kind,
            "q": q.strip(),
            "remote": remote.strip(),
            "kind_counts": kind_counts,
            "queue_count": queue_count,
        },
    )


# ---------- P9+P10: CV tailoring + ATS lint ----------


def _tailor_for_job(job_id: int):
    """Build a TailorReport for a job against the loaded CV. Returns
    (report, job, cv_loaded) or raises 404 if the job is gone."""
    from .cv_tailor import tailor

    with db_session() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such job")
        cv = s.get(CVProfile, 1)
        cv_skills = list(cv.detected_skills or []) if cv else []
        cv_languages = list(cv.detected_languages or []) if cv else []
        cv_text = (cv.text or "") if cv else ""
        cv_loaded = cv is not None
        # Detach the values we need before the session closes.
        job_view = {
            "id": job.id, "title": job.title, "company": job.company,
            "location": job.location, "skills": list(job.skills or []),
            "languages": list(job.languages or []),
            "description": job.description or "",
        }
    job_obj = type("J", (), job_view)
    report = tailor(job_obj, cv_skills, cv_languages, cv_text)
    return report, job_obj, cv_loaded


@app.get("/apply/tailor/{job_id:int}", response_class=HTMLResponse)
def apply_tailor(
    request: Request, job_id: int, _: None = Depends(_require_loopback)
) -> HTMLResponse:
    """Keyword-gap tailoring sheet + ATS lint for a job vs the loaded CV.
    Loopback-gated: it renders the CV's skill inventory (applicant data),
    like /profile and the queue view."""
    report, job, cv_loaded = _tailor_for_job(job_id)
    return templates.TemplateResponse(
        request,
        "tailor.html",
        {
            "nav": "apply",
            "today": _today(),
            "report": report,
            "job": job,
            "cv_loaded": cv_loaded,
        },
    )


@app.get("/apply/tailor/{job_id:int}.md")
def apply_tailor_md(
    request: Request, job_id: int, _: None = Depends(_require_loopback)
) -> Response:
    """The tailoring sheet as a downloadable markdown file. Loopback-gated —
    it embeds the applicant's name + CV skill inventory."""
    from .cv_tailor import render_markdown

    report, job, _ = _tailor_for_job(job_id)
    name = ""
    with db_session() as s:
        from .cowork_models import ApplicantProfile
        p = s.get(ApplicantProfile, 1)
        if p:
            name = p.full_name or ""
    md = render_markdown(report, job, applicant_name=name)
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="tailoring-{job_id}.md"'},
    )


# ---------- P6: Cowork handoff API (loopback + default-OFF toggle) ----------


def _require_cowork(request: Request) -> None:
    """/api/cowork/* = loopback AND the default-OFF export toggle. The
    toggle keeps applicant data un-exportable until the owner opts in;
    loopback keeps it on-machine even then."""
    _require_loopback(request)
    if not settings.cowork_export:
        raise HTTPException(
            status_code=403,
            detail="Cowork export is disabled. Set JOBHUNT_COWORK_EXPORT=1 "
                   "to enable the local handoff API.",
        )


@app.get("/api/cowork/export")
def cowork_export_route(
    request: Request, status: str = "queued", _: None = Depends(_require_cowork)
) -> JSONResponse:
    """The handoff document: applicant block + one record per application in
    the requested status. Built by cowork_export.build_export_document (shared
    with the CLI mirror). The JD is ALWAYS wrapped as __untrusted_data__."""
    from .cowork_export import build_export_document
    from .cowork_models import APPLICATION_STATUSES

    if status not in APPLICATION_STATUSES:
        raise HTTPException(status_code=400, detail=f"unknown status: {status}")

    with db_session() as s:
        doc = build_export_document(s, status)
    return JSONResponse(doc)


class _DraftBody(BaseModel):
    application_id: int
    fields_filled: dict[str, str] = {}
    agent_notes: str = ""
    error: str = ""

    @field_validator("fields_filled")
    @classmethod
    def _cap_fields(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 50:
            raise ValueError("too many fields")
        return {str(k)[:128]: str(val)[:2000] for k, val in v.items()}


class _ReceiptBody(BaseModel):
    application_id: int
    receipt: str = ""
    error: str = ""

    @field_validator("receipt")
    @classmethod
    def _receipt_shape(cls, v: str) -> str:
        # A message id: single line, bounded. Never a blob, never multiline.
        if "\n" in v or "\r" in v or len(v) > 512:
            raise ValueError("receipt must be a single line of at most 512 chars")
        return v

    @model_validator(mode="after")
    def _receipt_xor_error(self) -> "_ReceiptBody":
        # A submission is either a success (receipt) or a failure (error),
        # never both — else a 'failed' row keeps a green receipt badge.
        if self.receipt and self.error:
            raise ValueError("receipt and error are mutually exclusive")
        return self


@app.post("/api/cowork/draft")
def cowork_draft(
    body: _DraftBody, request: Request, _: None = Depends(_require_cowork)
) -> JSONResponse:
    """The actuator reports what it WOULD fill — never a submit. Moves
    queued→drafted (or →failed with an error). The draft is rendered on
    /apply?view=queue for human review (gate 2)."""
    new_status = "failed" if body.error else "drafted"
    _cas_transition(body.application_id, new_status, extra={
        "fields_filled": body.fields_filled,
        "agent_notes": _trim(body.agent_notes, 2000),
        "error": _trim(body.error, 2000),
    })
    return JSONResponse({"ok": True, "status": new_status})


class _ClaimBody(BaseModel):
    application_id: int


@app.post("/api/cowork/claim")
def cowork_claim(
    body: _ClaimBody, request: Request, _: None = Depends(_require_cowork)
) -> JSONResponse:
    """Actuator claims an approved application before acting on it: moves
    approved→submitting, which drops it out of the `status=approved` export
    poll. This is the race guard — a crash-then-rerun (or two overlapping
    actuators) can't both see the same approved row and double-submit. The
    claim is idempotent-safe: a second claim of an already-submitting row
    409s (and a concurrent double-claim loses the compare-and-swap)."""
    _cas_transition(body.application_id, "submitting")
    return JSONResponse({"ok": True, "status": "submitting"})


@app.post("/api/cowork/receipt")
def cowork_receipt(
    body: _ReceiptBody, request: Request, _: None = Depends(_require_cowork)
) -> JSONResponse:
    """Post-hoc proof of a submission. Legal only from 'submitting' (the
    claimed state), so a submit that skipped the human approve gate OR the
    claim can never be recorded as success."""
    new_status = "failed" if body.error else "submitted"
    _cas_transition(body.application_id, new_status, extra={
        "receipt": body.receipt,
        "error": _trim(body.error, 2000),
    })
    return JSONResponse({"ok": True, "status": new_status})


# ---------- P6: application queue actions (human gates 1 + 2) ----------


@app.post("/apply/queue/{job_id}", response_model=None)
def apply_queue_add(
    job_id: int, request: Request, _: None = Depends(_require_loopback)
):
    """Gate 1: the human queues a job for application. Idempotent for an
    active application; re-activates a terminal one (rejected/failed) so a
    job that couldn't be actuated the first time (e.g. a board-account
    Wuzzuf role) isn't a permanent dead-end."""
    from .cowork_models import TERMINAL_REQUEUEABLE, Application

    with db_session() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="no such job")
        existing = s.execute(
            select(Application).where(Application.job_id == job_id)
        ).scalar_one_or_none()
        if existing is None:
            s.add(Application(job_id=job_id))
        elif existing.status in TERMINAL_REQUEUEABLE:
            # Re-activate a terminal application AND clear the stale artifacts
            # of the previous attempt, so a fresh queue doesn't show an old
            # receipt/draft (which would misread as a completed submission).
            existing.status = "queued"
            existing.error = ""
            existing.receipt = ""
            existing.fields_filled = {}
            existing.agent_notes = ""
            existing.updated_at = datetime.now(UTC)
    return RedirectResponse("/apply?view=queue", status_code=303)


def _cas_transition(app_id: int, new_status: str, *, extra: dict | None = None) -> None:
    """Apply a state transition with a compare-and-swap so concurrent writers
    can't both succeed (SQLite WAL + a shared pool means two request threads
    read independently). We validate can_transition on the status we read,
    then UPDATE … WHERE id=:id AND status=:that_exact_status; a rowcount of 0
    means someone transitioned first → 409. This closes the claim/draft/
    receipt TOCTOU race that a plain get-then-set leaves open."""
    from sqlalchemy import update as _update

    from .cowork_models import Application, can_transition

    with db_session() as s:
        a = s.get(Application, app_id)
        if a is None:
            raise HTTPException(status_code=404, detail="no such application")
        current = a.status
        if not can_transition(current, new_status):
            raise HTTPException(
                status_code=409, detail=f"cannot move {current} -> {new_status}"
            )
        values = {"status": new_status, "updated_at": datetime.now(UTC)}
        if extra:
            values.update(extra)
        result = s.execute(
            _update(Application)
            .where(Application.id == app_id, Application.status == current)
            .values(**values)
        )
        if result.rowcount == 0:
            raise HTTPException(
                status_code=409, detail="application state changed concurrently"
            )


@app.post("/apply/queue/{app_id}/approve", response_model=None)
def apply_queue_approve(
    app_id: int, request: Request, _: None = Depends(_require_loopback)
):
    """Gate 2: the human approves the reviewed draft. Only drafted→approved
    is legal (per the state machine) — approving from queued (no draft to
    review) or from submitting (already claimed) is a 409."""
    _cas_transition(app_id, "approved")
    return RedirectResponse("/apply?view=queue", status_code=303)


@app.post("/apply/queue/{app_id}/reject", response_model=None)
def apply_queue_reject(
    app_id: int, request: Request, _: None = Depends(_require_loopback)
):
    _cas_transition(app_id, "rejected")
    return RedirectResponse("/apply?view=queue", status_code=303)


_last_refresh: dict[str, float] = {}
_REFRESH_COOLDOWN = 300


@app.post("/api/refresh")
async def api_refresh() -> JSONResponse:
    """Refresh all job sources. Rate-limited to once per 5 min."""
    import time

    now = time.time()
    last = _last_refresh.get("all", 0)
    if now - last < _REFRESH_COOLDOWN:
        remaining = int(_REFRESH_COOLDOWN - (now - last))
        return JSONResponse({
            "ok": False,
            "message": f"Please wait {remaining}s before refreshing again.",
        })

    _last_refresh["all"] = now
    result = await asyncio.shield(scrape_all())
    try:
        alert_result = await check_alerts()
        result["alerts"] = alert_result
    except Exception as exc:  # noqa: BLE001
        result["alerts"] = {"error": str(exc)}
    return JSONResponse(result)


# ---------- per-source health page ----------


@app.get("/health", response_class=HTMLResponse)
def health_page(request: Request) -> HTMLResponse:
    rows: list[dict] = []
    with db_session() as s:
        # Latest run per (source, board).
        sq = (
            select(
                ScrapeRun.source,
                ScrapeRun.board,
                func.max(ScrapeRun.started_at).label("latest"),
            )
            .group_by(ScrapeRun.source, ScrapeRun.board)
            .subquery()
        )
        latest_runs = s.execute(
            select(ScrapeRun)
            .join(
                sq,
                (ScrapeRun.source == sq.c.source)
                & (ScrapeRun.board == sq.c.board)
                & (ScrapeRun.started_at == sq.c.latest),
            )
            .order_by(ScrapeRun.source, ScrapeRun.board)
        ).scalars().all()
        for r in latest_runs:
            job_count = s.execute(
                select(func.count())
                .select_from(Job)
                .where(Job.source == r.source)
            ).scalar_one()
            now = datetime.now(UTC)
            started = r.started_at
            if started is not None and started.tzinfo is None:
                started = started.replace(tzinfo=UTC)
            age = (now - started) if started else timedelta(days=999)
            healthy = r.error is None and r.jobs_seen > 0 and age < timedelta(days=2)
            rows.append(
                {
                    "source": r.source,
                    "board": r.board or "—",
                    "last_run": r.started_at,
                    "jobs_seen": r.jobs_seen,
                    "jobs_added": r.jobs_added,
                    "error": r.error,
                    "healthy": healthy,
                    "total_in_db": job_count,
                }
            )
    sched_status = sched_module.status()
    return templates.TemplateResponse(
        request,
        "health.html",
        {
            "rows": rows,
            "scheduler": sched_status,
            "nav": "health",
            "today": _today(),
            "total": sum(r["total_in_db"] for r in rows) if rows else 0,
        },
    )


# ---------- saved searches / alerts ----------


@app.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request) -> HTMLResponse:
    with db_session() as s:
        searches = list(s.execute(select(SavedSearch).order_by(SavedSearch.created_at.desc())).scalars().all())
        available_sources = [
            r[0] for r in s.execute(
                select(Job.source).distinct().order_by(Job.source)
            ).all() if r[0]
        ]
    return templates.TemplateResponse(
        request,
        "alerts.html",
        {"searches": searches, "nav": "alerts", "today": _today(),
         "available_sources": available_sources},
    )


_MAX_ALERT_NAME = 128       # matches SavedSearch.name length
_MAX_ALERT_FIELD = 256       # plenty for any reasonable user input
_MAX_ALERT_TAGS = 50         # comma-separated lists


def _trim(s: str, limit: int) -> str:
    """Trim + truncate so a malformed or hostile input can't bloat the DB."""
    return (s or "").strip()[:limit]


@app.post("/alerts/create")
def alerts_create(
    name: str = Form(...),
    q: str = Form(""),
    company: str = Form(""),
    location: str = Form(""),
    remote: str = Form(""),
    level: str = Form(""),
    degree: str = Form(""),
    max_years: int | None = Form(None),
    languages: str = Form(""),
    skills: str = Form(""),
    posted_within_days: int | None = Form(None),
    notify: bool = Form(True),
    sources: list[str] = Form(default=[]),
    priority: bool = Form(False),
) -> RedirectResponse:
    name = _trim(name, _MAX_ALERT_NAME)
    if not name:
        raise HTTPException(400, "name required")
    # Bound every free-text field so a 5k-char paste can't bloat the row.
    query_json = {
        "q": _trim(q, _MAX_ALERT_FIELD),
        "company": _trim(company, _MAX_ALERT_FIELD),
        "location": _trim(location, _MAX_ALERT_FIELD),
        "remote": _trim(remote, 16),
        "level": _trim(level, 16),
        "degree": _trim(degree, 16),
        "max_years": max_years,
        "languages": [s.strip().lower() for s in languages.split(",") if s.strip()][:_MAX_ALERT_TAGS],
        "skills": [s.strip().lower() for s in skills.split(",") if s.strip()][:_MAX_ALERT_TAGS],
        "posted_within_days": posted_within_days,
        # P7: only-these-sources filter + fast-poll priority tier.
        "sources": [_trim(x, 32) for x in sources if x.strip()][:_MAX_ALERT_TAGS],
        "priority": bool(priority),
    }
    with db_session() as s:
        existing = s.execute(select(SavedSearch).where(SavedSearch.name == name)).scalar_one_or_none()
        if existing:
            existing.query_json = query_json
            existing.notify = notify
        else:
            s.add(SavedSearch(name=name, query_json=query_json, notify=notify, notified_job_ids=[]))
    return RedirectResponse("/alerts", status_code=303)


@app.post("/alerts/{search_id}/delete")
def alerts_delete(search_id: int) -> RedirectResponse:
    with db_session() as s:
        row = s.execute(select(SavedSearch).where(SavedSearch.id == search_id)).scalar_one_or_none()
        if row:
            s.delete(row)
    return RedirectResponse("/alerts", status_code=303)


@app.post("/api/alerts/check")
async def api_alerts_check() -> JSONResponse:
    return JSONResponse(await check_alerts())


# ---------- CV upload + semantic match ----------


@app.get("/cv", response_class=HTMLResponse)
def cv_page(request: Request) -> HTMLResponse:
    from .cv import cv_status

    status = cv_status()
    return templates.TemplateResponse(
        request,
        "cv.html",
        {"cv": status, "nav": "cv", "today": _today()},
    )


@app.post("/cv/upload")
async def cv_upload(file: UploadFile = File(...)) -> RedirectResponse:
    from .cv import match_all_jobs, upload_cv

    content = await file.read()
    try:
        upload_cv(file.filename or "cv.txt", content)
    except ValueError as exc:
        # Only true input errors (bad file type, parse failure) bubble as 400.
        raise HTTPException(400, str(exc)) from exc
    # Match jobs immediately so the user sees results on the next visit.
    try:
        match_all_jobs()
    except Exception as exc:  # noqa: BLE001
        log.warning("CV match failed: %s", exc)
    return RedirectResponse("/cv", status_code=303)


@app.post("/cv/clear")
def cv_clear_route() -> RedirectResponse:
    from .cv import clear_cv

    clear_cv()
    return RedirectResponse("/cv", status_code=303)


@app.post("/cv/match")
def cv_match_route() -> JSONResponse:
    from .cv import match_all_jobs

    updated = match_all_jobs()
    return JSONResponse({"updated": updated})


# ---------- sources management ----------


def _render_sources(request: Request, error: str | None = None) -> HTMLResponse:
    entries = list_all_sources()
    grouped: dict[str, list[dict]] = {}
    for e in entries:
        grouped.setdefault(e["source"], []).append(e)
    for key in grouped:
        grouped[key].sort(key=lambda e: (e["origin"] != "default", e["board"]))
    grouped_sorted = dict(sorted(grouped.items(), key=lambda kv: kv[0]))
    return templates.TemplateResponse(
        request,
        "sources.html",
        {
            "grouped": grouped_sorted,
            "source_types": available_source_types(),
            "error": error,
            "nav": "sources",
            "today": _today(),
            "total_local": sum(1 for e in entries if e["origin"] == "local"),
            "total_default": sum(1 for e in entries if e["origin"] == "default"),
        },
    )


@app.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request) -> HTMLResponse:
    try:
        return _render_sources(request)
    except Exception as exc:  # noqa: BLE001
        # File-not-found after a package upgrade, YAML parse errors, etc. —
        # serve a graceful "no sources" view instead of crashing the page.
        log.warning("sources page render failed: %s", exc)
        return templates.TemplateResponse(
            request,
            "sources.html",
            {
                "grouped": {},
                "source_types": [],
                "error": (
                    f"Couldn't read the source list ({exc}). "
                    "Try restarting jobhunt — this usually resolves itself."
                ),
                "nav": "sources",
                "today": _today(),
                "total_local": 0,
                "total_default": 0,
            },
        )


@app.post("/sources/add", response_model=None)
def sources_add_route(
    request: Request,
    source: str = Form(...),
    board: str = Form(...),
    company: str = Form(...),
) -> HTMLResponse | RedirectResponse:
    try:
        sources_add(source, board, company)
    except ValueError as exc:
        return _render_sources(request, error=str(exc))
    return RedirectResponse("/sources", status_code=303)


@app.post("/sources/{source}/{board:path}/remove")
def sources_remove_route(source: str, board: str) -> RedirectResponse:
    sources_remove(source, board)
    return RedirectResponse("/sources", status_code=303)


# ---------- settings page ----------


_GITHUB_REPO = "Abdalla2004-collab/Jobhunt"


def _detect_install_method() -> str:
    """Detect how jobhunt was installed."""
    import shutil
    import sys

    if getattr(sys, "frozen", False):
        return "binary"
    if shutil.which("uv"):
        return "uv"
    if shutil.which("pipx"):
        return "pipx"
    return "pip"


def _env_file_path() -> Path:
    """Path to the user-writable .env file in the data directory."""
    return settings.data_dir / ".env"


def _load_user_env() -> dict[str, str]:
    """Load key=value pairs from the user's .env file."""
    path = _env_file_path()
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        result[key.strip()] = val.strip().strip("\"'")
    return result


def _save_user_env(data: dict[str, str]) -> None:
    """Write key=value pairs to the user's .env file."""
    path = _env_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}={v}" for k, v in sorted(data.items()) if v]
    path.write_text("\n".join(lines) + "\n" if lines else "")


def _source_health_summary() -> dict:
    """Return a compact (offline, attention, total) tuple based on the
    latest scrape per source/board. Drives the Settings page badge."""
    offline = 0
    attention = 0
    total = 0
    try:
        with db_session() as s:
            sq = (
                select(
                    ScrapeRun.source,
                    ScrapeRun.board,
                    func.max(ScrapeRun.started_at).label("latest"),
                )
                .group_by(ScrapeRun.source, ScrapeRun.board)
                .subquery()
            )
            rows = s.execute(
                select(ScrapeRun)
                .join(
                    sq,
                    (ScrapeRun.source == sq.c.source)
                    & (ScrapeRun.board == sq.c.board)
                    & (ScrapeRun.started_at == sq.c.latest),
                )
            ).scalars().all()
            total = len(rows)
            for r in rows:
                if r.error:
                    offline += 1
                elif r.jobs_seen == 0:
                    attention += 1
    except Exception as exc:  # noqa: BLE001
        log.warning("source health summary failed: %s", exc)
    return {"offline": offline, "attention": attention, "total": total}


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    import platform

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "nav": "settings",
            "today": _today(),
            "version": __version__,
            "python_version": platform.python_version(),
            "platform": f"{platform.system()} {platform.machine()}",
            "data_dir": str(settings.data_dir),
            "db_path": str(settings.db_path),
            "sources_file": str(settings.sources_file),
            "local_sources_file": str(settings.local_sources_file),
            "install_method": _detect_install_method(),
            # Never render the raw key values (they'd be readable by a LAN
            # peer under HOST=0.0.0.0). Expose only whether each is set;
            # leaving the field blank on save keeps the stored key.
            "jooble_api_key_set": bool(settings.jooble_api_key),
            "reed_api_key_set": bool(settings.reed_api_key),
            "user_location": settings.user_location,
            "source_health": _source_health_summary(),
        },
    )


@app.get("/api/sources/health")
def api_sources_health() -> JSONResponse:
    """JSON source-health summary; used by the Settings page + the
    source-maintenance skill for scripted decisions."""
    return JSONResponse(_source_health_summary())


@app.post("/api/settings/test-keys")
async def api_test_keys(
    jooble_api_key: str = Form(""),
    reed_api_key: str = Form(""),
) -> JSONResponse:
    """Validate API keys with a minimal live request. Users get instant
    ✓/✗ feedback instead of finding out at the next scrape. Form fields
    are optional — if the user omits them, we test the keys already
    saved in settings."""
    import httpx

    jk = (jooble_api_key or settings.jooble_api_key or "").strip()
    rk = (reed_api_key or settings.reed_api_key or "").strip()

    async def test_jooble() -> dict:
        if not jk:
            return {"ok": None, "message": "no key set"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                # POST a tiny query — Jooble responds with totalCount or 401.
                r = await c.post(
                    f"https://jooble.org/api/{jk}",
                    json={"keywords": "developer", "location": "London", "page": "1"},
                )
            if r.status_code == 401:
                return {"ok": False, "message": "key rejected (401) — regenerate at jooble.org/api/about"}
            if r.status_code >= 400:
                return {"ok": False, "message": f"Jooble returned HTTP {r.status_code}"}
            data = r.json()
            if not isinstance(data, dict) or "jobs" not in data:
                return {"ok": False, "message": "unexpected response shape"}
            return {"ok": True, "message": f"{len(data.get('jobs') or [])} jobs in test query"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}

    async def test_reed() -> dict:
        if not rk:
            return {"ok": None, "message": "no key set"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(
                    "https://www.reed.co.uk/api/1.0/search",
                    params={"keywords": "developer", "resultsToTake": 1},
                    auth=httpx.BasicAuth(username=rk, password=""),
                )
            if r.status_code == 401:
                return {"ok": False, "message": "key rejected (401) — regenerate at reed.co.uk/developers/jobseeker"}
            if r.status_code >= 400:
                return {"ok": False, "message": f"Reed returned HTTP {r.status_code}"}
            data = r.json()
            total = data.get("totalResults", 0) if isinstance(data, dict) else 0
            return {"ok": True, "message": f"{total:,} jobs accessible"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}

    jooble_result, reed_result = await asyncio.gather(test_jooble(), test_reed())
    return JSONResponse({"jooble": jooble_result, "reed": reed_result})


@app.post("/api/settings/save")
def api_save_settings(
    jooble_api_key: str = Form(""),
    reed_api_key: str = Form(""),
    user_location: str = Form(""),
) -> RedirectResponse:
    """Save user settings to a .env file in the data directory."""
    jk = jooble_api_key.strip()[:256]
    rk = reed_api_key.strip()[:256]
    ul = user_location.strip()[:256]
    env = _load_user_env()
    # The key fields render blank (masked) — a blank submit means "keep the
    # current key", so masking never silently wipes a stored key. Update only
    # when the user actually typed a new one.
    if jk:
        env["JOBHUNT_JOOBLE_API_KEY"] = jk
        settings.jooble_api_key = jk
    if rk:
        env["JOBHUNT_REED_API_KEY"] = rk
        settings.reed_api_key = rk
    env["JOBHUNT_USER_LOCATION"] = ul
    _save_user_env(env)
    settings.user_location = ul
    return RedirectResponse("/settings", status_code=303)


@app.get("/api/check-update")
def api_check_update() -> JSONResponse:
    """Check GitHub for a newer release without installing anything."""
    import httpx

    try:
        resp = httpx.get(
            f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=10,
            follow_redirects=True,
        )
        if resp.status_code == 404:
            return JSONResponse({"ok": True, "update_available": False,
                                 "message": f"You are on v{__version__}. No releases found."})
        resp.raise_for_status()
        data = resp.json()
        latest_tag = data.get("tag_name", "").lstrip("v")
        current_parts = tuple(int(x) for x in __version__.split("."))
        try:
            latest_parts = tuple(int(x) for x in latest_tag.split("."))
        except (ValueError, AttributeError):
            latest_parts = (0, 0, 0)
        if latest_parts > current_parts:
            return JSONResponse({
                "ok": True, "update_available": True,
                "latest": latest_tag, "current": __version__,
                "url": data.get("html_url", ""),
                "message": f"Update available: v{latest_tag} (you have v{__version__})",
            })
        return JSONResponse({
            "ok": True, "update_available": False,
            "latest": latest_tag, "current": __version__,
            "message": f"You are on the latest version (v{__version__}).",
        })
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "message": f"Could not check for updates: {exc}"})


@app.post("/api/update")
def api_update() -> JSONResponse:
    """Update jobhunt. For uv/pipx installs, runs the upgrade command.

    For binary installs, returns the download URL so the frontend can
    offer a direct download link.
    """
    import platform
    import shutil
    import subprocess

    method = _detect_install_method()

    if method == "binary":
        # Binary users: check for new release and provide download link.
        import httpx

        try:
            resp = httpx.get(
                f"https://api.github.com/repos/{_GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
                timeout=10,
                follow_redirects=True,
            )
            resp.raise_for_status()
            data = resp.json()
            latest_tag = data.get("tag_name", "").lstrip("v")
            current_parts = tuple(int(x) for x in __version__.split("."))
            try:
                latest_parts = tuple(int(x) for x in latest_tag.split("."))
            except (ValueError, AttributeError):
                latest_parts = (0, 0, 0)
            if latest_parts <= current_parts:
                return JSONResponse({
                    "ok": True,
                    "message": f"Already on the latest version (v{__version__}).",
                })
            # Find the right asset for this platform.
            system = platform.system().lower()
            machine = platform.machine().lower()
            suffix = ""
            if system == "windows":
                suffix = "windows-x86_64.exe"
            elif system == "darwin":
                suffix = "macos-arm64" if "arm" in machine or "aarch" in machine else "macos-x86_64"
            else:
                suffix = "linux-x86_64"
            download_url = ""
            for asset in data.get("assets", []):
                if asset["name"].endswith(suffix):
                    download_url = asset["browser_download_url"]
                    break
            if download_url:
                msg = (
                    f"v{latest_tag} is available. "
                    "Download the new binary, replace this one, and restart."
                )
                return JSONResponse({
                    "ok": True,
                    "message": msg,
                    "download_url": download_url,
                    "latest": latest_tag,
                })
            msg = (
                f"v{latest_tag} is available but no binary found "
                f"for {system}/{machine}. "
                f"Download from: {data.get('html_url', '')}"
            )
            return JSONResponse({"ok": True, "message": msg})
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"ok": False, "message": f"Could not check for updates: {exc}"})

    elif method == "uv":
        uv = shutil.which("uv")
        result = subprocess.run(
            [uv, "tool", "install", "--reinstall", "--upgrade", "jobhunt-app"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            msg = (
                result.stdout.strip()
                or "jobhunt updated. Restart to use the new version."
            )
            return JSONResponse({"ok": True, "message": msg})
        return JSONResponse({
            "ok": False,
            "message": result.stderr.strip() or "Update failed.",
        })

    elif method == "pipx":
        pipx = shutil.which("pipx")
        result = subprocess.run(
            [pipx, "upgrade", "jobhunt-app"],
            capture_output=True, text=True, timeout=120,
        )
        msg = result.stdout.strip() or result.stderr.strip() or "done"
        return JSONResponse({"ok": result.returncode == 0, "message": msg})

    else:
        return JSONResponse({
            "ok": False,
            "message": "Could not determine install method. Download the latest from: "
                       f"https://github.com/{_GITHUB_REPO}/releases/latest",
        })


@app.post("/api/uninstall")
def api_uninstall() -> JSONResponse:
    """Return uninstall instructions appropriate for the install method.

    Kept for backward compatibility — the one-click button on the Settings page
    calls /api/uninstall-now (below) instead.
    """
    method = _detect_install_method()
    data_msg = (
        f"\n\nYour job data is in:\n  {settings.data_dir}\n"
        "Delete that folder too for a clean removal."
    )

    if method == "binary":
        return JSONResponse({
            "ok": True,
            "message": "Delete the jobhunt file you downloaded. That's it." + data_msg,
        })
    elif method == "uv":
        return JSONResponse({
            "ok": True,
            "message": "Run this in your terminal:\n\n  uv tool uninstall jobhunt-app" + data_msg,
        })
    elif method == "pipx":
        return JSONResponse({
            "ok": True,
            "message": "Run this in your terminal:\n\n  pipx uninstall jobhunt-app" + data_msg,
        })
    return JSONResponse({
        "ok": True,
        "message": "Run this in your terminal:\n\n  pip uninstall jobhunt-app" + data_msg,
    })


@app.post("/api/uninstall-now")
def api_uninstall_now() -> JSONResponse:
    """One-click uninstall. Schedules the actual uninstall to run in a
    detached subprocess AFTER our own server exits — on Windows the running
    binary has its files locked, so we must release them first.
    """
    import shutil
    import subprocess
    import sys
    import threading

    method = _detect_install_method()
    data_msg = (
        f"\nYour job data is at:\n  {settings.data_dir}\n"
        "Delete that folder for a fully clean removal."
    )

    if method == "binary":
        # Self-deleting a running binary is platform-specific and risky — just
        # tell the user what to do.
        return JSONResponse({
            "ok": True,
            "uninstalled": False,
            "message": (
                "You installed jobhunt as a single binary. "
                "Delete the jobhunt file you downloaded — that's the whole "
                "uninstall.\n" + data_msg
            ),
        })

    cmd: list[str] | None = None
    if method == "uv":
        uv = shutil.which("uv")
        if uv:
            cmd = [uv, "tool", "uninstall", "jobhunt-app"]
    elif method == "pipx":
        pipx = shutil.which("pipx")
        if pipx:
            cmd = [pipx, "uninstall", "jobhunt-app"]

    if cmd is None:
        return JSONResponse({
            "ok": False,
            "uninstalled": False,
            "message": (
                f"Could not find the {method} tool on your PATH. "
                "Open a terminal and run `pip uninstall jobhunt-app` instead.\n"
                + data_msg
            ),
        })

    # We can't call uv/pipx synchronously here because on Windows the running
    # binary has its files locked — uv tries to delete them and fails with
    # WinError 32. The fix: spawn the uninstall as a fully detached process,
    # have it wait a moment, then run while we're already gone.
    is_windows = sys.platform.startswith("win")
    if is_windows:
        # `start /b` + `timeout` runs the uninstall in a detached cmd window
        # after a short wait. /min hides the window. We deliberately don't
        # capture stdout — once we exit the user can't see it anyway.
        wrapper = (
            "timeout /t 2 /nobreak >nul && "
            + subprocess.list2cmdline(cmd)
        )
        try:
            subprocess.Popen(
                ["cmd.exe", "/c", wrapper],
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | getattr(subprocess, "DETACHED_PROCESS", 0)
                ),
                close_fds=True,
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({
                "ok": False,
                "uninstalled": False,
                "message": f"Uninstall command failed to start: {exc}\n" + data_msg,
            })
    else:
        # On Unix the running process can have its files unlinked while
        # executing — just shell out with a small delay so the response
        # flushes first.
        shell_cmd = "sleep 2 && " + " ".join(
            subprocess.list2cmdline([part]) for part in cmd
        )
        try:
            subprocess.Popen(
                ["/bin/sh", "-c", shell_cmd],
                start_new_session=True,
                close_fds=True,
            )
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({
                "ok": False,
                "uninstalled": False,
                "message": f"Uninstall command failed to start: {exc}\n" + data_msg,
            })

    # Schedule our own exit so the running binary releases its files before
    # the detached uninstaller tries to remove them. os._exit is brutal but
    # the only reliable way to stop uvicorn cross-platform from inside a
    # request handler — SIGTERM is unreliable on Windows.
    def _delayed_exit() -> None:
        import time

        time.sleep(1.0)
        os._exit(0)

    threading.Thread(target=_delayed_exit, daemon=True).start()

    return JSONResponse({
        "ok": True,
        "uninstalled": True,
        "message": (
            "Uninstall scheduled. jobhunt is closing now; the package will be "
            "removed in a few seconds. You can close this browser tab.\n"
            + data_msg
        ),
    })


@app.post("/api/clear-data")
def api_clear_data() -> JSONResponse:
    """Drop all job data but keep the schema intact."""
    with db_session() as s:
        from .models import Job, ScrapeRun
        s.execute(Job.__table__.delete())
        s.execute(ScrapeRun.__table__.delete())
    return JSONResponse({
        "ok": True,
        "message": "All jobs cleared. Click Refresh to re-populate.",
    })


# ---------- meta ----------


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request) -> HTMLResponse:
    """In-app help: shortcuts to common questions, troubleshooting, what
    each filter means. The non-technical user's safety net."""
    return templates.TemplateResponse(
        request,
        "help.html",
        {"nav": "help", "today": _today()},
    )


@app.get("/api/healthz")
def healthz() -> dict:
    """Operational status. Designed for both human curl + scripted
    monitoring. Adds counts the Settings page already shows so a single
    request gives a full picture."""
    import os as _os

    sources_health = _source_health_summary()
    job_count = 0
    last_refresh: str | None = None
    db_bytes = 0
    try:
        with db_session() as s:
            job_count = s.execute(
                select(func.count()).select_from(Job)
            ).scalar_one()
            row = s.execute(
                select(ScrapeRun.started_at)
                .order_by(ScrapeRun.started_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                if row.tzinfo is None:
                    row = row.replace(tzinfo=UTC)
                last_refresh = row.isoformat()
        if settings.db_path.exists():
            db_bytes = _os.path.getsize(settings.db_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("healthz stats failed: %s", exc)
    return {
        "ok": True,
        "version": __version__,
        "jobs": job_count,
        "sources": sources_health,
        "last_refresh": last_refresh,
        "db_bytes": db_bytes,
    }


@app.get("/api/scheduler")
def api_scheduler() -> dict:
    return sched_module.status()


@app.post("/api/scheduler/start")
def api_scheduler_start(interval_minutes: int | None = None) -> dict:
    sched_module.start(interval_minutes)
    return sched_module.status()


@app.post("/api/scheduler/stop")
def api_scheduler_stop() -> dict:
    sched_module.stop()
    return sched_module.status()
