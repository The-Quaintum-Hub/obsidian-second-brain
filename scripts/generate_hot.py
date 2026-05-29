"""Autogenerate hot.md — the live dashboard of ACTIVE projects, injected at
SessionStart. This is the continuity bridge. VIEW only — never hand-edit."""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.config import get_vault_path
from utils.frontmatter import parse_frontmatter

def build_hot(vault: Path) -> str:
    d = vault / "projects"
    rows = []
    if d.is_dir():
        for md in sorted(d.rglob("*.md")):
            fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            if fm.get("status") != "active":
                continue
            title = fm.get("title") or md.stem
            rel = md.relative_to(vault).with_suffix("")
            resume = fm.get("resume", "")
            line = f"- [[{rel}|{title}]]"
            if resume:
                line += f' — Resume: "{resume}"'
            rows.append(line)
    out = [
        "---", "title: Hot — proyectos activos", f"generated: {date.today().isoformat()}", "---",
        "", "# Proyectos activos (hot)", "", "> Autogenerado. NO editar a mano.", "",
    ]
    out += rows if rows else ["_Sin proyectos activos._"]
    return "\n".join(out) + "\n"

def main() -> None:
    vault = get_vault_path()
    (vault / "hot.md").write_text(build_hot(vault), encoding="utf-8")
    print("hot.md regenerated.")

if __name__ == "__main__":
    main()
