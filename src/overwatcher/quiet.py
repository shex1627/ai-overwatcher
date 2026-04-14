"""Quiet window state. In-memory — resets on restart, which is fine: quiet windows are short (hours)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

_quiet_until: Optional[datetime] = None


def set_quiet_until(until: datetime) -> None:
    global _quiet_until
    _quiet_until = until


def start_quiet_window(hours: int = 3, *, now: datetime) -> datetime:
    until = now + timedelta(hours=hours)
    set_quiet_until(until)
    return until


def end_quiet_window() -> None:
    global _quiet_until
    _quiet_until = None


def is_quiet(now: datetime) -> bool:
    if _quiet_until is None:
        return False
    if now >= _quiet_until:
        end_quiet_window()
        return False
    return True


def quiet_until() -> Optional[datetime]:
    return _quiet_until
