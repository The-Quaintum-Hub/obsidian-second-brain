"""
weekly_digest.py — Generate a weekly digest note from session notes.

Usage
-----
    python3 weekly_digest.py [--week YYYY-WNN]

    --week  ISO week string, e.g. "2024-W03".
            Defaults to the current ISO week.

The digest is written to:
    <vault>/journal/<YYYY>/WNN-digest.md
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_vault_path


# ---------------------------------------------------------------------------
# Week helpers
# ---------------------------------------------------------------------------

def _parse_week_arg(week_str: str) -> tuple[date, date, str, str]:
    """
    Parse a YYYY-WNN string and return (week_start, week_end, year_str, wnn_str).
    """
    m = re.fullmatch(r"(\d{4})-W(\d{2})", week_str)
    if not m:
        raise ValueError(f"Invalid --week format '{week_str}'. Use YYYY-WNN (e.g. 2024-W03).")
    year = int(m.group(1))
    week_num = int(m.group(2))
    # ISO week Monday
    week_start = date.fromisocalendar(year, week_num, 1)
    week_end = week_start + timedelta(days=6)
    year_str = str(year)
    wnn_str = f"W{week_num:02d}"
    return week_start, week_end, year_str, wnn_str


def _current_week() -> tuple[date, date, str, str]:
    today = date.today()
    iso = today.isocalendar()
    return _parse_week_arg(f"{iso.year}-W{iso.week:02d}")


# ---------------------------------------------------------------------------
# Session note parsing
# ---------------------------------------------------------------------------

_FM_RE = re.compile(
    r"^---\s*\n(.+?)\n---", re.DOTALL | re.MULTILINE
)
_KV_RE = re.compile(r"^(\w+):\s*(.+)$", re.MULTILINE)


def _parse_session_fm(path: Path) -> dict:
    """Extract key-value pairs from YAML frontmatter (flat values only)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = _FM_RE.match(text)
    if not m:
        return {}
    fm_block = m.group(1)
    result: dict = {}
    for km in _KV_RE.finditer(fm_block):
        key = km.group(1)
        val = km.group(2).strip().strip('"').strip("'")
        result[key] = val
    return result


def _session_date(fm: dict, path: Path) -> date | None:
    """Return the session date from frontmatter or filename."""
    raw = fm.get("date", "")
    if raw:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(raw[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
    return None


# ---------------------------------------------------------------------------
# Digest generator
# ---------------------------------------------------------------------------

def _generate_digest(
    vault_path: Path,
    week_start: date,
    week_end: date,
    year_str: str,
    wnn_str: str,
) -> str:
    """
    Scan journal/ for session notes in [week_start, week_end], group by project,
    and return the full digest markdown string.
    """
    journal_dir = vault_path / "journal"
    if not journal_dir.is_dir():
        print(f"Warning: journal/ directory not found in {vault_path}", file=sys.stderr)
        return ""

    # Collect matching sessions
    # structure: project -> list of (date, title, duration_min, rel_path)
    by_project: dict[str, list[tuple[date, str, int, str]]] = defaultdict(list)
    total_sessions = 0
    total_duration = 0

    for md in journal_dir.rglob("session-*.md"):
        fm = _parse_session_fm(md)
        sess_date = _session_date(fm, md)
        if sess_date is None:
            continue
        if not (week_start <= sess_date <= week_end):
            continue
        project = fm.get("project", "unknown")
        title = fm.get("title", md.stem)
        try:
            duration = int(fm.get("duration_min", "0"))
        except ValueError:
            duration = 0
        rel = str(md.relative_to(vault_path).with_suffix(""))
        by_project[project].append((sess_date, title, duration, rel))
        total_sessions += 1
        total_duration += duration

    projects_active = sorted(by_project.keys())
    date_range = f"{week_start.isoformat()} to {week_end.isoformat()}"
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------
    fm_lines = [
        "---",
        f'title: "Weekly Digest {year_str}-{wnn_str}"',
        f"category: journal",
        f"type: digest",
        f"date_range: \"{date_range}\"",
        f"session_count: {total_sessions}",
        f"projects_active: {len(projects_active)}",
        f"total_duration_min: {total_duration}",
        f"date: {now_str}",
        "tags:",
        "  - digest",
        f"  - {year_str}",
        f"  - {wnn_str}",
    ]
    for p in projects_active:
        fm_lines.append(f"  - {p}")
    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------
    body_lines = [
        f"# Weekly Digest {year_str}-{wnn_str}",
        "",
        f"**Period**: {date_range}  ",
        f"**Sessions**: {total_sessions}  ",
        f"**Projects active**: {len(projects_active)}  ",
        f"**Total coding time**: {total_duration} min  ",
        "",
    ]

    if not by_project:
        body_lines.append("_No sessions found for this week._")
    else:
        body_lines.append("## Sessions by Project")
        body_lines.append("")
        for project in projects_active:
            entries = sorted(by_project[project], key=lambda x: x[0])
            proj_duration = sum(e[2] for e in entries)
            body_lines.append(f"### {project}  ({len(entries)} sessions, {proj_duration} min)")
            body_lines.append("")
            for sess_date, title, duration, rel in entries:
                body_lines.append(
                    f"- {sess_date.isoformat()} | [[{rel}|{title}]] — {duration} min"
                )
            body_lines.append("")

    body = "\n".join(body_lines)
    return frontmatter + "\n\n" + body


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a weekly digest note from session notes."
    )
    parser.add_argument(
        "--week",
        default=None,
        metavar="YYYY-WNN",
        help="ISO week string (default: current week)",
    )
    args = parser.parse_args()

    try:
        vault_path = get_vault_path()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.week:
        try:
            week_start, week_end, year_str, wnn_str = _parse_week_arg(args.week)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        week_start, week_end, year_str, wnn_str = _current_week()

    print(
        f"Generating digest for {year_str}-{wnn_str} "
        f"({week_start} to {week_end})...",
        file=sys.stderr,
    )

    content = _generate_digest(vault_path, week_start, week_end, year_str, wnn_str)
    if not content:
        print("Nothing to write.", file=sys.stderr)
        sys.exit(0)

    # Write to journal/<year>/WNN-digest.md
    out_dir = vault_path / "journal" / year_str
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{wnn_str}-digest.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"Digest written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
