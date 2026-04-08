"""
session_context.py — SessionStart hook for Claude Code.

Outputs a brief Second Brain context block to stdout at the start of each
session.  Called via the PreToolUse / SessionStart hook in settings.json.

Exits silently (no output, exit 0) if the vault is unreachable or there is
nothing useful to show.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Allow running as a script from any directory
sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.config import get_vault_path
except Exception:
    sys.exit(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vault_path_safe() -> Path | None:
    """Return vault path or None if not configured / unreachable."""
    try:
        vp = get_vault_path()
        if vp.is_dir():
            return vp
    except Exception:
        pass
    return None


def _current_project() -> str:
    """Derive project name from PWD (last path component)."""
    cwd = os.environ.get("PWD", os.getcwd())
    return Path(cwd).name or "home"


_FM_DATE_RE = re.compile(r"^date:\s*(.+)$", re.MULTILINE)
_FM_TITLE_RE = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)


def _extract_fm(text: str) -> tuple[str, str]:
    """Return (title, date) extracted from YAML frontmatter, or ('', '')."""
    title = date = ""
    m = _FM_TITLE_RE.search(text[:600])
    if m:
        title = m.group(1).strip()
    m = _FM_DATE_RE.search(text[:600])
    if m:
        date = m.group(1).strip()
    return title, date


def _recent_sessions(vault_path: Path, project: str, limit: int = 3) -> list[str]:
    """
    Return formatted lines for the most recent session notes matching *project*.
    Each line: "  - YYYY-MM-DD | <title>"
    """
    journal_dir = vault_path / "journal"
    if not journal_dir.is_dir():
        return []

    entries: list[tuple[str, str, str]] = []  # (date, title, path)
    for md in journal_dir.rglob("session-*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if f"project: {project}" not in text:
            continue
        title, date = _extract_fm(text)
        if not date:
            # Fall back to file mtime
            try:
                mtime = md.stat().st_mtime
                date = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
            except OSError:
                date = "0000-00-00"
        if not title:
            title = md.stem
        entries.append((date, title, str(md.relative_to(vault_path).with_suffix(""))))

    # Sort by date descending, take top N
    entries.sort(key=lambda x: x[0], reverse=True)
    lines = []
    for date, title, _ in entries[:limit]:
        lines.append(f"  - {date} | {title}")
    return lines


def _recent_decisions(vault_path: Path, limit: int = 3) -> list[str]:
    """
    Return formatted lines for the most recent decisions (by filename sort).
    Each line: "  - <stem>"
    """
    decisions_dir = vault_path / "decisions"
    if not decisions_dir.is_dir():
        return []

    mds = sorted(decisions_dir.rglob("*.md"), key=lambda p: p.name, reverse=True)
    lines = []
    for md in mds[:limit]:
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        title, _ = _extract_fm(text)
        label = title or md.stem
        lines.append(f"  - {label}")
    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    vault_path = _vault_path_safe()
    if vault_path is None:
        sys.exit(0)

    project = _current_project()
    session_lines = _recent_sessions(vault_path, project)
    decision_lines = _recent_decisions(vault_path)

    # Nothing useful to show
    if not session_lines and not decision_lines:
        sys.exit(0)

    parts: list[str] = [f"[Second Brain Context - {project}]"]

    if session_lines:
        parts.append("Recent sessions:")
        parts.extend(session_lines)

    if decision_lines:
        parts.append("Recent decisions:")
        parts.extend(decision_lines)

    print("\n".join(parts))


if __name__ == "__main__":
    main()
