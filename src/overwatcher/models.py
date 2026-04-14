from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    ts: str = Field(index=True)  # ISO 8601 with offset
    direction: str  # 'in' | 'out'
    type: str = Field(index=True)
    mode: Optional[str] = None
    raw_text: Optional[str] = None
    parsed_json: Optional[str] = None
    twilio_sid: Optional[str] = Field(default=None, unique=True, index=True)
    related_timer_id: Optional[int] = Field(default=None, foreign_key="timers.id")
    request_id: Optional[str] = None


class Timer(SQLModel, table=True):
    __tablename__ = "timers"

    id: Optional[int] = Field(default=None, primary_key=True)
    task: str
    duration_min: int
    start_ts: str
    end_ts_scheduled: str
    mid_check_ts: Optional[str] = None
    status: str = Field(index=True)  # active|paused|completed|cancelled
    cancelled_at: Optional[str] = None
    notes: Optional[str] = None


class DayState(SQLModel, table=True):
    __tablename__ = "day_state"

    date: str = Field(primary_key=True)  # YYYY-MM-DD in user TZ
    mode: str = Field(default="bookend")
    morning_intent_json: Optional[str] = None
    morning_msg_id: Optional[int] = Field(default=None, foreign_key="messages.id")
    evening_msg_id: Optional[int] = Field(default=None, foreign_key="messages.id")
    last_inbound_ts: Optional[str] = None
