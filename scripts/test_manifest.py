"""Tests for manifest module."""
import json
import tempfile
from pathlib import Path

import pytest

from utils.manifest import Manifest


def test_load_and_record():
    with tempfile.TemporaryDirectory() as tmp:
        vault_path = Path(tmp) / "vault"
        vault_path.mkdir()

        # Fresh manifest (no file yet)
        m = Manifest(vault_path)

        assert m.is_processed("session-abc") is False
        assert m.stats["total_sources_ingested"] == 0

        # Record a session
        m.record_session(
            session_id="session-abc",
            project="terranova-platform",
            source_path="/home/etienne/.claude/sessions/session-abc.jsonl",
            pages_created=["projects/terranova-platform/2024-01-15.md"],
            pages_updated=["projects/terranova-platform/index.md"],
        )
        m.save()

        # Reload from disk and verify persistence
        m2 = Manifest(vault_path)

        assert m2.is_processed("session-abc") is True
        assert m2.is_processed("session-xyz") is False
        assert m2.stats["total_sources_ingested"] == 1
        assert "terranova-platform" in m2._data["projects"]
        assert m2._data["projects"]["terranova-platform"]["conversations_ingested"] == 1
        assert m2._data["last_updated"] is not None

        # Verify manifest file structure on disk
        manifest_file = vault_path / "_meta" / ".manifest.json"
        assert manifest_file.exists()
        raw = json.loads(manifest_file.read_text())
        assert raw["version"] == 1
        assert "session-abc" in raw["sources"]
        source = raw["sources"]["session-abc"]
        assert source["source_type"] == "claude_session"
        assert source["project"] == "terranova-platform"
        assert source["pages_created"] == ["projects/terranova-platform/2024-01-15.md"]
        assert source["pages_updated"] == ["projects/terranova-platform/index.md"]
