"""Google Sheets append-only log. Best-effort; Sheets is cosmetic, not on the hot path."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from overwatcher.config import get_settings

log = logging.getLogger(__name__)

_HEADERS = [
    "timestamp",
    "direction",
    "type",
    "mode",
    "raw_text",
    "parsed",
    "timer_id",
    "request_id",
]
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@lru_cache(maxsize=1)
def _worksheet() -> Optional[gspread.Worksheet]:
    s = get_settings()
    path = Path(s.google_service_account_json_path)
    if not s.google_sheets_id or not path.exists():
        log.warning("sheets_disabled", extra={"reason": "missing_config"})
        return None
    creds = Credentials.from_service_account_file(str(path), scopes=_SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(s.google_sheets_id)
    ws = sh.sheet1
    existing = ws.row_values(1)
    if existing != _HEADERS:
        ws.update("A1", [_HEADERS])
    return ws


def append_row(
    *,
    timestamp: str,
    direction: str,
    type_: str,
    mode: Optional[str],
    raw_text: Optional[str],
    parsed: Optional[str],
    timer_id: Optional[int],
    request_id: Optional[str],
) -> None:
    ws = _worksheet()
    if ws is None:
        return
    ws.append_row(
        [
            timestamp,
            direction,
            type_,
            mode or "",
            raw_text or "",
            parsed or "",
            str(timer_id) if timer_id else "",
            request_id or "",
        ],
        value_input_option="RAW",
    )
