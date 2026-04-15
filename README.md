# Overwatcher

SMS accountability agent for one person. Texts a morning intent prompt, routes every inbound SMS through an LLM classifier, manages user-declared timers, sends an evening reality check and a Friday weekly summary. Built for N=1 as a testable wedge for executive-dysfunction support.

Full design in [docs/architecture.md](./docs/architecture.md). Feature rationale in [docs/mvp.md](./docs/mvp.md), behavior model in [docs/behavior-science.md](./docs/behavior-science.md), LLM routing in [docs/llm-chains.md](./docs/llm-chains.md).

## Stack

- Python 3.12, FastAPI + Uvicorn (single worker), APScheduler with SQLite jobstore
- SQLite + SQLModel (WAL) as source of truth; Google Sheets as append-only transcript
- LiteLLM + Instructor behind a facade in [src/overwatcher/llm.py](./src/overwatcher/llm.py), two tiers with independent fallback chains
- Twilio for SMS; Cloudflare Tunnel for public ingress
- Self-hosted on an always-on home box under two user-mode systemd units ([DEPLOYMENT.md](./DEPLOYMENT.md))

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in
```

## Run (dev)

```bash
uvicorn overwatcher.main:app --reload --host 127.0.0.1 --port 8000
```

`/healthz` should return 200.

## Test

```bash
pytest
```

## Utility scripts

- `python scripts/probe_llm.py` — monthly wire-test of every model in the fallback chains (one plain + one structured call each) to catch provider retirements.
- `python scripts/bench_llm_latency.py` — latency benchmark. Runs ≥5 trials per (model, prompt) with a warmup, reports mean / p50 / p95 / min / max / stdev, writes raw trials to `benchmarks/*.csv` and summaries to `*.json`. Use before promoting a model between fast and quality tiers. Pass `--models <id> [<id> ...]` to test arbitrary litellm-supported ids outside the chain.

## Layout

```
src/overwatcher/    app code (routes, handlers, classifier, llm, timers, jobs, prompts)
tests/              mirrors the src layout
scripts/            probe_llm.py, bench_llm_latency.py
docs/               architecture, mvp, behavior, llm-chains, evaluation, ...
resources/          Google service-account key
```
