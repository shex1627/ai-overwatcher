import logging
import re
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AC[0-9a-f]{32}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+"),
]


def _redact(value: str) -> str:
    for pat in _SECRET_PATTERNS:
        value = pat.sub("[REDACTED]", value)
    return value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        for attr in ("raw_text", "parsed_json", "body"):
            val = getattr(record, attr, None)
            if isinstance(val, str):
                setattr(record, attr, _redact(val))
        return True


class JsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record: dict[str, Any], record: logging.LogRecord, message_dict: dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("event", record.name)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    # Reset handlers (so reloads / tests don't double-emit).
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)
