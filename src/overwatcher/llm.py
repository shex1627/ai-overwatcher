"""LLM facade: LiteLLM + Instructor with a per-call-type fallback chain.

Two call tiers:
- `fast`: classifier, warm-ack, timer parsing. Low latency requirement (<2s soft, <5s hard).
- `quality`: morning pushback, evening follow-up, weekly summary. Reasoning matters more than speed.

Every call:
- wraps user content in <user_input> tags (prompt injection defense),
- enforces a Pydantic schema via Instructor where structured output is needed,
- tries primary, then walks the fallback chain on timeout / rate-limit,
- logs `llm_model`, `llm_latency_ms`, and `prompt_version` on every call.
"""
from __future__ import annotations

import logging
import time
from typing import Type, TypeVar

import instructor
import litellm
from pydantic import BaseModel

from overwatcher.config import get_settings
from overwatcher.errors import LLMTimeoutError

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def wrap_user_input(text: str) -> str:
    """Every user-provided string must pass through this before entering a prompt."""
    return f"<user_input>\n{text}\n</user_input>"


def _instructor_client():
    # from_litellm yields a wrapper that accepts `response_model=` on completions
    return instructor.from_litellm(litellm.completion)


def _chain_for(tier: str) -> list[str]:
    s = get_settings()
    if tier == "fast":
        return [s.llm_fast_model, *s.fast_fallback_chain]
    if tier == "quality":
        return [s.llm_quality_model, *s.quality_fallback_chain]
    raise ValueError(f"unknown tier: {tier}")


def structured(
    *,
    tier: str,
    messages: list[dict[str, str]],
    response_model: Type[T],
    max_tokens: int = 500,
    soft_timeout_s: float = 5.0,
    request_id: str | None = None,
    prompt_version: str | None = None,
) -> T:
    """Run a structured-output LLM call with provider fallback. Raises LLMTimeoutError on total failure."""
    client = _instructor_client()
    last_exc: Exception | None = None
    for model in _chain_for(tier):
        t0 = time.monotonic()
        try:
            result = client.chat.completions.create(  # type: ignore[attr-defined]
                model=model,
                messages=messages,
                response_model=response_model,
                max_tokens=max_tokens,
                timeout=soft_timeout_s,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            log.info(
                "llm_call_ok",
                extra={
                    "llm_model": model,
                    "llm_tier": tier,
                    "llm_latency_ms": latency_ms,
                    "request_id": request_id,
                    "prompt_version": prompt_version,
                },
            )
            return result
        except Exception as exc:  # noqa: BLE001 — intentionally broad; we log + try next provider
            latency_ms = int((time.monotonic() - t0) * 1000)
            log.warning(
                "llm_call_failed",
                extra={
                    "llm_model": model,
                    "llm_tier": tier,
                    "llm_latency_ms": latency_ms,
                    "error_class": type(exc).__name__,
                    "request_id": request_id,
                },
            )
            last_exc = exc
            continue
    raise LLMTimeoutError(
        f"all providers failed for tier={tier}; last_error={type(last_exc).__name__}: {last_exc}"
    ) from last_exc


def complete_text(
    *,
    tier: str,
    messages: list[dict[str, str]],
    max_tokens: int = 500,
    soft_timeout_s: float = 5.0,
    request_id: str | None = None,
    prompt_version: str | None = None,
) -> str:
    """Unstructured text completion with the same fallback chain. Used for warm-acks."""
    last_exc: Exception | None = None
    for model in _chain_for(tier):
        t0 = time.monotonic()
        try:
            resp = litellm.completion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=soft_timeout_s,
            )
            latency_ms = int((time.monotonic() - t0) * 1000)
            text = resp.choices[0].message.content or ""
            log.info(
                "llm_call_ok",
                extra={
                    "llm_model": model,
                    "llm_tier": tier,
                    "llm_latency_ms": latency_ms,
                    "request_id": request_id,
                    "prompt_version": prompt_version,
                },
            )
            return text
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "llm_call_failed",
                extra={
                    "llm_model": model,
                    "llm_tier": tier,
                    "error_class": type(exc).__name__,
                    "request_id": request_id,
                },
            )
            last_exc = exc
            continue
    raise LLMTimeoutError(
        f"all providers failed for tier={tier}; last_error={type(last_exc).__name__}: {last_exc}"
    ) from last_exc
