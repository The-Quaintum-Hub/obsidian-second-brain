from pathlib import Path
from generate_index import build_index

def _write(p: Path, fm: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fm, encoding="utf-8")

def test_index_lists_curated_excludes_journal(tmp_path: Path):
    _write(tmp_path / "patterns" / "oc.md",
           "---\ntype: pattern\ntitle: OC gotchas\nproject: openclaw\nstatus: active\nupdated: 2026-05-28\n---\n")
    _write(tmp_path / "references" / "cf.md",
           "---\ntype: reference\ntitle: CF token\nproject: infra\nstatus: active\nupdated: 2026-05-28\n---\n")
    _write(tmp_path / "journal" / "2026" / "s.md",
           "---\ntype: journal\ntitle: noise\nproject: x\nstatus: done\nupdated: 2026-05-28\n---\n")
    out = build_index(tmp_path)
    assert "OC gotchas" in out
    assert "CF token" in out
    assert "noise" not in out          # journal excluded
    assert "## patterns" in out and "## references" in out
