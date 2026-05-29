"""Autogenerate index.md (Map of Content) from curated-note frontmatter.
journal/ is excluded. This file is a VIEW — never hand-edit index.md."""
from __future__ import annotations
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.config import get_vault_path
from utils.frontmatter import parse_frontmatter

CURATED = ("projects", "decisions", "patterns", "references", "concepts")

def build_index(vault: Path) -> str:
    out = [
        "---", "title: Second Brain Index", f"generated: {date.today().isoformat()}", "---",
        "", "# Second Brain — Índice", "", "> Autogenerado desde frontmatter. NO editar a mano.", "",
    ]
    for folder in CURATED:
        d = vault / folder
        if not d.is_dir():
            continue
        rows = []
        for md in sorted(d.rglob("*.md")):
            fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            title = fm.get("title") or md.stem
            rel = md.relative_to(vault).with_suffix("")
            meta = " · ".join(x for x in (fm.get("project", ""), fm.get("status", "")) if x)
            line = f"- [[{rel}|{title}]]"
            if meta:
                line += f" — {meta}"
            rows.append(line)
        if rows:
            out.append(f"## {folder}")
            out += rows
            out.append("")
    return "\n".join(out) + "\n"

def main() -> None:
    vault = get_vault_path()
    (vault / "index.md").write_text(build_index(vault), encoding="utf-8")
    print("index.md regenerated.")

if __name__ == "__main__":
    main()
