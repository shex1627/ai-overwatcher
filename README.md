# Overwatcher

SMS accountability agent for one person. See [docs/](./docs/) for the full design.

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
