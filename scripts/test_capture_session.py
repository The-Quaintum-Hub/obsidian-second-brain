"""Tests for capture_session module."""
import json
import tempfile
import time
from pathlib import Path

import pytest

from capture_session import find_latest_session, run_capture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    td: str,
    session_id: str,
    messages: int = 5,
    edit: bool = True,
    project_subdir: str = "-home-etienne-myproject",
) -> Path:
    """
    Create a fake JSONL session file with `messages` user messages and
    optionally an Edit tool call. Returns the path.
    """
    projects_dir = Path(td) / "projects"
    session_dir  = projects_dir / project_subdir
    session_dir.mkdir(parents=True, exist_ok=True)

    events = []
    for i in range(messages):
        ts = f"2024-03-15T10:{i:02d}:00Z"
        events.append({
            "type": "user",
            "timestamp": ts,
            "sessionId": session_id,
            "cwd": "/home/etienne/myproject",
            "version": "1.0.0",
            "gitBranch": "main",
            "message": {"content": f"User message number {i + 1} about the feature"},
        })
        assistant_content: list[dict] = [
            {"type": "text", "text": f"Assistant reply {i + 1}"}
        ]
        if edit and i == 0:
            assistant_content.append({
                "type": "tool_use",
                "name": "Edit",
                "input": {"file_path": "/home/etienne/myproject/main.py"},
            })
        events.append({
            "type": "assistant",
            "timestamp": f"2024-03-15T10:{i:02d}:30Z",
            "message": {"content": assistant_content},
        })

    path = session_dir / f"{session_id}.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return path


def _make_vault(td: str) -> Path:
    """Create a minimal vault with required directories and empty manifest."""
    vault = Path(td) / "vault"
    for d in ("journal", "concepts", "entities", "projects", "decisions",
              "_meta", "synthesis", "references"):
        (vault / d).mkdir(parents=True, exist_ok=True)
    return vault


# ---------------------------------------------------------------------------
# Test 1: find_latest_session
# ---------------------------------------------------------------------------

def test_find_latest():
    """Create 2 fake JSONL files; verify the most recently modified is returned."""
    with tempfile.TemporaryDirectory() as td:
        projects_dir = Path(td) / "projects"

        # First file (older)
        path_a = _make_session(td, "aaaa0001", messages=3)
        time.sleep(0.05)  # ensure mtime difference
        # Second file (newer)
        path_b = _make_session(td, "bbbb0002", messages=3, project_subdir="-home-etienne-other")

        result = find_latest_session(projects_dir)

        assert result is not None
        assert result == path_b


# ---------------------------------------------------------------------------
# Test 2: creates note
# ---------------------------------------------------------------------------

def test_creates_note():
    """5-message session with an Edit → note created in vault, manifest updated."""
    with tempfile.TemporaryDirectory() as td:
        vault  = _make_vault(td)
        jsonl  = _make_session(td, "cccc1111", messages=5, edit=True)

        created = run_capture(jsonl, vault, skip_enrichment=True)

        assert created is True

        # Note file must exist somewhere under journal/
        journal_dir = vault / "journal"
        notes = list(journal_dir.rglob("session-cccc1111.md"))
        assert len(notes) == 1, f"Expected 1 note, found {len(notes)}"

        note_content = notes[0].read_text(encoding="utf-8")
        assert "needs_enrichment: true" in note_content
        assert "project: myproject" in note_content

        # Manifest updated
        from utils.manifest import Manifest
        m = Manifest(vault)
        assert m.is_processed("cccc1111") is True


# ---------------------------------------------------------------------------
# Test 3: skips trivial sessions
# ---------------------------------------------------------------------------

def test_skips_trivial():
    """A 1-message session (trivial) → run_capture returns False, no note created."""
    with tempfile.TemporaryDirectory() as td:
        vault = _make_vault(td)
        jsonl = _make_session(td, "dddd2222", messages=1, edit=False)

        created = run_capture(jsonl, vault, skip_enrichment=True)

        assert created is False

        # No notes should have been written
        notes = list((vault / "journal").rglob("*.md"))
        assert len(notes) == 0


# ---------------------------------------------------------------------------
# Test 4: skips duplicate sessions
# ---------------------------------------------------------------------------

def test_skips_duplicate():
    """Session already recorded in manifest → run_capture returns False."""
    with tempfile.TemporaryDirectory() as td:
        vault = _make_vault(td)
        jsonl = _make_session(td, "eeee3333", messages=5, edit=True)

        # First run — should succeed
        first = run_capture(jsonl, vault, skip_enrichment=True)
        assert first is True

        # Second run — same session, should be skipped
        second = run_capture(jsonl, vault, skip_enrichment=True)
        assert second is False

        # Only one note should exist
        notes = list((vault / "journal").rglob("session-eeee3333.md"))
        assert len(notes) == 1
