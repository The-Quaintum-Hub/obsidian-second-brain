"""Tests for note_generator module."""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from utils.jsonl_parser import SessionData
from utils.note_generator import generate_session_note, NoteResult


def _make_session(
    session_id: str = "abcd1234efgh5678",
    project: str = "terranova-platform",
    cwd: str = "/home/etienne/terranova-platform",
    user_messages: list[str] | None = None,
    files_edited: list[str] | None = None,
    classification: str = "minor",
) -> SessionData:
    s = SessionData()
    s.session_id = session_id
    s.project = project
    s.cwd = cwd
    s.version = "1.0.0"
    s.start_time = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    s.end_time   = datetime(2024, 3, 15, 11, 0, 0, tzinfo=timezone.utc)
    s.duration_min = 30
    s.user_messages = user_messages or ["Can you help me fix the authentication bug?"]
    s.user_message_count = len(s.user_messages)
    s.files_edited = files_edited or []
    s.files_touched = list(s.files_edited)
    s.assistant_text = ["Sure, let me look at the code.", "I've fixed the bug."]
    s.tools_used = ["Read", "Edit"]
    s.classification = classification
    return s


def _make_vault(tmp: str) -> Path:
    vault = Path(tmp) / "vault"
    for d in ("journal", "concepts", "entities", "projects", "decisions",
              "_meta", "synthesis", "references"):
        (vault / d).mkdir(parents=True, exist_ok=True)
    return vault


# ---------------------------------------------------------------------------
# Test 1: metadata-only note (no enrichment)
# ---------------------------------------------------------------------------

def test_metadata_only_note():
    """Session with no enrichment → needs_enrichment: true, title from user message."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(tmp)
        session = _make_session()

        result = generate_session_note(session, vault, enrichment=None)

        assert isinstance(result, NoteResult)

        # Path structure
        assert result.note_path.startswith("journal/2024/03/15/")
        assert "session-abcd1234" in result.note_path
        assert result.note_path.endswith(".md")

        # pages_created contains the note path
        assert result.note_path in result.pages_created

        # Frontmatter flags
        assert "needs_enrichment: true" in result.content

        # Title derived from first user message
        assert "authentication bug" in result.content.lower() or \
               "Can you help" in result.content

        # Project and classification present
        assert "project: terranova-platform" in result.content
        assert "classification: minor" in result.content

        # No enrichment → no decisions section
        assert "## Decisions" not in result.content


# ---------------------------------------------------------------------------
# Test 2: enriched note with cross-links
# ---------------------------------------------------------------------------

def test_enriched_note_with_crosslinks():
    """Session with enrichment + a concept page in vault → [[concepts/...]] appears."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(tmp)

        # Create a concept page that the enrichment will reference
        concept_page = vault / "concepts" / "authentication.md"
        concept_page.write_text("# Authentication\nSome notes about auth.")

        session = _make_session(
            user_messages=[
                "Fix the authentication bug in the login flow",
                "Now update the session management",
            ],
            files_edited=["/home/etienne/terranova-platform/auth.ts"],
        )

        enrichment = {
            "title": "Fix authentication and session management",
            "summary": "Resolved a JWT validation bug and improved session handling.",
            "tags": ["auth", "bug-fix"],
            "decisions": ["Use httpOnly cookies for tokens", "JWT expiry set to 1h"],
            "concepts": ["authentication", "session management"],
        }

        result = generate_session_note(session, vault, enrichment=enrichment)

        # needs_enrichment false
        assert "needs_enrichment: false" in result.content

        # Title from enrichment
        assert "Fix authentication and session management" in result.content

        # Summary present
        assert "JWT validation bug" in result.content

        # Decisions listed
        assert "## Decisions" in result.content
        assert "httpOnly cookies" in result.content
        assert "JWT expiry" in result.content

        # Cross-link to concepts/authentication
        assert "[[concepts/authentication]]" in result.content

        # Tags from enrichment appear in frontmatter
        assert "auth" in result.content
        assert "bug-fix" in result.content

        # Files section shows relative path
        assert "auth.ts" in result.content
