"""End-to-end inbound pipeline with Twilio/LLM mocked out.

Verifies: webhook accepts → classifier runs (heuristic) → handler produces reply → send_sms called.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from overwatcher import db
from overwatcher.main import app


def _form(sid: str = "SMe2e1", body: str = "start design 30min") -> dict[str, str]:
    return {
        "From": "+15551111111",
        "Body": body,
        "MessageSid": sid,
        "To": "+15550000000",
        "NumMedia": "0",
        "SmsStatus": "received",
    }


def test_pipeline_start_command_sends_sms():
    db.init_db()
    with patch("overwatcher.routes.sms.sms.send_sms") as send, \
         patch("overwatcher.handlers.get_scheduler"):
        send.return_value = "SMreply123"
        with TestClient(app) as client:
            r = client.post("/sms/inbound", data=_form())
            assert r.status_code == 200

    send.assert_called_once()
    (reply,), _kwargs = send.call_args
    assert "design" in reply.lower()
    assert "30" in reply


def test_pipeline_empty_body_gets_empty_template():
    db.init_db()
    with patch("overwatcher.routes.sms.sms.send_sms") as send, \
         patch("overwatcher.handlers.get_scheduler"):
        send.return_value = "SMreply456"
        with TestClient(app) as client:
            r = client.post("/sms/inbound", data=_form(sid="SMempty", body=""))
            assert r.status_code == 200

    send.assert_called_once()
    (reply,), _ = send.call_args
    assert "empty" in reply.lower()
