"""Per-timer one-shot jobs. Scheduled on demand when a timer starts."""
from __future__ import annotations

import logging
from datetime import datetime

from overwatcher import repo, sms
from overwatcher.config import get_settings

log = logging.getLogger(__name__)


async def mid_check(timer_id: int) -> None:
    t = repo.get_timer(timer_id)
    if t is None or t.status != "active":
        log.info("mid_check_skipped_inactive", extra={"timer_id": timer_id})
        return
    settings = get_settings()
    now = datetime.now(settings.tz)
    # Passive on-track suppression: if user sent a progress note in the last 20 min, skip.
    if repo.last_progress_within(20, now=now):
        log.info("mid_check_suppressed_recent_progress", extra={"timer_id": timer_id})
        return
    body = f"Halfway through {t.task}. On track? yes / stuck / switching"
    sms.send_sms(body)
    repo.insert_message(
        ts=now.isoformat(),
        direction="out",
        type_="mid_check",
        raw_text=body,
        related_timer_id=timer_id,
    )


async def end_check(timer_id: int) -> None:
    t = repo.get_timer(timer_id)
    if t is None or t.status != "active":
        log.info("end_check_skipped_inactive", extra={"timer_id": timer_id})
        return
    settings = get_settings()
    now = datetime.now(settings.tz)
    body = f"Time's up on {t.task}. Done, or rolling it? (done / more Nmin / cancel)"
    sms.send_sms(body)
    repo.insert_message(
        ts=now.isoformat(),
        direction="out",
        type_="timer_check",
        raw_text=body,
        related_timer_id=timer_id,
    )
