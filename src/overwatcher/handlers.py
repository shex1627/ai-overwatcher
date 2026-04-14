"""Intent dispatcher + per-intent handlers. The hot-path brain of the product."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from overwatcher import llm_calls, pending, quiet, repo, sms
from overwatcher.config import get_settings
from overwatcher.jobs import timer_check
from overwatcher.scheduler import get_scheduler
from overwatcher.schemas import ClassifierOutput, Command, CommandVerb, Intent
from overwatcher.timers import compute_end_ts, compute_mid_check_ts

log = logging.getLogger(__name__)


def _today_str(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


def _template_warm_ack(intent: Intent) -> str:
    """Deterministic fallback replies. Used when the LLM warm-ack call fails or we're in quiet mode."""
    if intent == Intent.empty:
        return "Got an empty message. You ok?"
    if intent == Intent.morning_reply:
        return "Logged. Go."
    if intent == Intent.evening_reply:
        return "Logged. Rest up."
    return "Got it. Logged."


async def route(
    *,
    body: str,
    classifier_output: ClassifierOutput,
    now: datetime,
    request_id: Optional[str] = None,
) -> Optional[str]:
    """Dispatch a classified inbound message. Returns the reply text to send, or None for silent."""
    # Quiet window — process state changes silently. Commands still take effect (cancel, done, start).
    if quiet.is_quiet(now) and classifier_output.intent != Intent.command:
        log.info("quiet_window_silent", extra={"request_id": request_id})
        return None

    intent = classifier_output.intent

    if intent == Intent.empty:
        return _template_warm_ack(intent)

    if intent == Intent.command:
        return await _handle_command(
            classifier_output.command, body=body, now=now, request_id=request_id
        )

    if intent == Intent.mode_override and classifier_output.mode_override:
        repo.update_day_state(_today_str(now), mode=classifier_output.mode_override)
        return f"Mode set: {classifier_output.mode_override}."

    if intent == Intent.morning_reply:
        repo.update_day_state(
            _today_str(now),
            morning_intent_json=json.dumps(
                [i.model_dump() for i in classifier_output.if_then_items]
            )
            if classifier_output.if_then_items
            else None,
        )
        # Offer to start implicit timer if detected — remember the offer so a "yes" can confirm.
        if classifier_output.implicit_timer and classifier_output.implicit_duration_min:
            task = classifier_output.implicit_task or "that"
            pending.offer_timer(task=task, duration_min=classifier_output.implicit_duration_min, now=now)
            return (
                f"Sharp plan. Want me to check back in {classifier_output.implicit_duration_min} min "
                f"on {task}? (yes / no)"
            )
        # Pushback via LLM if it's worth pushing back on. Model decides.
        pushback = llm_calls.llm_morning_pushback(
            body=body,
            if_then_items=[i.model_dump() for i in classifier_output.if_then_items],
            now=now,
            request_id=request_id,
        )
        return pushback or _template_warm_ack(intent)

    if intent == Intent.evening_reply:
        morning_intent = _current_morning_intent(now)
        followup = llm_calls.llm_evening_followup(
            body=body, morning_intent=morning_intent, now=now, request_id=request_id
        )
        return followup or _template_warm_ack(intent)

    # progress / question / emotional / ambiguous — warm ack via LLM with template fallback.
    return _warm_ack(body=body, intent=intent, now=now, request_id=request_id)


def _current_morning_intent(now: datetime) -> Optional[str]:
    state = repo.get_or_create_day_state(_today_str(now))
    return state.morning_intent_json


def _warm_ack(*, body: str, intent: Intent, now: datetime, request_id: Optional[str]) -> str:
    active = [
        {"task": t.task, "duration_min": t.duration_min} for t in repo.active_timers()
    ]
    reply = llm_calls.llm_warm_ack(
        body=body,
        intent=intent,
        active_timers=active,
        morning_intent=_current_morning_intent(now),
        now=now,
        request_id=request_id,
    )
    return reply or _template_warm_ack(intent)


async def _handle_command(
    command: Optional[Command], *, body: str, now: datetime, request_id: Optional[str]
) -> Optional[str]:
    if command is None:
        return "Got a command but couldn't parse it. Try: start design 30min / stuck / done / cancel / quiet."

    if command.verb == CommandVerb.start:
        return await _handle_start(command, now=now, request_id=request_id)
    if command.verb == CommandVerb.stuck:
        return await _handle_stuck(now=now, request_id=request_id)
    if command.verb == CommandVerb.done:
        return await _handle_done(now=now, request_id=request_id)
    if command.verb == CommandVerb.cancel:
        return await _handle_cancel(command, now=now, request_id=request_id)
    if command.verb == CommandVerb.quiet:
        return _handle_quiet(command, now=now)
    if command.verb == CommandVerb.yes:
        offer = pending.take_offer(now)
        if offer is None:
            return "Noted."
        start_cmd = Command(
            verb=CommandVerb.start, task=offer.task, duration_min=offer.duration_min
        )
        return await _handle_start(start_cmd, now=now, request_id=request_id)
    if command.verb == CommandVerb.no:
        pending.clear()
        return "Skipping. No timer set."
    return None


