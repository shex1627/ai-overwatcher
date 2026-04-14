"""APScheduler setup. In-process, SQLite-backed jobstore so timers survive restart."""
from __future__ import annotations

import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from overwatcher.config import get_settings

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        s = get_settings()
        jobstore = SQLAlchemyJobStore(url=s.database_url)
        _scheduler = AsyncIOScheduler(
            jobstores={"default": jobstore},
            timezone=s.tz,
            job_defaults={"misfire_grace_time": 300, "coalesce": True},
        )
    return _scheduler


def register_daily_jobs() -> None:
    """Idempotent cron registration. Uses replace_existing=True so restarts don't double-schedule."""
    from overwatcher.jobs import evening, heartbeat, morning, weekly

    s = get_settings()
    sch = get_scheduler()
    sch.add_job(
        morning.run, trigger="cron", hour=9, minute=0, timezone=s.tz,
        id="daily_morning", replace_existing=True,
    )
    sch.add_job(
        evening.run, trigger="cron", hour=21, minute=0, timezone=s.tz,
        id="daily_evening", replace_existing=True,
    )
    sch.add_job(
        weekly.run, trigger="cron", day_of_week="fri", hour=17, minute=0, timezone=s.tz,
        id="weekly_summary", replace_existing=True,
    )
    sch.add_job(
        heartbeat.run, trigger="cron", hour=12, minute=0, timezone=s.tz,
        id="system_heartbeat", replace_existing=True,
    )
    log.info("daily_jobs_registered")


def start() -> None:
    sch = get_scheduler()
    if not sch.running:
        sch.start()
        log.info("scheduler_started")
    register_daily_jobs()


def shutdown() -> None:
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
