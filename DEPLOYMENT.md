# Overwatcher - Deployment Runbook

## Architecture Overview

Two systemd user services run on `bookhouse`:

```
overwatcher_api (FastAPI/uvicorn :8123)
  └─ overwatcher_tunnel (Cloudflare Tunnel, depends on api)
```

| Component | Port | Process | Public URL |
|-----------|------|---------|------------|
| FastAPI API | 8123 | uvicorn (1 worker) | https://overwatcher.ftdalpha.com |
| Cloudflare Tunnel | -- | cloudflared | Routes webhook hostname above |

The service binds to `127.0.0.1`. External access is exclusively through the Cloudflare Tunnel.
Twilio POSTs inbound SMS to `https://overwatcher.ftdalpha.com/sms/inbound`.

## Key Paths

| What | Path |
|------|------|
| Project root | `/home/bookworm/code/ai-overwatcher/` |
| Source code | `/home/bookworm/code/ai-overwatcher/src/overwatcher/` |
| Python venv | `/home/bookworm/.pyenv/versions/overwatcher/` |
| Env file | `/home/bookworm/code/ai-overwatcher/.env` |
| SQLite database | `/home/bookworm/code/ai-overwatcher/data/state.db` |
| Google SA key | `/home/bookworm/code/ai-overwatcher/resources/overwatcher-*.json` |
| API service file | `~/.config/systemd/user/overwatcher_api.service` |
| Tunnel service file | `~/.config/systemd/user/overwatcher_tunnel.service` |
| Tunnel config | `~/.cloudflared/overwatcher.yml` |

## Environment Variables (`.env`)

```
# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+17076226891
USER_PHONE=+14083935816

# Timezone
USER_TZ=America/Los_Angeles

# LLM providers (at least one required)
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GEMINI_API_KEY=...
MINIMAX_API_KEY=...

# Model selection
LLM_FAST_MODEL=minimax/MiniMax-M2.5
LLM_FAST_FALLBACKS=anthropic/claude-haiku-4-5,gemini/gemini-3-flash-preview,openai/gpt-5.4-mini
LLM_QUALITY_MODEL=minimax/MiniMax-M2.5
LLM_QUALITY_FALLBACKS=anthropic/claude-sonnet-4-5,openai/gpt-5.4,gemini/gemini-3.1-pro-preview,anthropic/claude-opus-4-6

# Google Sheets (best-effort logging)
GOOGLE_SHEETS_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/home/bookworm/code/ai-overwatcher/resources/overwatcher-289703-c1fdbd175e78.json

# Storage
DATABASE_URL=/home/bookworm/code/ai-overwatcher/data/state.db

# Web
PUBLIC_WEBHOOK_BASE_URL=https://overwatcher.ftdalpha.com
HOST=127.0.0.1
PORT=8123

# Logging
LOG_LEVEL=INFO
```

## Important Configuration

**Twilio webhook URL:**
- Set in the Twilio console → Phone Numbers → Active Numbers → `+17076226891`
- Webhook URL: `https://overwatcher.ftdalpha.com/sms/inbound` (HTTP POST)
- Signature validation uses `PUBLIC_WEBHOOK_BASE_URL` from `.env`

**Google Service Account JSON:**
- The `.env.example` has a macOS path (`/Users/shadowclone/...`). Production must point to the server path.
- See `docs/google-service-account-setup.md` for setup instructions.

**Tunnel config** (`~/.cloudflared/overwatcher.yml`):
- Must use `127.0.0.1` not `localhost` (avoids IPv6 resolution issues with cloudflared)

**Scheduled jobs** (APScheduler, configured in `src/overwatcher/scheduler.py`):
- 09:00 daily — morning prompt ("What are your top 1-3 items?")
- 21:00 daily — evening reflection (references morning plan)
- Friday 17:00 — weekly summary via LLM
- 12:00 daily — heartbeat (internal, no SMS sent)
- All times in `USER_TZ` (America/Los_Angeles)

---

## First-Time Setup

### 1. Create the Cloudflare Tunnel config

```bash
cat > ~/.cloudflared/overwatcher.yml << 'EOF'
tunnel: f8c9ee81-91ce-4535-bb7b-97f835dc7690
credentials-file: /home/bookworm/.cloudflared/f8c9ee81-91ce-4535-bb7b-97f835dc7690.json

ingress:
  - hostname: overwatcher.ftdalpha.com
    service: http://127.0.0.1:8123
  - service: http_status:404
EOF
```

If the tunnel doesn't exist yet:
```bash
cloudflared tunnel create overwatcher
cloudflared tunnel route dns overwatcher overwatcher.ftdalpha.com
```

### 2. Create systemd service files

**API service:**
```bash
cat > ~/.config/systemd/user/overwatcher_api.service << 'EOF'
[Unit]
Description=Overwatcher API (FastAPI/uvicorn)
After=network.target

[Service]
Type=simple
ExecStart=/home/bookworm/.pyenv/versions/overwatcher/bin/uvicorn overwatcher.main:app --host 127.0.0.1 --port 8123
WorkingDirectory=/home/bookworm/code/ai-overwatcher
EnvironmentFile=/home/bookworm/code/ai-overwatcher/.env
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
```

**Tunnel service:**
```bash
cat > ~/.config/systemd/user/overwatcher_tunnel.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel (overwatcher)
After=overwatcher_api.service

[Service]
Type=simple
ExecStart=cloudflared tunnel --config /home/bookworm/.cloudflared/overwatcher.yml run
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF
```

