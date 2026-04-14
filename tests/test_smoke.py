"""Smoke tests — the minimum that proves the scaffold is wired together.

These do NOT hit Twilio, the LLM, or Sheets. They only verify:
- the app boots,
- `/healthz` returns 200,
- the inbound webhook dedupes on MessageSid,
- phone-mismatch messages are dropped,
- signature validation rejects when a token is configured.
"""
from fastapi.testclient import TestClient

from overwatcher import db
from overwatcher.main import app


def _form(sid: str = "SM1", from_: str = "+15551111111", body: str = "hi") -> dict[str, str]:
    return {
        "From": from_,
        "Body": body,
        "MessageSid": sid,
        "To": "+15550000000",
        "NumMedia": "0",
        "SmsStatus": "received",
    }


def test_healthz():
    db.init_db()
    with TestClient(app) as client:
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_inbound_accepts_and_persists():
    db.init_db()
    with TestClient(app) as client:
        r = client.post("/sms/inbound", data=_form(sid="SMsmoke1"))
        assert r.status_code == 200

    from sqlmodel import Session, select

    from overwatcher.db import get_engine
    from overwatcher.models import Message

    with Session(get_engine()) as session:
        rows = session.exec(select(Message).where(Message.twilio_sid == "SMsmoke1")).all()
        assert len(rows) == 1
        assert rows[0].direction == "in"
        assert rows[0].raw_text == "hi"


def test_inbound_dedupes_on_sid():
    db.init_db()
    with TestClient(app) as client:
        r1 = client.post("/sms/inbound", data=_form(sid="SMdup"))
        r2 = client.post("/sms/inbound", data=_form(sid="SMdup"))
        assert r1.status_code == 200
        assert r2.status_code == 200

    from sqlmodel import Session, select

    from overwatcher.db import get_engine
    from overwatcher.models import Message

    with Session(get_engine()) as session:
        rows = session.exec(select(Message).where(Message.twilio_sid == "SMdup")).all()
        assert len(rows) == 1  # second POST was a no-op


def test_inbound_drops_wrong_sender():
    db.init_db()
    with TestClient(app) as client:
        r = client.post("/sms/inbound", data=_form(sid="SMwrong", from_="+15559999999"))
        assert r.status_code == 200

    from sqlmodel import Session, select

    from overwatcher.db import get_engine
    from overwatcher.models import Message

    with Session(get_engine()) as session:
        rows = session.exec(select(Message).where(Message.twilio_sid == "SMwrong")).all()
        assert rows == []


def test_signature_rejected_when_token_present(monkeypatch):
    """If TWILIO_AUTH_TOKEN is set, an unsigned request must be rejected with 403."""
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "fake_token_for_test")
    from overwatcher.config import get_settings

    get_settings.cache_clear()

    db.init_db()
    with TestClient(app) as client:
        r = client.post("/sms/inbound", data=_form(sid="SMsig"))
        assert r.status_code == 403
