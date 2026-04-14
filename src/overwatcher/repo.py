"""Thin DB access layer. Kept separate from models so handlers/tests don't juggle sessions directly."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import Session, col, select

from overwatcher import db
from overwatcher.models import DayState, Message, Timer


def insert_message(
    *,
    ts: str,
    direction: str,
    type_: str,
    raw_text: Optional[str] = None,
    parsed_json: Optional[str] = None,
    mode: Optional[str] = None,
    twilio_sid: Optional[str] = None,
    related_timer_id: Optional[int] = None,
    request_id: Optional[str] = None,
) -> Message:
    with db.session_scope() as s:
        m = Message(
            ts=ts,
            direction=direction,
            type=type_,
            raw_text=raw_text,
            parsed_json=parsed_json,
            mode=mode,
            twilio_sid=twilio_sid,
            related_timer_id=related_timer_id,
            request_id=request_id,
        )
        s.add(m)
        s.flush()
        s.refresh(m)
        return m


def has_message_type_on(date_str: str, type_: str, direction: str = "in") -> bool:
    with Session(db.get_engine()) as s:
        stmt = select(Message).where(
            col(Message.type) == type_,
            col(Message.direction) == direction,
            col(Message.ts).startswith(date_str),
        )
        return s.exec(stmt).first() is not None


def get_or_create_day_state(date_str: str) -> DayState:
    with db.session_scope() as s:
        row = s.get(DayState, date_str)
        if row is None:
            row = DayState(date=date_str)
            s.add(row)
            s.flush()
            s.refresh(row)
        return row


def update_day_state(date_str: str, **fields) -> None:
    with db.session_scope() as s:
        row = s.get(DayState, date_str)
        if row is None:
            row = DayState(date=date_str)
            s.add(row)
        for k, v in fields.items():
            setattr(row, k, v)


def get_timer(timer_id: int) -> Optional[Timer]:
    with Session(db.get_engine()) as s:
        return s.get(Timer, timer_id)


def active_timers() -> list[Timer]:
    with Session(db.get_engine()) as s:
        return list(s.exec(select(Timer).where(Timer.status == "active")))


def create_timer(
    *,
    task: str,
    duration_min: int,
    start_ts: str,
    end_ts_scheduled: str,
    mid_check_ts: Optional[str] = None,
) -> Timer:
    with db.session_scope() as s:
        t = Timer(
            task=task,
            duration_min=duration_min,
            start_ts=start_ts,
            end_ts_scheduled=end_ts_scheduled,
            mid_check_ts=mid_check_ts,
            status="active",
        )
        s.add(t)
        s.flush()
        s.refresh(t)
        return t


def set_timer_status(timer_id: int, status: str, *, cancelled_at: Optional[str] = None) -> None:
    with db.session_scope() as s:
        t = s.get(Timer, timer_id)
        if t is None:
            return
        t.status = status
        if cancelled_at:
            t.cancelled_at = cancelled_at


def last_progress_within(minutes: int, *, now: datetime) -> Optional[Message]:
    cutoff = (now - timedelta(minutes=minutes)).isoformat()
    with Session(db.get_engine()) as s:
        stmt = (
            select(Message)
            .where(Message.type == "progress", Message.direction == "in", Message.ts >= cutoff)
            .order_by(col(Message.ts).desc())
        )
        return s.exec(stmt).first()


def outbound_count_on(date_str: str) -> int:
    with Session(db.get_engine()) as s:
        rows = s.exec(
            select(Message).where(
                Message.direction == "out",
                col(Message.ts).startswith(date_str),
            )
        )
        return sum(1 for _ in rows)


def messages_in_window(start_ts: str, end_ts: str) -> list[Message]:
    with Session(db.get_engine()) as s:
        stmt = (
            select(Message)
            .where(Message.ts >= start_ts, Message.ts <= end_ts)
            .order_by(col(Message.ts).asc())
        )
        return list(s.exec(stmt))
