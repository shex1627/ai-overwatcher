"""Twilio send + signature validation. Thin wrapper; retries live here too."""
from __future__ import annotations

import logging

from twilio.request_validator import RequestValidator
from twilio.rest import Client

from overwatcher.config import get_settings

log = logging.getLogger(__name__)


def _client() -> Client:
    s = get_settings()
    return Client(s.twilio_account_sid, s.twilio_auth_token)


def validate_signature(url: str, params: dict[str, str], signature: str) -> bool:
    s = get_settings()
    if not s.twilio_auth_token:
        # In dev with no token configured, skip validation but log loudly.
        log.warning("twilio_signature_skipped_no_token")
        return True
    validator = RequestValidator(s.twilio_auth_token)
    return validator.validate(url, params, signature or "")


def send_sms(body: str, *, request_id: str | None = None) -> str:
    """Send to the configured USER_PHONE. Returns the Twilio SID."""
    s = get_settings()
    msg = _client().messages.create(
        to=s.user_phone,
        from_=s.twilio_from_number,
        body=body,
    )
    log.info(
        "sms_sent",
        extra={
            "twilio_sid": msg.sid,
            "request_id": request_id,
            "user_phone_last4": s.user_phone_last4,
            "length": len(body),
        },
    )
    return msg.sid
