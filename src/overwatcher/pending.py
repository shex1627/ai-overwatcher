"""Short-lived in-memory state for yes/no follow-ups (implicit-timer confirmations).

Lives in-process only — deliberately. A pending offer that survives restart is stale by definition:
if we restart, it's been > seconds, and the user's reply is for whatever we offered them now, not
whatever we offered before the crash. Keep it simple.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class PendingTimer:
    task: str
    duration_min: int
    offered_at: datetime


_pending: Optional[PendingTimer] = None
_EXPIRY_MINUTES = 10


def offer_timer(task: str, duration_min: int, now: datetime) -> None:
    global _pending
    _pending = PendingTimer(task=task, duration_min=duration_min, offered_at=now)


def take_offer(now: datetime) -> Optional[PendingTimer]:
    """Return the pending offer if still fresh, and clear it. Otherwise return None."""
    global _pending
    if _pending is None:
        return None
    if now - _pending.offered_at > timedelta(minutes=_EXPIRY_MINUTES):
        _pending = None
        return None
    offer = _pending
    _pending = None
    return offer


def clear() -> None:
    global _pending
    _pending = None
