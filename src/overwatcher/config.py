from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    user_phone: str = ""

    # Timezone (validated as a real zoneinfo key at load)
    user_tz: str = "America/Los_Angeles"

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    minimax_api_key: str = ""

    llm_fast_model: str = "anthropic/claude-haiku-4-5"
    llm_quality_model: str = "anthropic/claude-sonnet-4-5"
    llm_fast_fallbacks: str = ""
    llm_quality_fallbacks: str = ""

    # Sheets
    google_sheets_id: str = ""
    google_service_account_json_path: str = "./service-account.json"

    # Storage
    database_url: str = "sqlite:///./state.db"

    # Web
    public_webhook_base_url: str = "http://127.0.0.1:8000"
    host: str = "127.0.0.1"
    port: int = 8000

    # Misc
    log_level: str = "INFO"

    @field_validator("user_tz")
    @classmethod
    def _validate_tz(cls, v: str) -> str:
        ZoneInfo(v)  # raises if invalid
        return v

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.user_tz)

    @property
    def user_phone_last4(self) -> str:
        return self.user_phone[-4:] if self.user_phone else "????"

    @property
    def fast_fallback_chain(self) -> list[str]:
        return [m.strip() for m in self.llm_fast_fallbacks.split(",") if m.strip()]

    @property
    def quality_fallback_chain(self) -> list[str]:
        return [m.strip() for m in self.llm_quality_fallbacks.split(",") if m.strip()]

    def validate_required_for_runtime(self) -> list[str]:
        """Return a list of missing-but-required fields. Callers decide whether to raise."""
        missing: list[str] = []
        for key in (
            "twilio_account_sid",
            "twilio_auth_token",
            "twilio_from_number",
            "user_phone",
        ):
            if not getattr(self, key):
                missing.append(key)
        if not (
            self.anthropic_api_key
            or self.openai_api_key
            or self.gemini_api_key
            or self.minimax_api_key
        ):
            missing.append("at least one of ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / MINIMAX_API_KEY")
        if not self.google_sheets_id:
            missing.append("google_sheets_id")
        if not Path(self.google_service_account_json_path).exists():
            missing.append(f"service account json at {self.google_service_account_json_path}")
        return missing


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
