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
from .db import db_session, init_db
from .refresh import scrape_all

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


@app.command()
def doctor() -> None:
    """Check all sources and report which ones need attention."""
    import asyncio

    import httpx

    from .config import settings
    from .refresh import load_sources
    from .scrapers import SCRAPER_REGISTRY

    init_db()
    sources = load_sources()
    typer.echo(f"checking {len(sources)} sources...\n")

    async def check_source(spec: dict) -> tuple[str, str, str]:
        name = spec.get("source", "?")
        board = spec.get("board", "")
        company = spec.get("company", board)
        cls = SCRAPER_REGISTRY.get(name)
        if cls is None:
            return (company, "error", f"unknown source type: {name}")
        headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
        async with httpx.AsyncClient(
            headers=headers, timeout=15, follow_redirects=True,
        ) as client:
            try:
                scraper = cls(client=client, board=board)
                jobs = [j async for j in scraper.fetch()]
                if not jobs:
                    return (company, "warn", f"0 jobs returned ({name}/{board})")
                return (company, "ok", f"{len(jobs)} jobs")
            except Exception as exc:  # noqa: BLE001
                return (company, "error", f"{type(exc).__name__}: {exc}")

    async def run_all() -> list[tuple[str, str, str]]:
        return await asyncio.gather(*[check_source(s) for s in sources])

    results = asyncio.run(run_all())
    ok = [(c, m) for c, s, m in results if s == "ok"]
    warn = [(c, m) for c, s, m in results if s == "warn"]
    errors = [(c, m) for c, s, m in results if s == "error"]

    for company, msg in ok:
        typer.echo(f"  ok    {company:30s} {msg}")
    for company, msg in warn:
        typer.echo(f"  WARN  {company:30s} {msg}")
    for company, msg in errors:
        typer.echo(f"  FAIL  {company:30s} {msg}")

    typer.echo(f"\n{len(ok)} ok · {len(warn)} warnings · {len(errors)} errors")
    if errors:
        typer.echo("\nFailed sources may have changed their careers page URL.")
        typer.echo("Remove them: edit src/jobhunt/sources.yaml or use the Sources page in the UI.")


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
