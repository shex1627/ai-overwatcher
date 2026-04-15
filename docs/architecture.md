---
title: Architecture
updated: 2026-04-15
audience: Contributors and future-me starting a new feature
---

# Overwatcher — Architecture

Single-source-of-truth for what the project is, why it's built the way it is, and how the pieces fit. Feature-spec and research rationale live in the other docs under [docs/](./); this doc links out rather than duplicating.

## 1. What it does

Overwatcher is a personalized SMS accountability agent for executive dysfunction. It:

- Texts a **morning intent prompt** at 09:00 and pushes back once if the plan is vague or overambitious ([mvp.md](./mvp.md)).
- Routes every inbound SMS through an LLM classifier into one of a fixed set of intents (command, progress, question, morning/evening reply, emotional, empty, quiet) and **warmly acknowledges** every turn ([behavior-science.md](./behavior-science.md)).
- Manages **user-declared timers** (`start X 30min`, `done`, `stuck`, `cancel`) with mid-check and end-check rules ([feedback-cycles.md](./feedback-cycles.md)).
- On `stuck` during a timer, pauses the timer, asks the **internal-trigger question** ("what were you feeling?"), offers a smallest-next-step, and optionally resumes — the highest-value flow.
- Sends an **evening reality check** at 21:00 and a **Friday 17:00 weekly summary** (4–6 sentences, data + pattern + identity line).
- Logs every message and timer event to **SQLite** (source of truth) and **Google Sheets** (append-only, human-viewable).

Built for N=1 (the author) as a testable wedge; commercial thinking in [adhd-wedge.md](./adhd-wedge.md).

## 2. Why these choices

Decisions worth knowing before changing anything:

- **Python 3.12 + FastAPI + Uvicorn single worker.** Best LLM SDK ecosystem; async webhook handling; no need for multi-worker at N=1. Twilio webhook budget is 10s — inbound handler returns 200 immediately and does the real work in a background task.
- **SQLite + SQLModel, WAL mode.** Hot state fits in one file; zero ops; survives unclean shutdown. No Postgres until multi-user.
- **APScheduler in-process with SQLite jobstore.** Persistent cron without Redis/Celery. `misfire_grace_time=300s` so a brief restart doesn't skip the morning send. See [src/overwatcher/scheduler.py](../src/overwatcher/scheduler.py).
- **LiteLLM + Instructor behind a facade** ([src/overwatcher/llm.py](../src/overwatcher/llm.py)). One interface, many providers, Pydantic-validated structured output. Two tiers with independent fallback chains — full rationale in [llm-chains.md](./llm-chains.md) and [llm-abstraction-and-flows.md](./llm-abstraction-and-flows.md):
  - **Fast tier** (classifier, warm-ack, timer parser): Claude Haiku 4.5 primary → MiniMax-M2.5-highspeed → Gemini 3-Flash → GPT-5.4-mini. Budget 2s soft / 5s hard (webhook path).
  - **Quality tier** (morning pushback, evening follow-up, weekly summary): MiniMax-M2.7 primary → Sonnet 4.5 → GPT-5.4 → Gemini 3.1-Pro → Opus 4.6. Budget up to 30s (off webhook path, runs from scheduler or background task).
- **Heuristic fallback** when every provider fails: deterministic regex rules + template replies. The agent never goes silent on the user.
- **Prompts as versioned markdown** under [src/overwatcher/prompts/](../src/overwatcher/prompts/), loaded at startup via [prompts_loader.py](../src/overwatcher/prompts_loader.py). Anti-slop rules (no emojis, ≤3 sentences, never "I'm here to help!") live in the prompt, not the code.
- **Google Sheets is cosmetic, not load-bearing.** Decisions read from SQLite. Sheet writes are async best-effort; if Sheets is down the agent keeps working. Commit `606cce6` added outbound logging so the Sheet is a complete conversation transcript.
- **Twilio signature validation is non-negotiable.** Webhook rejects anything that doesn't validate; phone-number mismatch drops silently with 200.
- **Cloudflare Tunnel, not port-forward.** Free TLS, stable hostname, no router config. The tunnel is a second systemd unit that depends on the API unit.
- **Self-hosted on always-on home box**, not PaaS. Zero hosting bill, direct access to sqlite3 and journalctl, scheduler reliable. Acceptable because N=1.

See [technical-implementation.md](./technical-implementation.md) and the design audit in [technical-review.md](./technical-review.md) for the long-form version of each decision.

## 3. Module layout

