from __future__ import annotations

import asyncio
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import typer
import uvicorn

from . import __version__
from .config import settings
from .db import check_integrity, db_session, init_db
from .refresh import scrape_all


def _setup_file_logging() -> None:
    """Add a rotating file handler so a user can send the log when they
    hit a bug. Lives at `data_dir/jobhunt.log`, capped at 1 MB × 3 backups
    (~4 MB max disk use). Idempotent — never double-installs the handler."""
    import logging
    import logging.handlers

    log_path = settings.data_dir / "jobhunt.log"
    root = logging.getLogger("jobhunt")
    if any(getattr(h, "_jobhunt_file", False) for h in root.handlers):
        return  # already installed
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        ))
        handler._jobhunt_file = True  # type: ignore[attr-defined]
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    except OSError:
        # Read-only filesystem or similar — log to stderr only.
        pass

_FROZEN = getattr(sys, "frozen", False)

app = typer.Typer(invoke_without_command=True, help="jobhunt — local job board aggregator.")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"jobhunt {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """jobhunt — local job board aggregator."""
    _setup_file_logging()
    if ctx.invoked_subcommand is None:
        app_mode(port=None, no_browser=False, schedule=0)


def _is_port_in_use(port: int) -> bool:
    """Check if a port is already bound (another jobhunt instance running)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def _find_free_port(preferred: int) -> int:
    """Return preferred port if free; otherwise pick a free ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


apply_app = typer.Typer(help="Application-queue commands (Cowork handoff).")
app.add_typer(apply_app, name="apply")


@apply_app.command("export")
def apply_export(
    status: str = typer.Option("queued", help="queued | drafted | approved | submitted"),
) -> None:
    """Print the Cowork handoff JSON (mirror of GET /api/cowork/export).

    Honors the same default-OFF toggle as the HTTP endpoint; the CLI runs
    on the local machine by definition, so the loopback gate is satisfied."""
    import json as _json

    from .config import settings as _settings
    from .cowork_export import build_export_document
    from .cowork_models import APPLICATION_STATUSES
    from .db import db_session as _dbs

    if not _settings.cowork_export:
        typer.echo(
            "Cowork export is disabled. Set JOBHUNT_COWORK_EXPORT=1 to enable.",
            err=True,
        )
        raise typer.Exit(code=2)
    if status not in APPLICATION_STATUSES:
        typer.echo(f"unknown status: {status}", err=True)
        raise typer.Exit(code=2)
    init_db()
    with _dbs() as s:
        doc = build_export_document(s, status)
    typer.echo(_json.dumps(doc, ensure_ascii=False, indent=2))


@app.command()
def scrape() -> None:
    """Run all configured scrapers, dedup, and sweep stale listings."""
    init_db()
    result = asyncio.run(scrape_all())
    typer.echo(
        f"scraped {result['sources']} sources · "
        f"{result['added']} added · {result['seen']} seen · {result['removed']} removed"
    )


@app.command()
def serve(
    host: str = typer.Option(None, help="Bind host (defaults to env JOBHUNT_HOST)."),
    port: int = typer.Option(None, help="Bind port (defaults to env JOBHUNT_PORT)."),
    reload: bool = typer.Option(False, help="Enable auto-reload (dev only)."),
    schedule: int = typer.Option(
        0, "--schedule",
        help="Auto-refresh every N minutes in the background (0 = off).",
    ),
) -> None:
    """Start the web UI server in the foreground (no browser)."""
    init_db()
    if schedule > 0:
        import os
        os.environ["JOBHUNT_REFRESH_INTERVAL_MINUTES"] = str(schedule)
    if _FROZEN or not reload:
        from .main import app as webapp
        uvicorn.run(
            webapp,
            host=host or settings.host,
            port=port or settings.port,
        )
    else:
        uvicorn.run(
            "jobhunt.main:app",
            host=host or settings.host,
            port=port or settings.port,
            reload=True,
        )


@app.command(name="app")
def app_mode(
    port: int = typer.Option(None, help="Preferred port; an ephemeral port is used if busy."),
    no_browser: bool = typer.Option(False, help="Don't open a browser tab."),
    schedule: int = typer.Option(
        0, "--schedule",
        help="Auto-refresh every N minutes in the background (0 = off).",
    ),
) -> None:
    """Launch jobhunt as a local app — starts the server and opens it in your browser."""
    preferred = port or settings.port

    if not no_browser and _is_port_in_use(preferred):
        url = f"http://127.0.0.1:{preferred}/"
        typer.echo(f"jobhunt is already running at {url}")
        webbrowser.open(url)
        return

    init_db()
    if schedule > 0:
        import os
        os.environ["JOBHUNT_REFRESH_INTERVAL_MINUTES"] = str(schedule)
    chosen = preferred
    url = f"http://127.0.0.1:{chosen}/"
    typer.echo(f"jobhunt {__version__}")
    typer.echo(f"  data dir : {settings.data_dir}")
    typer.echo(f"  serving  : {url}")
    typer.echo("  ctrl+c to stop.")

    if not no_browser:
        threading.Thread(
            target=lambda: (time.sleep(0.8), webbrowser.open(url)),
            daemon=True,
        ).start()

    if _FROZEN:
        from .main import app as webapp
        uvicorn.run(webapp, host="127.0.0.1", port=chosen, log_level="warning")
    else:
        uvicorn.run("jobhunt.main:app", host="127.0.0.1", port=chosen, log_level="warning")


@app.command()
def info() -> None:
    """Show where jobhunt is keeping its files."""
    from .config import APP_NAME

    typer.echo(f"jobhunt {__version__}  ({APP_NAME})")
    typer.echo(f"  data dir          : {settings.data_dir}")
    typer.echo(f"  database          : {settings.db_path}")
    typer.echo(f"  sources (default) : {settings.sources_file}")
    typer.echo(f"  sources (local)   : {settings.local_sources_file}")
    typer.echo(f"  refresh interval  : {settings.refresh_interval_minutes} min")
    typer.echo(f"  bind              : {settings.host}:{settings.port}")


@app.command()
def stats() -> None:
    """Print quick stats about the local DB."""
    from sqlalchemy import func, select

    from .models import Job, ScrapeRun

    init_db()
    with db_session() as s:
        total = s.execute(select(func.count()).select_from(Job)).scalar_one()
        by_source = s.execute(
            select(Job.source, func.count()).group_by(Job.source).order_by(func.count().desc())
        ).all()
        last_run = s.execute(
            select(ScrapeRun).order_by(ScrapeRun.id.desc()).limit(1)
        ).scalar_one_or_none()
    typer.echo(f"total jobs: {total}")
    for source, n in by_source:
        typer.echo(f"  {source}: {n}")
    if last_run:
        typer.echo(
            f"last run: {last_run.source} @ {last_run.started_at:%Y-%m-%d %H:%M} "
            f"({last_run.jobs_added} added, error={last_run.error or '—'})"
        )


@app.command(name="match-cv")
def match_cv(file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False)) -> None:
    """Upload your CV, embed it locally, and score all jobs against it.

    Requires the [match] extra: pip install -e '.[match]'
    """
    try:
        from .cv import match_all_jobs, upload_cv
    except ImportError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    init_db()
    content = file.read_bytes()
    info_dict = upload_cv(file.name, content)
    typer.echo(f"loaded CV: {info_dict}")
    typer.echo("scoring all jobs against CV…")
    n = match_all_jobs()
    typer.echo(f"scored {n} jobs")


@app.command()
def check_alerts() -> None:
    """Manually run the saved-search alert check."""
    from .alerts import check_alerts as do_check

    init_db()
    result = asyncio.run(do_check())
    typer.echo(f"notified {result['notified']} from {result['searches']} saved searches")


@app.command(name="list-sources")
def list_sources() -> None:
    """List which scrapers are configured."""
    from .refresh import load_sources

    init_db()
    items = load_sources()
    typer.echo(f"{len(items)} configured sources:")
    by_kind: dict[str, int] = {}
    for it in items:
        by_kind[it.get("source", "?")] = by_kind.get(it.get("source", "?"), 0) + 1
    for kind, n in sorted(by_kind.items()):
        typer.echo(f"  {kind}: {n}")


_API_KEY_LINE_RE = None  # populated lazily


def _redact_env(env_text: str) -> str:
    """Strip API key values from a .env blob so a leaked backup zip can't
    expose live credentials. Keys are replaced with a sentinel that
    `restore` recognises and preserves."""
    import re

    global _API_KEY_LINE_RE
    if _API_KEY_LINE_RE is None:
        # Any JOBHUNT_* line whose key ends in a secret-bearing suffix:
        # API_KEY, TOKEN, PASSWORD, or SECRET (covers Jooble/Reed keys plus
        # the P7 TELEGRAM_BOT_TOKEN and SMTP_PASSWORD).
        _API_KEY_LINE_RE = re.compile(
            r"^(JOBHUNT_[A-Z0-9_]*?(?:API_KEY|TOKEN|PASSWORD|SECRET))\s*=.*$",
            re.MULTILINE,
        )
    return _API_KEY_LINE_RE.sub(
        r"\1=__REDACTED_BY_BACKUP__regenerate_via_settings__",
        env_text,
    )


@app.command()
def backup(
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output file. Defaults to jobhunt-backup-<timestamp>.zip in the data folder.",
    ),
    include_secrets: bool = typer.Option(
        False, "--include-secrets",
        help=(
            "Include raw API keys in the backup. Default: redacted. "
            "Only use this if you trust where the backup is going — "
            "the file is a plain zip, not encrypted."
        ),
    ),
) -> None:
    """Export your saved searches, CV profile, alerts, and source overrides
    to a zip file. Doesn't dump the job database itself — that's transient
    and gets re-scraped — only the data you'd care about losing.

    API keys are redacted by default — use --include-secrets to keep
    them (only if the backup will stay on a trusted machine)."""
    import json
    import zipfile
    from datetime import UTC, datetime

    from .models import CVProfile, SavedSearch

    init_db()
    if output is None:
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        output = settings.data_dir / f"jobhunt-backup-{ts}.zip"
    output.parent.mkdir(parents=True, exist_ok=True)

    with db_session() as s:
        searches = [
            {
                "name": r.name,
                "query_json": r.query_json,
                "notify": r.notify,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "notified_job_ids": r.notified_job_ids or [],
            }
            for r in s.query(SavedSearch).all()
        ]
        cv = s.get(CVProfile, 1)
        cv_data = None
        if cv is not None:
            cv_data = {
                "filename": cv.filename,
                "text": cv.text,
                "embedding": list(cv.embedding or []),
                "model": cv.model,
                "uploaded_at": cv.uploaded_at.isoformat() if cv.uploaded_at else None,
                "detected_skills": list(cv.detected_skills or []),
                "detected_languages": list(cv.detected_languages or []),
            }

    local_sources_path = Path(settings.local_sources_file)
    local_sources_yaml = (
        local_sources_path.read_text() if local_sources_path.exists() else ""
    )
    env_path = settings.data_dir / ".env"
    env_text = env_path.read_text() if env_path.exists() else ""
    env_for_backup = env_text if include_secrets else _redact_env(env_text)
    keys_were_redacted = bool(env_text) and env_for_backup != env_text

    payload = {
        "schema": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "version": __version__,
        "saved_searches": searches,
        "cv_profile": cv_data,
        "local_sources_yaml": local_sources_yaml,
        "env": env_for_backup,
        "secrets_included": include_secrets,
    }
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("jobhunt-backup.json", json.dumps(payload, indent=2))
    typer.echo(f"Backup written: {output}")
    typer.echo(f"  saved searches: {len(searches)}")
    typer.echo(f"  CV profile:     {'yes' if cv_data else 'no'}")
    typer.echo(f"  local sources:  {'yes' if local_sources_yaml else 'no'}")
    if include_secrets:
        typer.echo(
            "  ⚠ API keys included verbatim — treat this file like a password.",
            err=True,
        )
    elif keys_were_redacted:
        typer.echo("  API keys: REDACTED (re-enter on the Settings page after restore).")


@app.command()
def restore(
    backup_file: Path = typer.Argument(..., help="A zip produced by `jobhunt backup`."),
    force: bool = typer.Option(
        False, "--force", help="Skip the confirmation prompt; overwrites existing data.",
    ),
) -> None:
    """Restore saved searches, CV, alerts, and local sources from a backup
    zip. Refuses to run on a malformed file. Asks for confirmation unless
    `--force` is set."""
    import json
    import zipfile

    from .models import CVProfile, SavedSearch

    if not backup_file.exists():
        typer.echo(f"ERROR: {backup_file} not found", err=True)
        raise typer.Exit(1)

    try:
        with zipfile.ZipFile(backup_file) as z:
            with z.open("jobhunt-backup.json") as f:
                payload = json.load(f)
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        typer.echo(f"ERROR: not a valid jobhunt backup ({exc})", err=True)
        raise typer.Exit(1) from exc

    if payload.get("schema") != 1:
        typer.echo(
            f"ERROR: backup schema {payload.get('schema')} not supported; "
            "this jobhunt version expects schema 1.",
            err=True,
        )
        raise typer.Exit(1)

    if not force:
        typer.echo(f"About to restore: {len(payload.get('saved_searches', []))} saved searches, "
                   f"{'1' if payload.get('cv_profile') else '0'} CV, "
                   f"local sources, env settings.")
        if not typer.confirm("Overwrite existing data?"):
            typer.echo("Aborted.")
            raise typer.Exit(0)

    init_db()
    with db_session() as s:
        s.query(SavedSearch).delete()
        for r in payload.get("saved_searches", []):
            from datetime import datetime
            created_at = None
            if r.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(r["created_at"])
                except ValueError:
                    created_at = None
            s.add(SavedSearch(
                name=r["name"][:128],
                query_json=r.get("query_json") or {},
                notify=bool(r.get("notify", True)),
                created_at=created_at,
                notified_job_ids=list(r.get("notified_job_ids") or []),
            ))
        s.query(CVProfile).delete()
        cv = payload.get("cv_profile")
        if cv:
            from datetime import datetime
            uploaded_at = None
            if cv.get("uploaded_at"):
                try:
                    uploaded_at = datetime.fromisoformat(cv["uploaded_at"])
                except ValueError:
                    uploaded_at = None
            s.add(CVProfile(
                id=1,
                filename=cv.get("filename", ""),
                text=cv.get("text", ""),
                embedding=list(cv.get("embedding") or []),
                model=cv.get("model", ""),
                uploaded_at=uploaded_at,
                detected_skills=list(cv.get("detected_skills") or []),
                detected_languages=list(cv.get("detected_languages") or []),
            ))

    # local_sources.yaml: defence against a hostile backup pointing scrapers
    # at attacker-controlled hosts. Only accept entries whose `source` is a
    # known scraper kind from SCRAPER_REGISTRY; reject everything else
    # rather than silently writing it through.
    local_sources_yaml = payload.get("local_sources_yaml", "")
    if local_sources_yaml:
        import yaml as _yaml

        from .scrapers import SCRAPER_REGISTRY

        try:
            parsed = _yaml.safe_load(local_sources_yaml) or []
        except _yaml.YAMLError as exc:
            typer.echo(f"WARNING: local_sources YAML invalid, skipping: {exc}", err=True)
            parsed = None
        if isinstance(parsed, list):
            safe_entries = [
                e for e in parsed
                if isinstance(e, dict)
                and e.get("source") in SCRAPER_REGISTRY
                and isinstance(e.get("board"), str)
            ]
            dropped = (len(parsed) - len(safe_entries)) if parsed else 0
            if dropped:
                typer.echo(
                    f"WARNING: dropped {dropped} local_sources entries with "
                    "unknown scraper kinds.",
                    err=True,
                )
            Path(settings.local_sources_file).parent.mkdir(parents=True, exist_ok=True)
            Path(settings.local_sources_file).write_text(
                _yaml.safe_dump(safe_entries, sort_keys=False, allow_unicode=True)
            )

    # .env: same defence. A backup can carry user-set JOBHUNT_* keys, but
    # we allowlist known ones to stop a backup from injecting JOBHUNT_*=
    # variables we'd act on (data_dir overrides, webhook URLs, etc.).
    env_text = payload.get("env", "")
    if env_text:
        _ALLOWED_ENV_KEYS = {
            "JOBHUNT_JOOBLE_API_KEY",
            "JOBHUNT_REED_API_KEY",
            "JOBHUNT_USER_LOCATION",
        }
        kept_lines: list[str] = []
        for raw in env_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, _val = line.partition("=")
            if key.strip() in _ALLOWED_ENV_KEYS:
                kept_lines.append(line)
        (settings.data_dir / ".env").write_text("\n".join(kept_lines) + "\n" if kept_lines else "")
        if payload.get("secrets_included") is False:
            typer.echo(
                "Note: API keys were redacted in this backup. "
                "Re-enter them on the Settings page.",
            )

    typer.echo("Restore complete. Run `jobhunt` to start with the recovered data.")


@app.command()
def doctor(
    json_output: bool = typer.Option(
        False, "--json", help="Emit a machine-readable JSON report (used by the source-maintenance skill).",
    ),
) -> None:
    """Check all sources and report which ones need attention."""
    import asyncio
    import json as _json

    import httpx

    from .config import settings
    from .refresh import load_sources
    from .scrapers import SCRAPER_REGISTRY

    init_db()
    sources = load_sources()
    integrity_ok, integrity_msg = check_integrity()
    if not json_output:
        if integrity_ok:
            typer.echo("  db integrity: ok")
        else:
            typer.echo(f"  db integrity: FAIL — {integrity_msg}")
        typer.echo(f"checking {len(sources)} sources...\n")

    async def check_source(spec: dict) -> dict:
        name = spec.get("source", "?")
        board = spec.get("board", "")
        company = spec.get("company", board)
        cls = SCRAPER_REGISTRY.get(name)
        if cls is None:
            return {
                "source": name, "board": board, "company": company,
                "status": "error", "jobs_seen": 0,
                "detail": f"unknown source type: {name}",
            }
        headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
        async with httpx.AsyncClient(
            headers=headers, timeout=15, follow_redirects=True,
        ) as client:
            try:
                scraper = cls(client=client, board=board)
                jobs = [j async for j in scraper.fetch()]
                if not jobs:
                    return {
                        "source": name, "board": board, "company": company,
                        "status": "warn", "jobs_seen": 0,
                        "detail": "0 jobs returned",
                    }
                return {
                    "source": name, "board": board, "company": company,
                    "status": "ok", "jobs_seen": len(jobs),
                    "detail": f"{len(jobs)} jobs",
                }
            except Exception as exc:  # noqa: BLE001
                return {
                    "source": name, "board": board, "company": company,
                    "status": "error", "jobs_seen": 0,
                    "detail": f"{type(exc).__name__}: {exc}",
                }

    async def run_all() -> list[dict]:
        # Bound concurrency so validating 150+ sources (many sharing a host) doesn't
        # trip 429/WAF blocks during the maintenance skill's post-add health check.
        from .concurrency import gather_bounded

        return await gather_bounded(
            [lambda spec=spec: check_source(spec) for spec in sources],
            settings.concurrency,
        )

    results = asyncio.run(run_all())
    ok = [r for r in results if r["status"] == "ok"]
    warn = [r for r in results if r["status"] == "warn"]
    errors = [r for r in results if r["status"] == "error"]

    if json_output:
        # Stable schema for the source-maintenance skill to consume.
        typer.echo(_json.dumps({
            "total": len(results),
            "ok": len(ok),
            "warn": len(warn),
            "error": len(errors),
            "integrity": {"ok": integrity_ok, "message": integrity_msg},
            "results": results,
        }, indent=2))
        return

    for r in ok:
        typer.echo(f"  ok    {r['company']:30s} {r['detail']}")
    for r in warn:
        typer.echo(f"  WARN  {r['company']:30s} {r['detail']} ({r['source']}/{r['board']})")
    for r in errors:
        typer.echo(f"  FAIL  {r['company']:30s} {r['detail']}")

    typer.echo(f"\n{len(ok)} ok · {len(warn)} warnings · {len(errors)} errors")
    if errors:
        typer.echo("\nFailed sources may have changed their careers page URL.")
        typer.echo("Fix automatically: ask Claude 'run the source-maintenance skill'.")
        typer.echo("Fix manually: edit src/jobhunt/sources.yaml or use the Sources page in the UI.")


@app.command()
def update() -> None:
    """Update jobhunt to the latest version."""
    import shutil
    import subprocess

    uv = shutil.which("uv")
    pipx = shutil.which("pipx")

    if uv:
        typer.echo("updating via uv...")
        result = subprocess.run(
            [uv, "tool", "install", "--reinstall", "--upgrade", "jobhunt-app"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            typer.echo(result.stdout.strip() if result.stdout.strip() else "jobhunt is up to date.")
        else:
            typer.echo(f"upgrade failed: {result.stderr.strip()}", err=True)
            raise typer.Exit(1)
    elif pipx:
        typer.echo("updating via pipx...")
        subprocess.run([pipx, "upgrade", "jobhunt-app"], check=False)
    else:
        typer.echo(
            "could not find uv or pipx. update manually:\n"
            "  uv tool upgrade jobhunt\n"
            "  — or —\n"
            "  pipx upgrade jobhunt",
            err=True,
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
