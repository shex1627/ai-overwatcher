import os
import tempfile

import pytest

# Point DB at a per-test temp file so nothing touches the real state.db.
# This must happen before any overwatcher imports.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")
# Blank out secrets so get_settings() doesn't pick up the user's real .env during tests.
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "")  # empty -> sms.validate_signature short-circuits true
os.environ.setdefault("TWILIO_FROM_NUMBER", "+15550000000")
os.environ.setdefault("USER_PHONE", "+15551111111")
os.environ.setdefault("GOOGLE_SHEETS_ID", "")
os.environ.setdefault("PUBLIC_WEBHOOK_BASE_URL", "http://test")


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    from overwatcher.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _fresh_tables():
    """Drop & recreate all tables per test so one test's rows don't leak into the next."""
    from sqlmodel import SQLModel

    from overwatcher.db import get_engine

    engine = get_engine()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _mock_llm_calls(monkeypatch):
    """Default: stub every LLM call so tests don't hit real APIs.

    Individual tests that want to verify LLM-path behavior override these with their own patches.
    """
    from overwatcher import llm_calls

    # Default classifier stub returns None → handlers fall through to the heuristic.
    monkeypatch.setattr(llm_calls, "llm_classify", lambda **_: None)
    monkeypatch.setattr(llm_calls, "llm_warm_ack", lambda **_: None)
    monkeypatch.setattr(llm_calls, "llm_morning_pushback", lambda **_: None)
    monkeypatch.setattr(llm_calls, "llm_evening_followup", lambda **_: None)
    monkeypatch.setattr(llm_calls, "llm_weekly_summary", lambda **_: None)
    yield
