"""Typed LLM call wrappers, one per prompt.

Each function:
- loads the versioned prompt
- wraps user content in <user_input> (the prompt itself already has the tags; we just render)
- calls LiteLLM+Instructor for structured output or plain text
- on total failure, returns a deterministic fallback (never raises into the hot path)
- logs prompt_version, model used, latency, request_id
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from overwatcher import llm, prompts_loader
from overwatcher.errors import LLMTimeoutError
from overwatcher.schemas import ClassifierOutput, Intent

log = logging.getLogger(__name__)


def _fmt_recent(messages: list[dict]) -> str:
    if not messages:
        return "  (none)"
    lines = []
    for m in messages[-5:]:
        ts = m.get("ts", "?")[:16]  # drop seconds
        direction = m.get("direction", "?")
        text = (m.get("raw_text") or "").replace("\n", " ")[:120]
        lines.append(f"  [{ts}] {direction}: {text}")
    return "\n".join(lines)


def llm_classify(
    *,
    body: str,
    now: datetime,
    has_morning_reply_today: bool,
    has_evening_reply_today: bool,
    recent_messages: list[dict],
    request_id: Optional[str] = None,
) -> Optional[ClassifierOutput]:
    """LLM-first classification. Returns None on total failure — caller falls back to heuristic."""
    prompt = prompts_loader.load("classifier")
    rendered = prompt.render(
        now_iso=now.isoformat(),
        has_morning_reply_today=str(has_morning_reply_today).lower(),
        has_evening_reply_today=str(has_evening_reply_today).lower(),
        recent_messages=_fmt_recent(recent_messages),
        body=body,
    )
    try:
        return llm.structured(
            tier="fast",
            messages=[{"role": "user", "content": rendered}],
            response_model=ClassifierOutput,
            max_tokens=500,
            soft_timeout_s=5.0,
            request_id=request_id,
            prompt_version=f"classifier.v{prompt.version}",
        )
    except LLMTimeoutError:
        log.warning("classifier_llm_total_failure", extra={"request_id": request_id})
        return None
    except Exception as exc:  # noqa: BLE001 — Instructor/Pydantic validation errors end up here
        log.warning(
            "classifier_llm_schema_invalid",
            extra={"request_id": request_id, "error_class": type(exc).__name__},
        )
        return None


def llm_warm_ack(
    *,
    body: str,
    intent: Intent,
    active_timers: list[dict],
    morning_intent: Optional[str],
    request_id: Optional[str] = None,
) -> Optional[str]:
    """Generate a warm reply. Returns None on total failure — caller falls back to template."""
    prompt = prompts_loader.load("warm_ack")
    active_str = "none" if not active_timers else "; ".join(
        f"{t['task']} ({t['duration_min']}min)" for t in active_timers
    )
    rendered = prompt.render(
        intent=intent.value,
        active_timers=active_str,
        morning_intent=morning_intent or "not set",
        body=body,
    )
    try:
        text = llm.complete_text(
            tier="fast",
            messages=[{"role": "user", "content": rendered}],
            max_tokens=200,
            soft_timeout_s=5.0,
            request_id=request_id,
            prompt_version=f"warm_ack.v{prompt.version}",
        )
    except LLMTimeoutError:
        log.warning("warm_ack_llm_total_failure", extra={"request_id": request_id})
        return None
    # Hard cap just in case the model ignored our instruction.
    return text.strip()[:300] or None


def llm_morning_pushback(
    *,
    body: str,
    if_then_items: list[dict],
    request_id: Optional[str] = None,
) -> Optional[str]:
    prompt = prompts_loader.load("morning_pushback")
    rendered = prompt.render(
        if_then_items=json.dumps(if_then_items) if if_then_items else "none",
        body=body,
    )
    try:
        text = llm.complete_text(
            tier="quality",
            messages=[{"role": "user", "content": rendered}],
            max_tokens=200,
            soft_timeout_s=8.0,
            request_id=request_id,
            prompt_version=f"morning_pushback.v{prompt.version}",
        )
    except LLMTimeoutError:
        log.warning("morning_pushback_llm_total_failure", extra={"request_id": request_id})
        return None
    return text.strip()[:300] or None


def llm_evening_followup(
    *,
    body: str,
    morning_intent: Optional[str],
    request_id: Optional[str] = None,
) -> Optional[str]:
    prompt = prompts_loader.load("evening_followup")
    rendered = prompt.render(
        morning_intent=morning_intent or "not set",
        body=body,
    )
    try:
        text = llm.complete_text(
            tier="quality",
            messages=[{"role": "user", "content": rendered}],
            max_tokens=200,
            soft_timeout_s=8.0,
            request_id=request_id,
            prompt_version=f"evening_followup.v{prompt.version}",
        )
    except LLMTimeoutError:
        log.warning("evening_followup_llm_total_failure", extra={"request_id": request_id})
        return None
    return text.strip()[:300] or None


def llm_weekly_summary(
    *,
    messages: list[dict],
    start_ts: str,
    end_ts: str,
    request_id: Optional[str] = None,
) -> Optional[str]:
    prompt = prompts_loader.load("weekly_summary")
    # Compact representation — drop noisy fields, cap body length per message.
    compact = [
        {
            "ts": m.get("ts", "")[:16],
            "direction": m.get("direction"),
            "type": m.get("type"),
            "text": (m.get("raw_text") or "")[:200],
        }
        for m in messages
    ]
    rendered = prompt.render(
        start_ts=start_ts,
        end_ts=end_ts,
        message_count=len(messages),
        messages_json=json.dumps(compact, ensure_ascii=False),
    )
    try:
        text = llm.complete_text(
            tier="quality",
            messages=[{"role": "user", "content": rendered}],
            max_tokens=400,
            soft_timeout_s=30.0,
            request_id=request_id,
            prompt_version=f"weekly_summary.v{prompt.version}",
        )
    except LLMTimeoutError:
        log.warning("weekly_summary_llm_total_failure", extra={"request_id": request_id})
        return None
    return text.strip()[:600] or None
