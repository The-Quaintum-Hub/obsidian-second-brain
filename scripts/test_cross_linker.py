"""Tests for utils/cross_linker.py"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make sure the scripts directory is on sys.path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "utils"))

from utils.cross_linker import run_cross_linker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def temp_vault(tmp_path: Path) -> Path:
    """Create a minimal vault structure for testing."""
    # concepts/ dir with one concept page
    concepts_dir = tmp_path / "concepts"
    concepts_dir.mkdir(parents=True)
    (concepts_dir / "docker-compose.md").write_text(
        "---\ntitle: docker-compose\n---\n\n# docker-compose\n\nOrchestration tool.\n",
        encoding="utf-8",
    )

    # journal/ dir with a session note that mentions docker-compose in plain text
    journal_dir = tmp_path / "journal" / "2024" / "01" / "01"
    journal_dir.mkdir(parents=True)
    session_note = journal_dir / "session-abc12345.md"
    session_note.write_text(
        "---\ntitle: Deploy with docker-compose\nproject: myproject\n---\n\n"
        "# Deploy with docker-compose\n\n"
        "Today I used docker-compose to spin up the services.\n",
        encoding="utf-8",
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_adds_wikilinks(temp_vault: Path) -> None:
    """
    After running the cross-linker the session note should contain a wikilink
    to concepts/docker-compose wherever the plain text 'docker-compose' appeared,
    and stats['links_added'] should be >= 1.
    """
    stats = run_cross_linker(temp_vault)

    # Check stats
    assert stats["links_added"] >= 1, (
        f"Expected at least 1 link added, got {stats['links_added']}"
    )
    assert stats["files_modified"] >= 1, (
        f"Expected at least 1 file modified, got {stats['files_modified']}"
    )

    # Check the session note was updated
    session_note = (
        temp_vault / "journal" / "2024" / "01" / "01" / "session-abc12345.md"
    )
    content = session_note.read_text(encoding="utf-8")

    assert "[[concepts/docker-compose" in content, (
        f"Expected [[concepts/docker-compose wikilink in note body.\n"
        f"Actual content:\n{content}"
    )


def test_no_self_link(temp_vault: Path) -> None:
    """The concept page itself should not gain a self-link."""
    run_cross_linker(temp_vault)
    concept = (temp_vault / "concepts" / "docker-compose.md").read_text(encoding="utf-8")
    # Count occurrences of [[concepts/docker-compose in the concept file
    assert "[[concepts/docker-compose" not in concept, (
        "Concept page should not self-link"
    )


def test_no_duplicate_links(temp_vault: Path) -> None:
    """Running the linker twice should not double-link the same term."""
    run_cross_linker(temp_vault)
    stats2 = run_cross_linker(temp_vault)
    assert stats2["links_added"] == 0, (
        f"Second run should add 0 links, got {stats2['links_added']}"
    )


def test_returns_stats_keys(temp_vault: Path) -> None:
    """run_cross_linker should always return the expected stat keys."""
    stats = run_cross_linker(temp_vault)
    for key in ("files_scanned", "links_added", "files_modified"):
        assert key in stats, f"Missing key: {key}"
