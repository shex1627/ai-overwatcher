"""9pm prompt. Reads today's morning intent if any and interpolates it."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from overwatcher import repo, sms
from overwatcher.config import get_settings

log = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    now = datetime.now(settings.tz)
    date_str = now.strftime("%Y-%m-%d")
    state = repo.get_or_create_day_state(date_str)
    if state.morning_intent_json:
        try:
            items = json.loads(state.morning_intent_json)
            summary = "; ".join(
                f"{i.get('trigger', '?')} → {i.get('action', '?')}" for i in items[:3]
            )
            body = f"Evening check-in. Today's plan was: {summary}. How did it actually go?"
        except json.JSONDecodeError:
            body = "Evening check-in. How did today actually go?"
    else:
        body = "Evening check-in. How did today actually go?"
    sms.send_sms(body)
    m = repo.insert_message(
        ts=now.isoformat(), direction="out", type_="evening", raw_text=body
    )
    repo.update_day_state(date_str, evening_msg_id=m.id)
    log.info("evening_prompt_sent", extra={"date": date_str})
