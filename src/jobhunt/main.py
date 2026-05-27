from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from . import __version__
from . import scheduler as sched_module
from .alerts import check_alerts
from .config import settings
from .db import db_session, init_db
from .filters import JobQuery, count, facets, search
from .models import CVProfile, Job, SavedSearch, ScrapeRun
from .refresh import scrape_all
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

app = FastAPI(title="jobhunt", version=__version__)
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


@app.on_event("startup")
async def _on_startup() -> None:
    init_db()
    if settings.refresh_interval_minutes > 0:
        sched_module.start()


@app.on_event("shutdown")
def _on_shutdown() -> None:
    sched_module.stop()


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
        min_cv_match=_safe_float(min_cv_match),
        sort=sort or "score",
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
            "nav": "search",
            "today": _today(),
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
                }
                for j in rows
            ],
        }
    )


@app.post("/api/refresh")
async def api_refresh() -> JSONResponse:
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
    return templates.TemplateResponse(
        request,
        "alerts.html",
        {"searches": searches, "nav": "alerts", "today": _today()},
    )


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
) -> RedirectResponse:
    name = name.strip()
    if not name:
        raise HTTPException(400, "name required")
    query_json = {
        "q": q.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "remote": remote.strip(),
        "level": level.strip(),
        "degree": degree.strip(),
        "max_years": max_years,
        "languages": [s.strip().lower() for s in languages.split(",") if s.strip()],
        "skills": [s.strip().lower() for s in skills.split(",") if s.strip()],
        "posted_within_days": posted_within_days,
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
    try:
        from .cv import cv_status
        status = cv_status()
        cv_available = True
    except ImportError as exc:
        status = {"loaded": False, "error": str(exc)}
        cv_available = False
    return templates.TemplateResponse(
        request,
        "cv.html",
        {"cv": status, "cv_available": cv_available, "nav": "cv", "today": _today()},
    )


@app.post("/cv/upload")
async def cv_upload(file: UploadFile = File(...)) -> RedirectResponse:
    from .cv import match_all_jobs, upload_cv

    content = await file.read()
    try:
        upload_cv(file.filename or "cv.txt", content)
    except (ValueError, ImportError) as exc:
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
    return _render_sources(request)


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
        },
    )


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
            [uv, "tool", "install", "--reinstall", "--upgrade",
             f"git+https://github.com/{_GITHUB_REPO}.git"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            msg = result.stdout.strip() or "jobhunt updated. Restart to use the new version."
            return JSONResponse({"ok": True, "message": msg})
        return JSONResponse({"ok": False, "message": result.stderr.strip() or "Update failed."})

    elif method == "pipx":
        pipx = shutil.which("pipx")
        result = subprocess.run(
            [pipx, "upgrade", "jobhunt"],
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
    """Return uninstall instructions appropriate for the install method."""
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
            "message": "Run this in your terminal:\n\n  uv tool uninstall jobhunt" + data_msg,
        })
    elif method == "pipx":
        return JSONResponse({
            "ok": True,
            "message": "Run this in your terminal:\n\n  pipx uninstall jobhunt" + data_msg,
        })
    return JSONResponse({
        "ok": True,
        "message": "Run this in your terminal:\n\n  pip uninstall jobhunt" + data_msg,
    })


@app.post("/api/clear-data")
def api_clear_data() -> JSONResponse:
    """Delete the local database. Jobs will be re-scraped on next refresh."""
    import os

    db = settings.db_path
    if db.exists():
        os.remove(db)
        init_db()
        return JSONResponse({
            "ok": True,
            "message": "Database cleared. Pull listings to re-populate.",
        })
    return JSONResponse({"ok": True, "message": "Database already empty."})


# ---------- meta ----------


@app.get("/api/healthz")
def healthz() -> dict:
    return {"ok": True, "version": __version__}


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
