from pathlib import Path
from generate_hot import build_hot

def _write(p: Path, fm: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(fm, encoding="utf-8")

def test_hot_only_active_projects_with_resume(tmp_path: Path):
    _write(tmp_path / "projects" / "altyro.md",
           '---\ntype: project\ntitle: Sol Altyro\nproject: altyro\nstatus: active\nupdated: 2026-05-28\nresume: "guíame los pasos de Meta"\n---\n')
    _write(tmp_path / "projects" / "old.md",
           "---\ntype: project\ntitle: Old thing\nproject: x\nstatus: done\nupdated: 2026-01-01\n---\n")
    out = build_hot(tmp_path)
    assert "Sol Altyro" in out
    assert "guíame los pasos de Meta" in out
    assert "Old thing" not in out      # done excluded

def test_hot_handles_no_active_projects(tmp_path: Path):
    (tmp_path / "projects").mkdir()
    out = build_hot(tmp_path)
    assert "Sin proyectos activos" in out
