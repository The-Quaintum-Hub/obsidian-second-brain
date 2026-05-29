"""Validate minimal frontmatter on curated notes. Flags orphans so they don't
become invisible. Exit 1 if any errors (usable as a guard)."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.config import get_vault_path
from utils.frontmatter import parse_frontmatter
from utils.vault_router import FOLDER_BY_TYPE

REQUIRED = ("type", "title", "project", "status", "updated")
CURATED = ("projects", "decisions", "patterns", "references", "concepts")

def validate_note(rel_path: str, fm: dict) -> list[str]:
    errors: list[str] = []
    missing = [k for k in REQUIRED if not fm.get(k)]
    if missing:
        errors.append(f"{rel_path}: missing frontmatter: {', '.join(missing)}")
    t = fm.get("type")
    if t and t not in FOLDER_BY_TYPE:
        errors.append(f"{rel_path}: invalid type {t!r}")
    return errors

def main() -> None:
    vault = get_vault_path()
    errors: list[str] = []
    for folder in CURATED:
        d = vault / folder
        if not d.is_dir():
            continue
        for md in d.rglob("*.md"):
            text = md.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(text)
            errors += validate_note(str(md.relative_to(vault)), fm)
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("All curated notes have valid frontmatter.")

if __name__ == "__main__":
    main()
