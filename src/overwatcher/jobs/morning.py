"""9am prompt. Sends SMS, records morning message, upserts day_state."""
from __future__ import annotations

import logging
from datetime import datetime

from overwatcher import repo, sms
from overwatcher.config import get_settings

log = logging.getLogger(__name__)

MORNING_PROMPT = (
    "Good morning. What are your top 1-3 items for today? "
    "Try if-then format — e.g. 'if it's 10am, then I open the design doc and do 30 min on section 2.'"
)


async def run() -> None:
    settings = get_settings()
    now = datetime.now(settings.tz)
    date_str = now.strftime("%Y-%m-%d")
    sms.send_sms(MORNING_PROMPT)
    m = repo.insert_message(
        ts=now.isoformat(),
        direction="out",
        type_="morning",
        raw_text=MORNING_PROMPT,
    )
    repo.update_day_state(date_str, mode="bookend", morning_msg_id=m.id)
    log.info("morning_prompt_sent", extra={"date": date_str})