```
src/overwatcher/
├── main.py              FastAPI app + lifespan (starts scheduler, registers jobs)
├── config.py            Pydantic Settings, reads .env
├── routes/
│   ├── sms.py           POST /sms/inbound — Twilio webhook
│   └── health.py        GET /healthz
├── classifier.py        LLM intent classifier (fast tier + fallback)
├── handlers.py          Intent dispatch → reply text or None
├── llm.py               LiteLLM + Instructor facade with fallback chains
├── llm_calls.py         High-level prompt calls (pushback, warm-ack, summary…)
├── prompts/             Markdown prompts, versioned with code
├── prompts_loader.py    Load prompts at startup
├── schemas.py           Pydantic output schemas (ClassifierOutput, Command, …)
├── sms.py               Twilio wrapper: send_sms, validate_signature
├── sheets.py            Google Sheets append (async, best-effort)
├── models.py            SQLModel: Message, Timer, DayState
├── db.py                SQLite session factory
├── repo.py              Typed data-access helpers
├── timers.py            Timer state logic + mid-check rules
├── quiet.py             Quiet-window state
├── pending.py           Pending implicit-timer offers (ask-then-confirm)
├── scheduler.py         APScheduler setup + daily job registration
├── jobs/
│   ├── morning.py       09:00 daily
│   ├── evening.py       21:00 daily
│   ├── weekly.py        Fri 17:00
│   ├── heartbeat.py     12:00 daily internal log
│   └── timer_check.py   Per-timer mid-check and end-check
├── errors.py            Named exceptions
└── logging_setup.py     Structured JSON logging
```

Tests in [tests/](../tests/) mirror this layout (classifier, handlers, timers, inbound pipeline, phase4, smoke, config). Utility scripts:
- [scripts/probe_llm.py](../scripts/probe_llm.py) — monthly wire-test of every model in the fallback chains to catch retirements (one call per model, plain + structured).
- [scripts/bench_llm_latency.py](../scripts/bench_llm_latency.py) — latency benchmark across the chains (or arbitrary `--models` ids). Runs ≥5 trials per (model, prompt) with a warmup, reports mean/p50/p95/min/max/stdev, writes raw trials to `benchmarks/*.csv` and summaries to `*.json`. Use before promoting a model between fast/quality tiers.

## 4. Data flow — inbound SMS

1. User sends SMS. Twilio POSTs to `https://overwatcher.ftdalpha.com/sms/inbound` via Cloudflare Tunnel.
2. [routes/sms.py](../src/overwatcher/routes/sms.py) validates the Twilio signature, checks `From == USER_PHONE`, dedupes on `MessageSid` (unique constraint), inserts a placeholder inbound `Message` row, returns 200 within the 10s budget.
3. Background task pulls the last 5 messages as context and calls `classifier.classify(body, context)` → `ClassifierOutput(intent, command?, if_then_items?, implicit_timer?, internal_trigger_flags?)`. LLM fallback chain applies; on total failure, heuristic rules.
4. The inbound `Message` row is updated with `type = intent` and `parsed_json = output.json`. Google Sheets append fires async.
5. [handlers.py](../src/overwatcher/handlers.py) routes by intent:
   - `command` → [timers.py](../src/overwatcher/timers.py) / [quiet.py](../src/overwatcher/quiet.py) state change, warm reply.
   - `morning_reply` → update `day_state.morning_intent_json`, optionally LLM pushback.
   - `evening_reply` → LLM follow-up, compares to morning items, may ask internal-trigger question if drift.
   - `progress` / `question` / `emotional` → LLM warm-ack with active-timer + morning-intent context.
   - `empty` → template "Got an empty message. You ok?"
   - `quiet` → silent (still logged).
6. Reply sent via `sms.send_sms()`. Outbound `Message` row inserted; Sheets append fires.

## 5. Data flow — scheduled jobs

APScheduler with SQLite jobstore in [src/overwatcher/scheduler.py](../src/overwatcher/scheduler.py). Time zone is `USER_TZ` from config (America/Los_Angeles).

