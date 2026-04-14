"""Daily 'system alive' row. Not sent as SMS — just a row in the DB/Sheets for eyeballing."""
from __future__ import annotations

import logging
from datetime import datetime

from overwatcher import repo, sheets
from overwatcher.config import get_settings

log = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    now = datetime.now(settings.tz)
    date_str = now.strftime("%Y-%m-%d")
    sent = repo.outbound_count_on(date_str)
    body = f"heartbeat: sent_today={sent}"
    repo.insert_message(ts=now.isoformat(), direction="out", type_="heartbeat", raw_text=body)
    try:
        sheets.append_row(
            timestamp=now.isoformat(), direction="out", type_="heartbeat",
            mode=None, raw_text=body, parsed=None, timer_id=None, request_id=None,
        )
    except Exception:  # noqa: BLE001
        log.warning("sheets_append_failed", extra={"job": "heartbeat"})
    log.info("heartbeat", extra={"sent_today": sent})
