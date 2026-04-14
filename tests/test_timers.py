from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from overwatcher.timers import (
    compute_end_ts,
    compute_mid_check_ts,
    extract_task,
    parse_duration_minutes,
    parse_until,
)

TZ = ZoneInfo("America/Los_Angeles")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("start design 30min", 30),
        ("30 min on the stew", 30),
        ("for 1 hour on refactor", 60),
        ("2 hrs of writing", 120),
        ("15m", 15),
        ("a bit on X", None),
        ("", None),
    ],
)
def test_parse_duration(text, expected):
    assert parse_duration_minutes(text) == expected


def test_parse_until_future_same_day():
    now = datetime(2026, 4, 13, 13, 0, tzinfo=TZ)
    assert parse_until("until 3pm", now) == 120


def test_parse_until_next_day_when_past():
    now = datetime(2026, 4, 13, 16, 0, tzinfo=TZ)
    # 3pm has passed today → rolls to tomorrow 3pm → 23h
    assert parse_until("until 3pm", now) == 23 * 60


def test_parse_until_returns_none_when_absent():
    now = datetime(2026, 4, 13, 13, 0, tzinfo=TZ)
    assert parse_until("do the design", now) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("start design 30min", "design"),
        ("start the stew for 45 min", "the stew"),
        ("begin refactor 2hr", "refactor"),
    ],
)
def test_extract_task(text, expected):
    assert extract_task(text) == expected


def test_compute_mid_check_none_under_45():
    start = datetime(2026, 4, 13, 10, 0, tzinfo=TZ)
    assert compute_mid_check_ts(start, 30) is None
    assert compute_mid_check_ts(start, 45) is None


def test_compute_mid_check_none_between_45_and_90():
    start = datetime(2026, 4, 13, 10, 0, tzinfo=TZ)
    assert compute_mid_check_ts(start, 60) is None
    assert compute_mid_check_ts(start, 90) is None


def test_compute_mid_check_halfway_over_90():
    start = datetime(2026, 4, 13, 10, 0, tzinfo=TZ)
    assert compute_mid_check_ts(start, 120) == start + timedelta(minutes=60)


def test_compute_mid_check_respects_heartbeat_mode():
    start = datetime(2026, 4, 13, 10, 0, tzinfo=TZ)
    assert compute_mid_check_ts(start, 30, mode="heartbeat") == start + timedelta(minutes=15)


def test_compute_mid_check_respects_opt_in():
    start = datetime(2026, 4, 13, 10, 0, tzinfo=TZ)
    assert compute_mid_check_ts(start, 60, user_opted_in=True) == start + timedelta(minutes=30)


def test_compute_end_ts_has_grace():
    start = datetime(2026, 4, 13, 10, 0, tzinfo=TZ)
    assert compute_end_ts(start, 30) == start + timedelta(minutes=30, seconds=120)