- **09:00 daily** — [jobs/morning.py](../src/overwatcher/jobs/morning.py) sends intent prompt, upserts `day_state(mode="bookend")`.
- **21:00 daily** — [jobs/evening.py](../src/overwatcher/jobs/evening.py) reads `day_state.morning_intent_json`, sends reality prompt.
- **Fri 17:00** — [jobs/weekly.py](../src/overwatcher/jobs/weekly.py) selects last 7 days of messages, calls quality-tier LLM summary, sends 4–6 sentence recap.
- **12:00 daily** — [jobs/heartbeat.py](../src/overwatcher/jobs/heartbeat.py) inserts an internal row with sent-count and LLM-latency p50/p99. If this row goes stale, something broke.
- **Per-timer** — [jobs/timer_check.py](../src/overwatcher/jobs/timer_check.py) schedules end-check at `start_ts + duration + 2min`. Mid-check at ~50% only when duration >90min or user opted in; suppressed if user sent a progress note in the last 20min.

## 6. Storage

**SQLite** at `/home/bookworm/code/ai-overwatcher/data/state.db`, WAL mode. Source of truth.

- `messages` — every inbound/outbound message. Dedupe key `twilio_sid UNIQUE`. Fields: `ts, direction, type, mode, raw_text, parsed_json, twilio_sid, request_id, related_timer_id`.
- `timers` — declared work blocks and their lifecycle. `status ∈ {active, paused, completed, cancelled}`. Fields include `task, duration_min, start_ts, end_ts_scheduled, mid_check_ts, notes`.
- `day_state` — per-day: `mode`, `morning_intent_json`, refs to morning/evening message rows, `last_inbound_ts`.
- `apscheduler_jobs` — APScheduler's own table.

**Google Sheets** — append-only log. Columns: `timestamp, direction, type, mode, raw_text, parsed, timer_id, request_id`. Viewable on phone. Never read by the app for decisions.

## 7. External services and failure modes

| Service | Used for | Failure mode |
|---|---|---|
| Twilio | SMS send + webhook | App still runs; scheduled jobs fire but can't send. Twilio retries inbound 3× ~10 min. |
| Anthropic / OpenAI / Google / MiniMax | LLM inference | Provider down → next in chain. All down → heuristic + template. |
| Google Sheets | Append-only transcript | Logging stops; SMS functionality unaffected. |
| Cloudflare Tunnel | Public HTTPS ingress | Inbound SMS can't reach app; local scheduler still fires. |

Full rescue map (signature invalid, duplicate webhook, LLM timeout, rate limit, invalid structured output, send failure, Sheets down, SQLite full, scheduler misfire, prompt injection, clock skew, empty message) is in [technical-review.md](./technical-review.md).

## 8. Deployment

Runbook in [DEPLOYMENT.md](../DEPLOYMENT.md). Summary:

- Home Debian box `bookhouse`. Code in `/home/bookworm/code/ai-overwatcher/`, venv via pyenv, `.env` alongside, Google SA key under [resources/](../resources/).
- Two user-mode systemd units:
  - `overwatcher_api` — `uvicorn overwatcher.main:app --host 127.0.0.1 --port 8123`.
  - `overwatcher_tunnel` — `cloudflared tunnel run` with `After=overwatcher_api.service`.
- Tunnel ID `f8c9ee81-91ce-4535-bb7b-97f835dc7690`, public URL `https://overwatcher.ftdalpha.com/sms/inbound` (Twilio webhook target).
- Logs: `journalctl --user -u overwatcher_api -f`. DB: `sqlite3 data/state.db`.

## 9. Observability

- **JSON structured logs** via python-json-logger. Every line carries `ts, level, event, request_id, user_phone_last4, llm_model, llm_latency_ms, error_class`. Configured in [logging_setup.py](../src/overwatcher/logging_setup.py).
- **Request ID** generated at webhook entry and propagated through LLM, Sheets, and Twilio-send calls. One request_id == one conversation turn.
- **Daily heartbeat row** at 12:00 includes `sent_count, p50_llm_ms, p99_llm_ms, error_count_24h`. Missing for >36h = broken.
- **Named exceptions only** ([errors.py](../src/overwatcher/errors.py)). No bare `except Exception`.

## 10. Where to go next

- Adding a feature? Start with [mvp.md](./mvp.md) for the feature list, then [feedback-cycles.md](./feedback-cycles.md) for how cadence should behave.
- Changing an LLM call? Read [llm-abstraction-and-flows.md](./llm-abstraction-and-flows.md) and [llm-chains.md](./llm-chains.md) first; keep the fallback chain and timeouts intact.
- Changing the prompt? Edit the markdown under [src/overwatcher/prompts/](../src/overwatcher/prompts/). Keep anti-slop rules.
- Changing behavior on the wire? The inbound pipeline test in [tests/test_inbound_pipeline.py](../tests/test_inbound_pipeline.py) is the first place to update.
- Evaluating quality? [evaluation.md](./evaluation.md).
