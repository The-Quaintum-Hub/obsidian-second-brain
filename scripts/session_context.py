"""session_context.py — SessionStart hook for Claude Code.

Prints the contents of the vault's hot.md (active-projects dashboard) to stdout
so Claude has continuity at session start. Exits silently if the vault or hot.md
is unreachable.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from utils.config import get_vault_path
except Exception:
    sys.exit(0)

def main() -> None:
    try:
        vault = get_vault_path()
        hot = vault / "hot.md"
        if not hot.is_file():
            sys.exit(0)
        text = hot.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        sys.exit(0)
    if not text or "_Sin proyectos activos._" in text:
        sys.exit(0)
    # Strip frontmatter for a cleaner injection
    if text.startswith("---"):
        parts = text.split("---", 2)
        text = parts[2].strip() if len(parts) == 3 else text
    print(text)

if __name__ == "__main__":
    main()