async def _handle_start(cmd: Command, *, now: datetime, request_id: Optional[str]) -> str:
    if not cmd.task or not cmd.duration_min:
        return "Need a task and a duration. Try: start design 30min"

    start_iso = now.isoformat()
    end_dt = compute_end_ts(now, cmd.duration_min)
    mid_dt = compute_mid_check_ts(now, cmd.duration_min)

    t = repo.create_timer(
        task=cmd.task,
        duration_min=cmd.duration_min,
        start_ts=start_iso,
        end_ts_scheduled=end_dt.isoformat(),
        mid_check_ts=mid_dt.isoformat() if mid_dt else None,
    )

    sch = get_scheduler()
    sch.add_job(
        timer_check.end_check,
        trigger="date",
        run_date=end_dt,
        args=[t.id],
        id=f"timer_end_{t.id}",
        replace_existing=True,
    )
    if mid_dt:
        sch.add_job(
            timer_check.mid_check,
            trigger="date",
            run_date=mid_dt,
            args=[t.id],
            id=f"timer_mid_{t.id}",
            replace_existing=True,
        )

    log.info(
        "timer_started",
        extra={
            "request_id": request_id,
            "timer_id": t.id,
            "task": t.task,
            "duration_min": t.duration_min,
        },
    )
    return f"Timer set. {cmd.duration_min} min on {cmd.task}. Go."


async def _handle_stuck(*, now: datetime, request_id: Optional[str]) -> str:
    active = repo.active_timers()
    sch = get_scheduler()
    for t in active:
        repo.set_timer_status(t.id, "paused")
        for job_id in (f"timer_end_{t.id}", f"timer_mid_{t.id}"):
            try:
                sch.remove_job(job_id)
            except Exception as exc:  # noqa: BLE001 — APScheduler's JobLookupError; isolating here is fine
                log.debug("scheduler_remove_skip", extra={"job_id": job_id, "err": type(exc).__name__})
    log.info("stuck_paused_timers", extra={"count": len(active), "request_id": request_id})
    return (
        "Paused. What were you feeling right before you got stuck — bored, anxious, "
        "unsure where to start?"
    )


async def _handle_done(*, now: datetime, request_id: Optional[str]) -> str:
    active = repo.active_timers()
    sch = get_scheduler()
    for t in active:
        repo.set_timer_status(t.id, "completed")
        for job_id in (f"timer_end_{t.id}", f"timer_mid_{t.id}"):
            try:
                sch.remove_job(job_id)
            except Exception as exc:  # noqa: BLE001
                log.debug("scheduler_remove_skip", extra={"job_id": job_id, "err": type(exc).__name__})
    log.info("done_completed_timers", extra={"count": len(active), "request_id": request_id})
    return "Logged done."


async def _handle_cancel(cmd: Command, *, now: datetime, request_id: Optional[str]) -> str:
    active = repo.active_timers()
    target = cmd.task
    cancelled: list[int] = []
    sch = get_scheduler()
    for t in active:
        if target and target.lower() not in t.task.lower():
            continue
        repo.set_timer_status(t.id, "cancelled", cancelled_at=now.isoformat())
        for job_id in (f"timer_end_{t.id}", f"timer_mid_{t.id}"):
            try:
                sch.remove_job(job_id)
            except Exception as exc:  # noqa: BLE001
                log.debug("scheduler_remove_skip", extra={"job_id": job_id, "err": type(exc).__name__})
        cancelled.append(t.id)
    log.info("cancel_done", extra={"cancelled_ids": cancelled, "request_id": request_id})
    if not cancelled:
        return "No active timer to cancel."
    return f"Cancelled {len(cancelled)} timer(s)."


def _handle_quiet(cmd: Command, *, now: datetime) -> str:
    hours = 3
    if cmd.duration_min and cmd.duration_min >= 60:
        hours = max(1, cmd.duration_min // 60)
    until = quiet.start_quiet_window(hours=hours, now=now)
    return f"Quiet until {until.strftime('%H:%M')}. I'll keep logging but won't text."
