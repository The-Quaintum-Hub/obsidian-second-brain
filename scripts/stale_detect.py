"""
stale_detect.py — Detect stale and orphan concept/entity pages in the vault.

Usage
-----
    python3 stale_detect.py [--days 30] [--fix]

    --days  Look back this many days when scanning recent sessions (default 30).
    --fix   Add ``stale: true`` to frontmatter of stale pages.

Definitions
-----------
Orphan  — A concept/entity page with NO incoming wikilinks at all.
Stale   — A concept/entity page that has some incoming links but was NOT
          referenced in any recent session (within --days).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_vault_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:\|[^\]]+)?\]\]")
_FM_DATE_RE = re.compile(r"^date:\s*(\S+)", re.MULTILINE)
_FM_STALE_RE = re.compile(r"^stale:\s*\S+\s*$", re.MULTILINE)


def _read_wikilinks(text: str) -> set[str]:
    """Return all wikilink targets (lowercased, without .md) found in *text*."""
    targets: set[str] = set()
    for m in _WIKILINK_RE.finditer(text):
        target = m.group(1).strip().lower()
        # Drop anchors like page#section
        target = target.split("#")[0].strip()
        if target:
            targets.add(target)
    return targets


def _note_date(path: Path) -> date | None:
    """Extract the note date from frontmatter, or None."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:300]
    except OSError:
        return None
    m = _FM_DATE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip().strip('"').strip("'")[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _add_stale_flag(path: Path) -> None:
    """Add or update ``stale: true`` in the frontmatter of *path*."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return

    if _FM_STALE_RE.search(content):
        # Replace existing stale line
        new_content = _FM_STALE_RE.sub("stale: true", content, count=1)
    elif content.startswith("---"):
        # Insert after opening ---
        new_content = content.replace("---\n", "---\nstale: true\n", 1)
    else:
        # No frontmatter — prepend a minimal one
        new_content = "---\nstale: true\n---\n\n" + content

    try:
        path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(f"  Warning: could not write {path}: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run_stale_detect(vault_path: Path, days: int = 30, fix: bool = False) -> dict:
    """
    Scan the vault and report stale/orphan pages.

    Returns:
        {
            "orphans": [str],   # paths relative to vault
            "stale": [str],     # paths relative to vault
            "fixed": int,       # number of files with stale: true added (if --fix)
        }
    """
    cutoff = date.today() - timedelta(days=days)

    # ------------------------------------------------------------------
    # 1. Collect concept/entity candidate pages
    # ------------------------------------------------------------------
    candidate_dirs = ("concepts", "entities")
    candidate_pages: dict[str, Path] = {}  # rel_no_ext_lower -> path

    for dir_name in candidate_dirs:
        src_dir = vault_path / dir_name
        if not src_dir.is_dir():
            continue
        for md in src_dir.rglob("*.md"):
            rel = str(md.relative_to(vault_path).with_suffix(""))
            candidate_pages[rel.lower()] = md
            # Also register stem alone
            candidate_pages[md.stem.lower()] = md

    if not candidate_pages:
        print("No concept/entity pages found.", file=sys.stderr)
        return {"orphans": [], "stale": [], "fixed": 0}

    # ------------------------------------------------------------------
    # 2. Scan ALL notes to build incoming-link and recent-reference sets
    # ------------------------------------------------------------------
    all_incoming: set[str] = set()      # pages that have ANY incoming link
    recent_referenced: set[str] = set() # pages referenced in recent sessions

    journal_dir = vault_path / "journal"

    for md in vault_path.rglob("*.md"):
        parts = md.relative_to(vault_path).parts
        # Skip dot-files and _archives
        if any(p.startswith(".") or p == "_archives" for p in parts):
            continue

        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        links = _read_wikilinks(text)
        all_incoming.update(links)

        # Check if this is a recent session note
        is_journal = parts[0] == "journal" if parts else False
        if is_journal and md.name.startswith("session-"):
            note_date = _note_date(md)
            is_recent = note_date is not None and note_date >= cutoff
            if is_recent:
                recent_referenced.update(links)

    # ------------------------------------------------------------------
    # 3. Classify pages
    # ------------------------------------------------------------------
    # Deduplicate by canonical path
    canonical: dict[Path, str] = {}  # path -> rel_no_ext_lower (canonical)
    for key, path in candidate_pages.items():
        rel = str(path.relative_to(vault_path).with_suffix(""))
        rel_lower = rel.lower()
        if path not in canonical:
            canonical[path] = rel_lower

    orphans: list[str] = []
    stale: list[str] = []

    for path, rel_lower in canonical.items():
        stem_lower = path.stem.lower()
        # Check incoming links (by full rel path or by stem)
        has_incoming = rel_lower in all_incoming or stem_lower in all_incoming
        recently_seen = rel_lower in recent_referenced or stem_lower in recent_referenced

        if not has_incoming:
            orphans.append(str(path.relative_to(vault_path)))
        elif not recently_seen:
            stale.append(str(path.relative_to(vault_path)))

    orphans.sort()
    stale.sort()

    # ------------------------------------------------------------------
    # 4. Optional fix
    # ------------------------------------------------------------------
    fixed = 0
    if fix:
        for rel_path in stale:
            full_path = vault_path / rel_path
            _add_stale_flag(full_path)
            fixed += 1

    return {"orphans": orphans, "stale": stale, "fixed": fixed}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect stale and orphan concept/entity pages in the vault."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        metavar="N",
        help="Look-back window in days for recent sessions (default: 30)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Add stale: true to frontmatter of stale pages",
    )
    args = parser.parse_args()

    try:
        vault_path = get_vault_path()
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not vault_path.is_dir():
        print(f"Error: vault path not found: {vault_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning vault: {vault_path}", file=sys.stderr)
    print(f"Look-back window: {args.days} days", file=sys.stderr)
    if args.fix:
        print("Fix mode: ON (will add stale: true to frontmatter)", file=sys.stderr)
    print("", file=sys.stderr)

    result = run_stale_detect(vault_path, days=args.days, fix=args.fix)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    orphans = result["orphans"]
    stale = result["stale"]

    if orphans:
        print(f"ORPHANS ({len(orphans)} — no incoming links at all):")
        for p in orphans:
            print(f"  {p}")
        print()
    else:
        print("No orphan pages found.")
        print()

    if stale:
        print(f"STALE ({len(stale)} — not referenced in last {args.days} days):")
        for p in stale:
            print(f"  {p}")
        if args.fix:
            print(f"\nFixed {result['fixed']} pages (added stale: true).")
        print()
    else:
        print(f"No stale pages found (look-back: {args.days} days).")
        print()


if __name__ == "__main__":
    main()
