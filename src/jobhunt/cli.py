from __future__ import annotations

import asyncio
import socket
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

app = typer.Typer(no_args_is_help=True, help="jobhunt — local job board aggregator.")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"jobhunt {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """jobhunt — local job board aggregator."""


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
    uvicorn.run(
        "jobhunt.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=reload,
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
    init_db()
    if schedule > 0:
        import os
        os.environ["JOBHUNT_REFRESH_INTERVAL_MINUTES"] = str(schedule)
    chosen = _find_free_port(port or settings.port)
    url = f"http://127.0.0.1:{chosen}/"
    typer.echo(f"jobhunt {__version__}")
    typer.echo(f"  data dir : {settings.data_dir}")
    typer.echo(f"  serving  : {url}")
    typer.echo("  ctrl+c to stop.")

    if not no_browser:
        threading.Thread(
            target=lambda: (time.sleep(0.6), webbrowser.open(url)),
            daemon=True,
        ).start()

    uvicorn.run(
        "jobhunt.main:app",
        host="127.0.0.1",
        port=chosen,
        log_level="warning",
    )


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


if __name__ == "__main__":
    app()
