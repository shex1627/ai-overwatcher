"""Load + render prompt .md files. Versioned so log lines can report which prompt produced output."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_PROMPT_DIR = Path(__file__).parent / "prompts"
_VERSION_RE = re.compile(r"^#\s*version:\s*(\d+)", re.MULTILINE)
_TIER_RE = re.compile(r"^#\s*tier:\s*(\w+)", re.MULTILINE)


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    tier: str
    body: str

    def render(self, **kwargs) -> str:
        """Substitute {variables}. Unknown variables raise KeyError at render time, never at load time."""
        return self.body.format(**kwargs)


@lru_cache(maxsize=32)
def load(name: str) -> Prompt:
    path = _PROMPT_DIR / f"{name}.md"
    raw = path.read_text(encoding="utf-8")
    v_match = _VERSION_RE.search(raw)
    t_match = _TIER_RE.search(raw)
    version = int(v_match.group(1)) if v_match else 0
    tier = t_match.group(1) if t_match else "fast"
    # Strip leading header-comment lines so they don't appear in the rendered prompt.
    body = re.sub(r"^(#.*\n)+", "", raw, count=1).lstrip()
    return Prompt(name=name, version=version, tier=tier, body=body)
