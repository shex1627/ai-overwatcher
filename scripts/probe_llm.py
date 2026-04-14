"""Probe every model in the LLM fallback chains. No production code depends on this.

Run:  .venv/bin/python scripts/probe_llm.py

For each model:
  1. Does a plain `litellm.completion` succeed? (wire test)
  2. Does an Instructor structured-output call succeed? (schema test)

Prints a table. Any FAIL means the model string needs fixing in .env before Phase 4.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure src is importable when running as a script.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env manually (we don't want to depend on pydantic-settings here).
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

import instructor  # noqa: E402
import litellm  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class Ping(BaseModel):
    ok: bool
    word: str


def _chain(env_key: str) -> list[str]:
    raw = os.environ.get(env_key, "")
    return [m.strip() for m in raw.split(",") if m.strip()]


MODELS: list[tuple[str, str]] = [
    ("fast_primary", os.environ.get("LLM_FAST_MODEL", "")),
    *[("fast_fallback", m) for m in _chain("LLM_FAST_FALLBACKS")],
    ("quality_primary", os.environ.get("LLM_QUALITY_MODEL", "")),
    *[("quality_fallback", m) for m in _chain("LLM_QUALITY_FALLBACKS")],
]


def probe_plain(model: str) -> tuple[bool, str, float]:
    t0 = time.monotonic()
    try:
        resp = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
            max_tokens=10,
            timeout=15,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        text = (resp.choices[0].message.content or "").strip()
        return True, text[:40], latency_ms
    except Exception as exc:  # noqa: BLE001
        latency_ms = (time.monotonic() - t0) * 1000
        return False, f"{type(exc).__name__}: {str(exc)[:120]}", latency_ms


def probe_structured(model: str) -> tuple[bool, str, float]:
    t0 = time.monotonic()
    try:
        client = instructor.from_litellm(litellm.completion)
        result: Ping = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Return ok=true and word='pong' in the schema."},
            ],
            response_model=Ping,
            max_tokens=300,
            timeout=20,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        return True, f"ok={result.ok} word={result.word!r}", latency_ms
    except Exception as exc:  # noqa: BLE001
        latency_ms = (time.monotonic() - t0) * 1000
        return False, f"{type(exc).__name__}: {str(exc)[:120]}", latency_ms


def main() -> int:
    print(f"{'tier':<18} {'model':<40} {'plain':<8} {'struct':<8} {'notes'}")
    print("-" * 120)
    any_failures = False
    for tier, model in MODELS:
        if not model:
            continue
        plain_ok, plain_note, plain_ms = probe_plain(model)
        struct_ok, struct_note, struct_ms = probe_structured(model)
        status_p = f"{'OK' if plain_ok else 'FAIL'} {plain_ms:>5.0f}ms"
        status_s = f"{'OK' if struct_ok else 'FAIL'} {struct_ms:>5.0f}ms"
        print(f"{tier:<18} {model:<40} {status_p:<8} {status_s:<8}")
        if not plain_ok:
            print(f"    plain_err:  {plain_note}")
            any_failures = True
        if not struct_ok:
            print(f"    struct_err: {struct_note}")
            any_failures = True
        if plain_ok and struct_ok:
            print(f"    plain: {plain_note}   struct: {struct_note}")
    return 1 if any_failures else 0


if __name__ == "__main__":
    sys.exit(main())
