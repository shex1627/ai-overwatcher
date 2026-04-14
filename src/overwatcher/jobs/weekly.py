"""Friday 5pm summary. Reads last 7 days of messages, asks the quality-tier LLM to write it."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from overwatcher import llm_calls, repo, sms
from overwatcher.config import get_settings

log = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    now = datetime.now(settings.tz)
    start_dt = now - timedelta(days=7)
    start_iso = start_dt.isoformat()
    end_iso = now.isoformat()

    msgs = repo.messages_in_window(start_iso, end_iso)
    inbound = sum(1 for m in msgs if m.direction == "in")

    if inbound == 0:
        body = "Quiet week. No logs to summarize. Nothing to fix — sometimes weeks are like that."
    else:
        msg_dicts = [
            {
                "ts": m.ts,
                "direction": m.direction,
                "type": m.type,
                "raw_text": m.raw_text,
            }
            for m in msgs
        ]
        summary = llm_calls.llm_weekly_summary(
            messages=msg_dicts, start_ts=start_iso, end_ts=end_iso
        )
        if summary:
            body = summary
        else:
            body = (
                f"Weekly check-in: {inbound} messages this week. "
                "Summary model was unreachable — full review will run next Friday."
            )

    sms.send_sms(body)
    repo.insert_message(ts=now.isoformat(), direction="out", type_="weekly", raw_text=body)
    log.info("weekly_sent", extra={"inbound": inbound, "llm_used": inbound > 0})
