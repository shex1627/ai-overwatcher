# Google Service Account Setup

How to create the service account JSON that `gspread` uses to append rows to the Overwatcher log sheet.

Env vars this produces (see [technical-implementation.md](technical-implementation.md#L535-L536)):

```
GOOGLE_SHEETS_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/data/service-account.json
```

---

## 1. Create a Google Cloud project

1. Go to https://console.cloud.google.com/
2. Top bar → project dropdown → **New Project**
3. Name it `overwatcher` (or anything). No org needed for personal use.
4. Select the project once created.

## 2. Enable the APIs

In the project, go to **APIs & Services → Library** and enable:

- **Google Sheets API** (required)
- **Google Drive API** (only if you want the app to create/list sheets; for MVP append-only to an existing sheet, you can skip this — matches the scope-minimization note in [technical-implementation.md:502](technical-implementation.md#L502))

## 3. Create the service account

1. **APIs & Services → Credentials → Create Credentials → Service account**
2. Name: `overwatcher-writer`. Skip the optional role grants (we authorize per-sheet, not project-wide).
3. Click **Done**.

## 4. Generate the JSON key

1. On the Credentials page, click the service account you just made.
2. **Keys** tab → **Add Key → Create new key → JSON → Create**.
3. A file like `overwatcher-writer-abc123.json` downloads. **This is the only copy** — Google does not store it.
4. Rename to `service-account.json` and move to your deployment's data dir (matches `GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/data/service-account.json`).

## 5. Share the Sheet with the service account

The service account is its own identity — it cannot see your Sheets until you share.

1. Open the JSON; copy the `client_email` field (looks like `overwatcher-writer@<project>.iam.gserviceaccount.com`).
2. Open your target Google Sheet.
3. **Share** → paste that email → role **Editor** → uncheck "Notify people" → **Share**.
4. Copy the sheet ID from the URL: `https://docs.google.com/spreadsheets/d/<THIS_PART>/edit` → that's `GOOGLE_SHEETS_ID`.

## 6. Create the log tab

Add a sheet tab with header row matching [technical-implementation.md:144](technical-implementation.md#L144):

```
timestamp | direction | type | mode | raw_text | parsed | timer_id
```

## 7. Wire it up

`.env`:

```
GOOGLE_SHEETS_ID=1AbCdEf...
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/data/service-account.json
```

Minimal `sheets.py` smoke test:

```python
import gspread
gc = gspread.service_account(filename="/data/service-account.json")
sh = gc.open_by_key("<GOOGLE_SHEETS_ID>")
sh.sheet1.append_row(["2026-04-13T09:00", "out", "morning", "bookend", "hi", "", ""])
```

If this appends a row, you're done.

---

## Security notes

- **Do not commit `service-account.json`.** Add to `.gitignore`.
- Key grants append access to any sheet shared with that email. Share only the log sheet.
- Rotate: Credentials → service account → Keys → delete old, create new.
- If leaked: delete the key immediately in the console; the JSON becomes inert.
- For deploy: mount as a secret/volume at `/data/service-account.json` rather than baking into the image.

## Common errors

| Error | Cause |
|---|---|
| `APIError: PERMISSION_DENIED` | Sheet not shared with `client_email`, or Sheets API not enabled. |
| `SpreadsheetNotFound` | Wrong `GOOGLE_SHEETS_ID`, or sheet not shared. |
| `invalid_grant` | System clock skew, or JSON file corrupted/partially copied. |
| `insufficient authentication scopes` | Using a Drive-scoped call but Drive API not enabled; MVP only needs Sheets scope. |
