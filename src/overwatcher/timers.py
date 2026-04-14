"""Timer parsing and scheduling helpers. Pure functions — no IO."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

_DURATION_RE = re.compile(
    r"""
    (?:
        (?P<num>\d+)\s*
        (?P<unit>min(?:ute)?s?|m|hr?s?|hour(?:s)?|h)\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_UNTIL_RE = re.compile(r"\buntil\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE)
_FOR_RE = re.compile(r"\bfor\s+(\d+)\s*(min|minutes|hr|hrs|hour|hours|h|m)\b", re.IGNORECASE)


def parse_duration_minutes(text: str) -> Optional[int]:
    """Pull a duration in minutes out of free text. Returns None if not found."""
    m = _FOR_RE.search(text) or _DURATION_RE.search(text)
    if not m:
        return None
    try:
        n = int(m.group("num") if "num" in m.groupdict() and m.group("num") else m.group(1))
    except (IndexError, TypeError, ValueError):
        return None
    unit = (m.group("unit") if "unit" in m.groupdict() and m.group("unit") else m.group(2)).lower()
    if unit.startswith(("h",)):
        return n * 60
    return n


def parse_until(text: str, now: datetime) -> Optional[int]:
    """Parse 'until 3pm' into duration minutes from `now`. Returns None if parse fails or result is ≤0."""
    m = _UNTIL_RE.search(text)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    delta = int((target - now).total_seconds() // 60)
    return delta if delta > 0 else None


def extract_task(text: str) -> Optional[str]:
    """Extract the task name from a 'start X 30min' style command. Heuristic, good enough for the hot path."""
    # Strip command verb
    cleaned = re.sub(r"^\s*(start|begin|timer)\s+", "", text.strip(), flags=re.IGNORECASE)
    # Strip 'on' connector
    cleaned = re.sub(r"\s+on\s+", " ", cleaned, flags=re.IGNORECASE)
    # Strip duration phrases
    cleaned = _FOR_RE.sub("", cleaned)
    cleaned = _DURATION_RE.sub("", cleaned)
    cleaned = _UNTIL_RE.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .,:;-")
    return cleaned or None


def compute_mid_check_ts(
    start: datetime,
    duration_min: int,
    *,
    mode: Optional[str] = None,
    user_opted_in: bool = False,
) -> Optional[datetime]:
    """Decision logic for mid-check scheduling — see §6.2 of technical-implementation.md.

    - heartbeat mode OR explicit opt-in: always mid-check at the halfway point
    - duration > 90 min: mid-check at halfway
    - 45 < duration <= 90: no auto mid-check (caller may ask the user and opt in)
    - duration <= 45: never
    """
    if mode == "heartbeat" or user_opted_in:
        return start + timedelta(minutes=duration_min // 2)
    if duration_min > 90:
        return start + timedelta(minutes=duration_min // 2)
    return None


def compute_end_ts(start: datetime, duration_min: int, *, grace_seconds: int = 120) -> datetime:
    return start + timedelta(minutes=duration_min, seconds=grace_seconds)
