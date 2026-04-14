"""Phase 4 tests: LLM-path behavior, fallback paths, pending-timer confirmation, prompt loader."""
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from overwatcher import db, pending, prompts_loader, quiet
from overwatcher.handlers import route
from overwatcher.schemas import (
    ClassifierOutput,
    Command,
    CommandVerb,
    IfThenItem,
    Intent,
)

TZ = ZoneInfo("America/Los_Angeles")


def _now():
    return datetime(2026, 4, 13, 14, 0, tzinfo=TZ)


@pytest.fixture(autouse=True)
def _fresh_state():
    db.init_db()
    quiet.end_quiet_window()
    pending.clear()
    yield
    pending.clear()
    quiet.end_quiet_window()


# ---- Prompt loader ---------------------------------------------------------


def test_prompt_loader_parses_version_and_tier():
    p = prompts_loader.load("classifier")
    assert p.version >= 1
    assert p.tier in {"fast", "quality"}
    assert "<user_input>" in p.body


def test_prompt_loader_renders_variables():
    p = prompts_loader.load("warm_ack")
    rendered = p.render(intent="progress", active_timers="none", morning_intent="write section 2", body="working on it")
    assert "progress" in rendered
    assert "write section 2" in rendered
    assert "working on it" in rendered


def test_prompt_loader_missing_var_raises():
    p = prompts_loader.load("warm_ack")
    with pytest.raises(KeyError):
        p.render(intent="progress")  # missing other required vars


# ---- Classifier LLM-first with heuristic fallback --------------------------


async def test_classifier_uses_llm_when_available():
    from overwatcher import classifier, llm_calls

    llm_out = ClassifierOutput(
        intent=Intent.command,
        command=Command(verb=CommandVerb.start, task="x", duration_min=30),
        confidence=0.95,
    )
    with patch.object(llm_calls, "llm_classify", return_value=llm_out):
        result = await classifier.classify(
            "start x 30min",
            now=_now(),
            has_morning_reply_today=False,
            has_evening_reply_today=False,
            request_id="req1",
        )
    assert result.intent == Intent.command
    assert result.command and result.command.task == "x"


async def test_classifier_falls_back_to_heuristic_when_llm_returns_none():
    from overwatcher import classifier, llm_calls

    with patch.object(llm_calls, "llm_classify", return_value=None):
        result = await classifier.classify(
            "start design 30min",
            now=_now(),
            has_morning_reply_today=False,
            has_evening_reply_today=False,
        )
    # Heuristic handles `start` commands correctly.
    assert result.intent == Intent.command
    assert result.command and result.command.verb == CommandVerb.start


async def test_classifier_short_circuits_empty_without_llm():
    """Empty body must not trigger an LLM call."""
    from overwatcher import classifier, llm_calls

    with patch.object(llm_calls, "llm_classify") as mock_llm:
        result = await classifier.classify(
            "",
            now=_now(),
            has_morning_reply_today=False,
            has_evening_reply_today=False,
        )
        mock_llm.assert_not_called()
    assert result.intent == Intent.empty


# ---- Warm-ack LLM with template fallback -----------------------------------


async def test_warm_ack_uses_llm_reply():
    from overwatcher import llm_calls

    with patch.object(llm_calls, "llm_warm_ack", return_value="Good plan — stick with it."):
        out = await route(
            body="still on section 2",
            classifier_output=ClassifierOutput(intent=Intent.progress),
            now=_now(),
        )
    assert out == "Good plan — stick with it."


async def test_warm_ack_falls_back_to_template_on_llm_none():
    from overwatcher import llm_calls

    with patch.object(llm_calls, "llm_warm_ack", return_value=None):
        out = await route(
            body="progress note",
            classifier_output=ClassifierOutput(intent=Intent.progress),
            now=_now(),
        )
    # Template fallback is deterministic.
    assert out == "Got it. Logged."


# ---- Pending implicit-timer confirmation -----------------------------------


async def test_morning_reply_with_implicit_timer_offers_and_yes_starts():
    co = ClassifierOutput(
        intent=Intent.morning_reply,
        if_then_items=[IfThenItem(trigger="10am", action="design 30min")],
        implicit_timer=True,
        implicit_task="design",
        implicit_duration_min=30,
    )
    # First: morning reply -> offer is stored; reply asks "check back in 30 min on design?"
    out = await route(body="10am design 30min", classifier_output=co, now=_now())
    assert out is not None and "30" in out and "design" in out

    # Then user replies "yes" -> that completes the start
    yes_co = ClassifierOutput(intent=Intent.command, command=Command(verb=CommandVerb.yes))
    with patch("overwatcher.handlers.get_scheduler"):
        started = await route(body="yes", classifier_output=yes_co, now=_now())
    assert started is not None and "design" in started.lower()


async def test_yes_with_no_pending_offer_returns_noted():
    yes_co = ClassifierOutput(intent=Intent.command, command=Command(verb=CommandVerb.yes))
    out = await route(body="yes", classifier_output=yes_co, now=_now())
    assert out == "Noted."


async def test_no_clears_pending_offer():
    pending.offer_timer(task="design", duration_min=30, now=_now())
    no_co = ClassifierOutput(intent=Intent.command, command=Command(verb=CommandVerb.no))
    out = await route(body="no", classifier_output=no_co, now=_now())
    assert out == "Skipping. No timer set."
    assert pending.take_offer(_now()) is None


async def test_pending_offer_expires():
    from datetime import timedelta

    pending.offer_timer(task="design", duration_min=30, now=_now())
    # Jump 15 min into the future (expiry is 10 min)
    later = _now() + timedelta(minutes=15)
    yes_co = ClassifierOutput(intent=Intent.command, command=Command(verb=CommandVerb.yes))
    out = await route(body="yes", classifier_output=yes_co, now=later)
    assert out == "Noted."  # expired, no start


# ---- Morning pushback path -------------------------------------------------


async def test_morning_pushback_used_when_llm_returns_text():
    from overwatcher import llm_calls

    co = ClassifierOutput(intent=Intent.morning_reply, if_then_items=[])
    with patch.object(llm_calls, "llm_morning_pushback", return_value="What's the first 15 minutes?"):
        out = await route(body="work on the paper today", classifier_output=co, now=_now())
    assert out == "What's the first 15 minutes?"


async def test_morning_without_implicit_timer_uses_pushback_llm_then_template():
    from overwatcher import llm_calls

    co = ClassifierOutput(intent=Intent.morning_reply, if_then_items=[])
    with patch.object(llm_calls, "llm_morning_pushback", return_value=None):
        out = await route(body="work on the paper today", classifier_output=co, now=_now())
    assert out == "Logged. Go."
