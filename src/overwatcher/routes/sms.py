"""POST /sms/inbound — Twilio webhook.

Flow: validate signature → phone-check → dedupe → insert inbound row → schedule
classification + handler dispatch as a background task → return 200 under Twilio's 10s budget.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Form, Header, HTTPException, Request, Response
from sqlmodel import select

from overwatcher import classifier, db, handlers, repo, sheets, sms
from overwatcher.config import get_settings
from overwatcher.models import Message

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sms", tags=["sms"])


@router.post("/inbound")
async def inbound(
    request: Request,
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(""),
    MessageSid: str = Form(...),
    To: str = Form(""),
    NumMedia: int = Form(0),
    SmsStatus: str = Form(""),
    x_twilio_signature: str | None = Header(default=None, alias="X-Twilio-Signature"),
) -> Response:
    request_id = uuid.uuid4().hex
    settings = get_settings()

    # Twilio signs the public URL it hit, not our internal one.
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    public_url = f"{settings.public_webhook_base_url.rstrip('/')}/sms/inbound"
    if not sms.validate_signature(public_url, params, x_twilio_signature or ""):
        log.warning(
            "twilio_signature_invalid",
            extra={"request_id": request_id, "twilio_sid": MessageSid},
        )
        raise HTTPException(status_code=403, detail="invalid signature")

    if settings.user_phone and From != settings.user_phone:
        log.warning(
            "phone_number_mismatch",
            extra={"request_id": request_id, "twilio_sid": MessageSid},
        )
        return Response(status_code=200)

    # Dedupe on Twilio SID (unique constraint enforces at DB level too).
    with db.session_scope() as session:
        existing = session.exec(select(Message).where(Message.twilio_sid == MessageSid)).first()
        if existing:
            log.info(
                "duplicate_webhook_ignored",
                extra={"request_id": request_id, "twilio_sid": MessageSid},
            )
            return Response(status_code=200)

        msg = Message(
            ts=datetime.now(settings.tz).isoformat(),
            direction="in",
            type="progress",  # placeholder — updated after classification
            raw_text=Body,
            twilio_sid=MessageSid,
            request_id=request_id,
        )
        session.add(msg)

    log.info(
        "inbound_received",
        extra={
            "request_id": request_id,
            "twilio_sid": MessageSid,
            "user_phone_last4": settings.user_phone_last4,
            "body_length": len(Body),
        },
    )

    background_tasks.add_task(_process_inbound, MessageSid, Body, request_id)
    return Response(status_code=200)


async def _process_inbound(message_sid: str, body: str, request_id: str) -> None:
    """Classify + dispatch + reply. Runs after the webhook returns so Twilio never sees timeouts."""
    settings = get_settings()
    now = datetime.now(settings.tz)
    today = now.strftime("%Y-%m-%d")

    # Pull the last handful of messages as context for the classifier.
    day_start_iso = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    recent = [
        {"ts": m.ts, "direction": m.direction, "raw_text": m.raw_text}
        for m in repo.messages_in_window(day_start_iso, now.isoformat())[-5:]
    ]
    try:
        result = await classifier.classify(
            body,
            now=now,
            has_morning_reply_today=repo.has_message_type_on(today, "morning_reply"),
            has_evening_reply_today=repo.has_message_type_on(today, "evening_reply"),
            recent_messages=recent,
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception(
            "classifier_failed",
            extra={"request_id": request_id, "error_class": type(exc).__name__},
        )
        return

    # Upgrade the inbound row's `type` to the classified intent + attach parsed output.
    with db.session_scope() as session:
        stmt = select(Message).where(Message.twilio_sid == message_sid)
        msg = session.exec(stmt).first()
        if msg is not None:
            msg.type = result.intent.value
            msg.parsed_json = result.model_dump_json()

    # Mirror inbound to Sheets (best-effort, cosmetic).
    try:
        sheets.append_row(
            timestamp=now.isoformat(),
            direction="in",
            type_=result.intent.value,
            mode=None,
            raw_text=body,
            parsed=result.model_dump_json(),
            timer_id=None,
            request_id=request_id,
        )
    except Exception as exc:  # noqa: BLE001 — Sheets is cosmetic
        log.warning(
            "sheets_append_failed",
            extra={"request_id": request_id, "error_class": type(exc).__name__},
        )

    reply = await handlers.route(
        body=body, classifier_output=result, now=now, request_id=request_id
    )
    if reply is None:
        return

    try:
        twilio_sid = sms.send_sms(reply, request_id=request_id)
    except Exception as exc:  # noqa: BLE001 — TwilioRestException / network
        log.exception(
            "twilio_send_failed",
            extra={"request_id": request_id, "error_class": type(exc).__name__},
        )
        return

    repo.insert_message(
        ts=datetime.now(settings.tz).isoformat(),
        direction="out",
        type_="ack",
        raw_text=reply,
        twilio_sid=twilio_sid,
        request_id=request_id,
    )
