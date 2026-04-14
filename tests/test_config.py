from overwatcher.config import get_settings


def test_tz_validates_real_zone():
    s = get_settings()
    assert s.tz.key == s.user_tz


def test_fallback_chain_parses_csv(monkeypatch):
    monkeypatch.setenv("LLM_FAST_FALLBACKS", "openai/gpt-4o-mini, gemini/gemini-1.5-flash")
    get_settings.cache_clear()
    s = get_settings()
    assert s.fast_fallback_chain == ["openai/gpt-4o-mini", "gemini/gemini-1.5-flash"]


def test_required_fields_flagged_when_missing(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    get_settings.cache_clear()
    missing = get_settings().validate_required_for_runtime()
    assert "twilio_account_sid" in missing
    assert any("at least one of" in m for m in missing)
