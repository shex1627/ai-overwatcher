"""Benchmark latency of every model in the LLM fallback chains.

For each model, runs two prompts (short plain completion + structured-output)
N times each and reports mean / p50 / p95 / min / max / stdev. A warmup call
is made first per (model, prompt) and excluded from stats so we're measuring
steady-state, not cold-start.

Guidance applied (from shudaizi knowledge):
  - Multiple trials for non-determinism (agent_design checklist)
  - Report latency distribution p50/p95, not just mean (observability checklist)
  - Differences under ~3% are noise — infra-driven swings of ~6pts are normal
    (agent_design / observability checklists)

Run:
  .venv/bin/python scripts/bench_llm_latency.py                  # defaults: 5 trials
  .venv/bin/python scripts/bench_llm_latency.py --trials 10
  .venv/bin/python scripts/bench_llm_latency.py --models anthropic/claude-haiku-4-5

Outputs:
  benchmarks/llm_latency_<timestamp>.csv   raw per-trial rows
  benchmarks/llm_latency_<timestamp>.json  summary stats
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

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


class Classification(BaseModel):
    category: str
    confidence: float


PROMPT_SHORT = {
    "name": "short_plain",
    "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
    "max_tokens": 10,
}

PROMPT_STRUCTURED = {
    "name": "structured_classify",
    "messages": [
        {
            "role": "user",
            "content": (
                "Classify this SMS into one of: checkin, excuse, unknown. "
                "Message: 'just finished my workout, feeling great'. "
                "Return category and a confidence 0-1."
            ),
        },
    ],
    "max_tokens": 800,
}


def _chain(env_key: str) -> list[str]:
    raw = os.environ.get(env_key, "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def discover_models() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if m := os.environ.get("LLM_FAST_MODEL", ""):
        out.append(("fast_primary", m))
    out += [("fast_fallback", m) for m in _chain("LLM_FAST_FALLBACKS")]
    if m := os.environ.get("LLM_QUALITY_MODEL", ""):
        out.append(("quality_primary", m))
    out += [("quality_fallback", m) for m in _chain("LLM_QUALITY_FALLBACKS")]
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for tier, model in out:
        if model in seen:
            continue
        seen.add(model)
        deduped.append((tier, model))
    return deduped


def call_plain(model: str, prompt: dict) -> tuple[bool, float, str]:
    t0 = time.monotonic()
    try:
        resp = litellm.completion(
            model=model,
            messages=prompt["messages"],
            max_tokens=prompt["max_tokens"],
            timeout=30,
        )
        dt = (time.monotonic() - t0) * 1000
        text = (resp.choices[0].message.content or "").strip()
        return True, dt, text[:60]
    except Exception as exc:  # noqa: BLE001
        dt = (time.monotonic() - t0) * 1000
        return False, dt, f"{type(exc).__name__}: {str(exc)[:100]}"


def call_structured(model: str, prompt: dict) -> tuple[bool, float, str]:
    t0 = time.monotonic()
    try:
        client = instructor.from_litellm(litellm.completion)
        result: Classification = client.chat.completions.create(
            model=model,
            messages=prompt["messages"],
            response_model=Classification,
            max_tokens=prompt["max_tokens"],
            timeout=30,
        )
        dt = (time.monotonic() - t0) * 1000
        return True, dt, f"category={result.category} conf={result.confidence:.2f}"
    except Exception as exc:  # noqa: BLE001
        dt = (time.monotonic() - t0) * 1000
        return False, dt, f"{type(exc).__name__}: {str(exc)[:100]}"


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    if len(values) == 1:
        return values[0]
    s = sorted(values)
    k = (len(s) - 1) * pct
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def summarize(ms_values: list[float]) -> dict:
    if not ms_values:
        return {"n": 0}
    return {
        "n": len(ms_values),
        "mean_ms": round(statistics.fmean(ms_values), 1),
        "stdev_ms": round(statistics.stdev(ms_values), 1) if len(ms_values) > 1 else 0.0,
        "min_ms": round(min(ms_values), 1),
        "p50_ms": round(percentile(ms_values, 0.50), 1),
        "p95_ms": round(percentile(ms_values, 0.95), 1),
        "max_ms": round(max(ms_values), 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5, help="Trials per (model, prompt). Min 5.")
    parser.add_argument("--warmup", type=int, default=1, help="Warmup calls (excluded from stats).")
    parser.add_argument(
        "--models",
        nargs="*",
        help="Test these exact model ids instead of the .env chain. Any litellm-supported id works; "
        "errors surface in the output (e.g., NotFoundError for a bad id).",
    )
    parser.add_argument("--out-dir", default=str(ROOT / "benchmarks"))
    args = parser.parse_args()

    if args.trials < 5:
        print(f"[warn] --trials={args.trials} is below the recommended 5; bumping to 5.")
        args.trials = 5

    if args.models:
        chain = {m: t for t, m in discover_models()}
        models = [(chain.get(m, "adhoc"), m) for m in args.models]
    else:
        models = discover_models()
    if not models:
        print("No models to test.")
        return 1

    prompts = [
        (PROMPT_SHORT, call_plain),
        (PROMPT_STRUCTURED, call_structured),
    ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = out_dir / f"llm_latency_{stamp}.csv"
    json_path = out_dir / f"llm_latency_{stamp}.json"

    raw_rows: list[dict] = []
    summaries: list[dict] = []

    print(f"Trials={args.trials} warmup={args.warmup} models={len(models)} prompts={len(prompts)}")
    print("-" * 110)

    for tier, model in models:
        for prompt, caller in prompts:
            # Warmup
            for _ in range(args.warmup):
                caller(model, prompt)

            latencies_ok: list[float] = []
            ok_count = 0
            fail_count = 0
            last_note = ""
            for trial in range(args.trials):
                ok, dt_ms, note = caller(model, prompt)
                raw_rows.append(
                    {
                        "tier": tier,
                        "model": model,
                        "prompt": prompt["name"],
                        "trial": trial,
                        "ok": ok,
                        "latency_ms": round(dt_ms, 2),
                        "note": note,
                    }
                )
                last_note = note
                if ok:
                    ok_count += 1
                    latencies_ok.append(dt_ms)
                else:
                    fail_count += 1

            stats = summarize(latencies_ok)
            summary = {
                "tier": tier,
                "model": model,
                "prompt": prompt["name"],
                "trials": args.trials,
                "ok": ok_count,
                "fail": fail_count,
                **stats,
                "sample_note": last_note,
            }
            summaries.append(summary)

            tag = f"{model} [{prompt['name']}]"
            if ok_count == 0:
                print(f"{tag:<72} ALL FAILED  ({last_note})")
            else:
                print(
                    f"{tag:<72} "
                    f"ok={ok_count}/{args.trials} "
                    f"p50={stats['p50_ms']:>6.0f}ms "
                    f"p95={stats['p95_ms']:>6.0f}ms "
                    f"mean={stats['mean_ms']:>6.0f}ms "
                    f"min={stats['min_ms']:>6.0f} max={stats['max_ms']:>6.0f}"
                )

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(raw_rows[0].keys()))
        writer.writeheader()
        writer.writerows(raw_rows)

    with json_path.open("w") as f:
        json.dump(
            {
                "run_at": stamp,
                "trials_per_cell": args.trials,
                "warmup": args.warmup,
                "note": (
                    "Differences under ~3% are within infra noise (shudaizi agent_design "
                    "checklist). Prefer p95 over mean when comparing tail behavior."
                ),
                "summaries": summaries,
            },
            f,
            indent=2,
        )

    print("-" * 110)
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
