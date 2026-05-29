"""Minimal YAML-frontmatter parser (no external deps)."""
from __future__ import annotations
import re

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)

def parse_frontmatter(text: str) -> dict:
    """Parse leading YAML frontmatter into a dict. Returns {} if absent.

    Supports `key: value` and `key: [a, b, c]` (flat lists only).
    """
    m = _FM_RE.match(text)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            fm[key] = [x.strip().strip('"').strip("'") for x in val[1:-1].split(",") if x.strip()]
        else:
            fm[key] = val.strip('"').strip("'")
    return fm
