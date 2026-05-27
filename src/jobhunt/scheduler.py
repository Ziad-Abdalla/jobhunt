"""Background scheduler for unattended local refreshes.

Self-update mechanism: APScheduler runs the scrape pipeline on a fixed interval
(default 6 hours). Lives entirely in-process, no external cron needed, free.
Opt-in via env var or the `--schedule` flag — defaults off so first-run is calm.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .refresh import scrape_all

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_last_run: dict[str, object] = {"at": None, "result": None, "error": None}


async def _job() -> None:
    log.info("scheduler: starting scheduled scrape")
    try:
        result = await scrape_all()
        _last_run["at"] = datetime.now(UTC).isoformat()
        _last_run["result"] = result
        _last_run["error"] = None
        log.info("scheduler: completed (%s)", result)
        # Best-effort alert checking after each refresh.
        try:
            from .alerts import check_alerts

            await check_alerts()
        except Exception as exc:  # noqa: BLE001
            log.warning("scheduler: alert check failed: %s", exc)
    except Exception as exc:  # noqa: BLE001
        _last_run["at"] = datetime.now(UTC).isoformat()
        _last_run["error"] = f"{type(exc).__name__}: {exc}"
        log.exception("scheduler: scrape failed")


def start(interval_minutes: int | None = None) -> None:
    global _scheduler
    if _scheduler is not None:
        return
    interval = interval_minutes or settings.refresh_interval_minutes
    if interval <= 0:
        log.info("scheduler: disabled (interval <= 0)")
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(_job, "interval", minutes=interval, id="refresh", max_instances=1)
    _scheduler.start()
    log.info("scheduler: started; refreshing every %d minutes", interval)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def status() -> dict:
    if _scheduler is None:
        return {"running": False, "last_run": _last_run}
    jobs = []
    for j in _scheduler.get_jobs():
        jobs.append(
            {
                "id": j.id,
                "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
            }
        )
    return {
        "running": True,
        "interval_minutes": settings.refresh_interval_minutes,
        "jobs": jobs,
        "last_run": _last_run,
    }


def run_once_blocking() -> dict:
    """Convenience for the CLI: run one scrape and return the result."""
    return asyncio.run(scrape_all())
