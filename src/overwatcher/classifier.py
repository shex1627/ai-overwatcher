"""Classifier: LLM primary, heuristic fallback.

The heuristic is deterministic — no LLM. It's the guaranteed last resort when all providers fail
or the LLM output won't parse. Not as accurate as the model but ensures the system keeps working.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from overwatcher import timers
from overwatcher.schemas import (
    ClassifierOutput,
    Command,
    CommandVerb,
    Intent,
)

log = logging.getLogger(__name__)

_COMMAND_WORDS = {
    "start": CommandVerb.start,
    "stuck": CommandVerb.stuck,
    "done": CommandVerb.done,
    "finished": CommandVerb.done,
    "quiet": CommandVerb.quiet,
    "cancel": CommandVerb.cancel,
    "yes": CommandVerb.yes,
    "y": CommandVerb.yes,
    "no": CommandVerb.no,
    "n": CommandVerb.no,
}

_MODE_WORDS = {"bookend", "blocks", "heartbeat"}


def heuristic_classify(
    body: str,
    *,
    now: datetime,
    has_morning_reply_today: bool,
    has_evening_reply_today: bool,
    tz: ZoneInfo | None = None,
) -> ClassifierOutput:
    """Cheap rule-based classifier. Runs when the LLM fails or as a correctness check."""
    text = (body or "").strip()
    if not text:
        return ClassifierOutput(intent=Intent.empty, confidence=1.0)

    lower = text.lower()
    first_word = re.split(r"[\s,.;:!?]", lower, maxsplit=1)[0]

    # Mode override: first token is a mode word.
    if first_word in _MODE_WORDS:
        return ClassifierOutput(
            intent=Intent.mode_override,
            mode_override=first_word,  # type: ignore[arg-type]
            confidence=0.95,
        )

    # Command detection: first token is a command word.
    if first_word in _COMMAND_WORDS:
        verb = _COMMAND_WORDS[first_word]
        cmd = Command(verb=verb)
        if verb == CommandVerb.start:
            remainder = text[len(first_word):].strip()
            duration = timers.parse_duration_minutes(remainder) or timers.parse_until(
                remainder, now
            )
            task = timers.extract_task(remainder)
            cmd.task = task
            cmd.duration_min = duration
        elif verb == CommandVerb.cancel:
            remainder = text[len(first_word):].strip()
            cmd.task = remainder or None
        elif verb == CommandVerb.quiet:
            remainder = text[len(first_word):].strip()
            cmd.duration_min = timers.parse_duration_minutes(remainder)
        return ClassifierOutput(intent=Intent.command, command=cmd, confidence=0.9)

    # Implicit timer detection in free-form text (e.g. "30 min on the design doc").
    implicit_duration = timers.parse_duration_minutes(text)
    if implicit_duration:
        task = timers.extract_task(text) or ""
        # Strip "on" and duration fragments already removed inside extract_task.
        if task and not task.isspace():
            return ClassifierOutput(
                intent=Intent.progress,
                implicit_timer=True,
                implicit_task=task,
                implicit_duration_min=implicit_duration,
                confidence=0.6,
            )

    # Time-window default: if no morning reply yet and it's morning, treat as morning_reply.
    hour = now.hour
    if 7 <= hour < 12 and not has_morning_reply_today:
        return ClassifierOutput(intent=Intent.morning_reply, confidence=0.55)
    if 19 <= hour < 23 and not has_evening_reply_today:
        return ClassifierOutput(intent=Intent.evening_reply, confidence=0.55)

    # Fallthrough: progress note.
    return ClassifierOutput(intent=Intent.progress, confidence=0.5)


async def classify(
    body: str,
    *,
    now: datetime,
    has_morning_reply_today: bool,
    has_evening_reply_today: bool,
    recent_messages: Optional[list[dict]] = None,
    request_id: Optional[str] = None,
) -> ClassifierOutput:
    """Primary classifier entry point.

    LLM-first via `llm_calls.llm_classify` (LiteLLM+Instructor with provider fallback chain).
    On total LLM failure or schema-validation failure, falls back to the deterministic heuristic
    so the system always produces a result.
    """
    # Short-circuit: empty message doesn't need an LLM.
    if not (body or "").strip():
        return ClassifierOutput(intent=Intent.empty, confidence=1.0)

    # Import here to avoid a circular import (llm_calls → prompts_loader is fine;
    # classifier is imported by handlers, and llm_calls imports nothing from here).
    from overwatcher import llm_calls

    llm_result = llm_calls.llm_classify(
        body=body,
        now=now,
        has_morning_reply_today=has_morning_reply_today,
        has_evening_reply_today=has_evening_reply_today,
        recent_messages=recent_messages or [],
        request_id=request_id,
    )
    if llm_result is not None:
        log.info(
            "classifier_result",
            extra={
                "request_id": request_id,
                "intent": llm_result.intent.value,
                "confidence": llm_result.confidence,
                "classifier_mode": "llm",
            },
        )
        return llm_result

    # Fallback: deterministic heuristic. Keeps the system working when every LLM provider is down.
    result = heuristic_classify(
        body,
        now=now,
        has_morning_reply_today=has_morning_reply_today,
        has_evening_reply_today=has_evening_reply_today,
    )
    log.warning(
        "classifier_result_heuristic_fallback",
        extra={
            "request_id": request_id,
            "intent": result.intent.value,
            "confidence": result.confidence,
            "classifier_mode": "heuristic",
        },
    )
    return result