### 3. Install dependencies

```bash
pyenv activate overwatcher
uv pip install -e ".[dev]"
```

### 4. Verify `.env`

Fix the Google SA path (currently points to macOS):
```bash
# Copy the service account JSON to the server if needed, then update .env:
# GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/home/bookworm/code/ai-overwatcher/resources/overwatcher-289703-c1fdbd175e78.json
```

Set the real public URL:
```bash
# PUBLIC_WEBHOOK_BASE_URL=https://overwatcher.ftdalpha.com
```

### 5. Create data directory and initialize DB

```bash
mkdir -p /home/bookworm/code/ai-overwatcher/data
```

The database is auto-created on first startup via `SQLModel.metadata.create_all()`.

### 6. Enable and start services

```bash
systemctl --user daemon-reload
systemctl --user enable overwatcher_api overwatcher_tunnel
systemctl --user start overwatcher_api overwatcher_tunnel
```

### 7. Configure Twilio webhook

In the Twilio console, set the webhook for `+17076226891` to:
```
https://overwatcher.ftdalpha.com/sms/inbound  (HTTP POST)
```

---

## Redeploying After Code Changes

### Code changes only

```bash
systemctl --user restart overwatcher_api.service
systemctl --user status overwatcher_api.service
```

No build step needed — uvicorn reloads the app on restart.

### If you changed Python dependencies

```bash
pyenv activate overwatcher
uv pip install -e ".[dev]"
systemctl --user restart overwatcher_api.service
```

### If you changed a service file

```bash
systemctl --user daemon-reload
systemctl --user restart overwatcher_api.service overwatcher_tunnel.service
```

---

## Service Management

### Check status

```bash
# Both at once
systemctl --user status overwatcher_api overwatcher_tunnel

# Quick check
systemctl --user is-active overwatcher_api overwatcher_tunnel
```

### View logs

```bash
# API logs (live)
journalctl --user -u overwatcher_api -f

# Tunnel logs
journalctl --user -u overwatcher_tunnel -f

# Last 50 lines
journalctl --user -u overwatcher_api -n 50
```

### Stop everything

```bash
systemctl --user stop overwatcher_tunnel overwatcher_api
```

### Enable/disable on boot

```bash
# Disable
systemctl --user disable overwatcher_api overwatcher_tunnel

# Enable
systemctl --user enable overwatcher_api overwatcher_tunnel
```

---

## Health Checks

```bash
# Local health endpoint
curl -s http://127.0.0.1:8123/healthz

# Public URL
curl -s -o /dev/null -w "%{http_code}" https://overwatcher.ftdalpha.com/healthz
```

---

## Database

- **Engine:** SQLite (`data/state.db`)
- **ORM:** SQLModel (SQLAlchemy + Pydantic)
- **Tables:** `messages`, `timers`, `day_state`, `apscheduler_jobs`
- **Schema creation:** Auto-created on app startup via `SQLModel.metadata.create_all(engine)`
- **No migration system** — schema changes require manual ALTER TABLE or recreating the DB
- **Backup:** `cp data/state.db data/state.db.bak`

---

## Troubleshooting

### Bad Gateway (502)

1. **Check services are running:**
   ```bash
   systemctl --user is-active overwatcher_api overwatcher_tunnel
   ```

2. **Check port is listening:**
   ```bash
   ss -tlnp | grep 8123
   ```

3. **Check tunnel logs:**
   ```bash
   journalctl --user -u overwatcher_tunnel -n 20 --no-pager
   ```
   - `dial tcp [::1]:8123: connection refused` → use `127.0.0.1` not `localhost` in tunnel config

### SMS not arriving

1. **Check Twilio webhook URL** in the console matches `https://overwatcher.ftdalpha.com/sms/inbound`
2. **Check API logs** for inbound requests:
   ```bash
   journalctl --user -u overwatcher_api -n 50 --no-pager | grep inbound
   ```
3. **Check signature validation** — `PUBLIC_WEBHOOK_BASE_URL` in `.env` must exactly match the Twilio webhook URL base

### LLM failures

```bash
journalctl --user -u overwatcher_api -f
```

The app has a multi-provider fallback chain. If all providers fail, it falls back to heuristic classification and template responses. Check API key validity with:
```bash
pyenv activate overwatcher
python scripts/probe_llm.py
```

### Scheduled jobs not firing

APScheduler jobs are persisted in SQLite (`apscheduler_jobs` table). If jobs are missing after a restart:
```bash
journalctl --user -u overwatcher_api -n 30 --no-pager | grep -i scheduler
```

Jobs register with `replace_existing=True` on every startup, so a restart should fix stale state.

### Google Sheets logging broken

Sheets logging is best-effort — failures are logged but don't affect SMS delivery. Common causes:
- Service account JSON path wrong (check `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`)
- Service account not shared on the target sheet
- Token expired (shouldn't happen with service accounts)

---

## External Dependencies

| Service | What it provides | Failure impact |
|---------|-----------------|----------------|
| Twilio | SMS send/receive | No SMS; app still runs, jobs still fire |
| LLM providers | Intent classification, reply generation | Falls back to heuristic classifier + template replies |
| Google Sheets | Append-only message log | Logging stops; all other functionality unaffected |
| Cloudflare Tunnel | Public HTTPS webhook ingress | Inbound SMS can't reach app; outbound scheduled jobs still fire |
