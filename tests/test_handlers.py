from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from overwatcher import db, quiet, repo
from overwatcher.handlers import route
from overwatcher.schemas import ClassifierOutput, Command, CommandVerb, Intent

TZ = ZoneInfo("America/Los_Angeles")


@pytest.fixture(autouse=True)
def _fresh_db():
    db.init_db()
    quiet.end_quiet_window()
    yield
    quiet.end_quiet_window()


def _now():
    return datetime(2026, 4, 13, 14, 0, tzinfo=TZ)


async def test_empty_intent_returns_template():
    out = await route(
        body="",
        classifier_output=ClassifierOutput(intent=Intent.empty),
        now=_now(),
    )
    assert out == "Got an empty message. You ok?"


async def test_start_command_creates_timer_and_jobs():
    co = ClassifierOutput(
        intent=Intent.command,
        command=Command(verb=CommandVerb.start, task="design", duration_min=30),
    )
    # Don't actually register APScheduler jobs against a running scheduler.
    with patch("overwatcher.handlers.get_scheduler") as mock_sch:
        instance = mock_sch.return_value
        instance.add_job.return_value = None
        out = await route(body="start design 30min", classifier_output=co, now=_now())
    assert out is not None
    assert "design" in out
    active = repo.active_timers()
    assert len(active) == 1
    assert active[0].task == "design"
    assert active[0].duration_min == 30


async def test_quiet_command_sets_window_and_silences_progress():
    co = ClassifierOutput(intent=Intent.command, command=Command(verb=CommandVerb.quiet))
    out = await route(body="quiet", classifier_output=co, now=_now())
    assert out is not None and "Quiet" in out

    # A subsequent progress message during the quiet window returns None (silent).
    progress = ClassifierOutput(intent=Intent.progress)
    silent = await route(body="still working", classifier_output=progress, now=_now())
    assert silent is None


async def test_cancel_with_no_active_timer():
    co = ClassifierOutput(
        intent=Intent.command, command=Command(verb=CommandVerb.cancel, task="design")
    )
    with patch("overwatcher.handlers.get_scheduler"):
        out = await route(body="cancel design", classifier_output=co, now=_now())
    assert out == "No active timer to cancel."


async def test_mode_override_persists_to_day_state():
    co = ClassifierOutput(intent=Intent.mode_override, mode_override="blocks")
    out = await route(body="blocks today", classifier_output=co, now=_now())
    assert out == "Mode set: blocks."
    state = repo.get_or_create_day_state(_now().strftime("%Y-%m-%d"))
    assert state.mode == "blocks"


async def test_command_works_even_in_quiet_window():
    """Commands (cancel/done/start) must still take effect even during a quiet window."""
    quiet.start_quiet_window(hours=1, now=_now())
    co = ClassifierOutput(intent=Intent.command, command=Command(verb=CommandVerb.done))
    with patch("overwatcher.handlers.get_scheduler"):
        out = await route(body="done", classifier_output=co, now=_now())
    assert out == "Logged done."
