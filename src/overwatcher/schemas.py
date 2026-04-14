"""Pydantic schemas for LLM structured output. Provider-agnostic via Instructor."""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Intent(str, Enum):
    morning_reply = "morning_reply"
    evening_reply = "evening_reply"
    command = "command"
    progress = "progress"
    question = "question"
    emotional = "emotional"
    mode_override = "mode_override"
    ambiguous = "ambiguous"
    empty = "empty"


class CommandVerb(str, Enum):
    start = "start"
    stuck = "stuck"
    done = "done"
    quiet = "quiet"
    cancel = "cancel"
    yes = "yes"
    no = "no"


class Command(BaseModel):
    verb: CommandVerb
    task: Optional[str] = Field(default=None, description="Target task if relevant (start/cancel).")
    duration_min: Optional[int] = Field(default=None, description="Duration for timer starts.")


class IfThenItem(BaseModel):
    trigger: str = Field(description="The if-condition (usually a time or cue).")
    action: str = Field(description="The then-action (specific, small).")


class ClassifierOutput(BaseModel):
    intent: Intent
    command: Optional[Command] = None
    if_then_items: list[IfThenItem] = Field(default_factory=list)
    implicit_timer: bool = False
    implicit_task: Optional[str] = None
    implicit_duration_min: Optional[int] = None
    mode_override: Optional[Literal["bookend", "blocks", "heartbeat"]] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
