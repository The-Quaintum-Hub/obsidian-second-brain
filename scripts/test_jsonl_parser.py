"""Tests for JSONL parser module."""
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from utils.jsonl_parser import parse_session, SessionData


def _write_jsonl(path: Path, events: list[dict]) -> None:
    lines = [json.dumps(e) for e in events]
    path.write_text("\n".join(lines) + "\n")


def test_extracts_session_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        events = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:00:00Z",
                "sessionId": "abc123",
                "cwd": "/home/etienne/terranova-platform",
                "version": "1.2.3",
                "gitBranch": "main",
                "message": {"content": "Can you help me with auth?"},
            },
            {
                "type": "progress",
                "timestamp": "2024-01-15T10:00:05Z",
                "message": "thinking...",
            },
            {
                "type": "assistant",
                "timestamp": "2024-01-15T10:01:00Z",
                "message": {
                    "content": [
                        {"type": "thinking", "thinking": "Let me look at the code."},
                        {"type": "text", "text": "Sure, let me read auth.ts first."},
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": "/home/etienne/terranova-platform/auth.ts"},
                        },
                    ]
                },
            },
            {
                "type": "file-history-snapshot",
                "timestamp": "2024-01-15T10:01:10Z",
            },
            {
                "type": "user",
                "timestamp": "2024-01-15T10:02:00Z",
                "sessionId": "abc123",
                "cwd": "/home/etienne/terranova-platform",
                "version": "1.2.3",
                "gitBranch": "main",
                "message": {"content": "Please edit the file to fix the bug."},
            },
            {
                "type": "assistant",
                "timestamp": "2024-01-15T10:03:00Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "I'll fix the bug now."},
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": "/home/etienne/terranova-platform/auth.ts"},
                        },
                    ]
                },
            },
        ]
        _write_jsonl(p, events)

        data = parse_session(p)

        assert data.session_id == "abc123"
        assert data.project == "terranova-platform"
        assert data.user_message_count == 2
        assert data.duration_min >= 1
        assert "/home/etienne/terranova-platform/auth.ts" in data.files_touched
        assert "/home/etienne/terranova-platform/auth.ts" in data.files_edited
        assert "Read" in data.tools_used
        assert "Edit" in data.tools_used
        assert len(data.assistant_text) == 2
        assert data.classification == "minor"


def test_substantial_classification():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        events = []
        for i in range(12):
            events.append({
                "type": "user",
                "timestamp": f"2024-01-15T10:{i:02d}:00Z",
                "sessionId": "bigone",
                "cwd": "/home/etienne/altyro-platform",
                "version": "1.0.0",
                "gitBranch": "main",
                "message": {"content": f"Message number {i}"},
            })
            events.append({
                "type": "assistant",
                "timestamp": f"2024-01-15T10:{i:02d}:30Z",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": f"/home/etienne/altyro-platform/file{i}.ts"},
                        }
                    ]
                },
            })
        _write_jsonl(p, events)

        data = parse_session(p)

        assert data.user_message_count == 12
        assert len(data.files_edited) > 0
        assert data.classification == "substantial"


def test_trivial_classification():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "session.jsonl"
        events = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:00:00Z",
                "sessionId": "tiny",
                "cwd": "/home/etienne/youtube_automation",
                "version": "1.0.0",
                "gitBranch": "",
                "message": {"content": "What time is it?"},
            },
            {
                "type": "assistant",
                "timestamp": "2024-01-15T10:00:10Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "I don't have access to the current time."}
                    ]
                },
            },
        ]
        _write_jsonl(p, events)

        data = parse_session(p)

        assert data.user_message_count == 1
        assert data.classification == "trivial"


def test_skips_subagent_sessions():
    with tempfile.TemporaryDirectory() as tmp:
        subagents_dir = Path(tmp) / "subagents"
        subagents_dir.mkdir()
        p = subagents_dir / "session.jsonl"
        events = [
            {
                "type": "user",
                "timestamp": "2024-01-15T10:00:00Z",
                "sessionId": "sub001",
                "cwd": "/home/etienne/altyro-platform",
                "version": "1.0.0",
                "gitBranch": "main",
                "message": {"content": "Do something"},
            },
        ]
        _write_jsonl(p, events)

        data = parse_session(p)

        assert data.classification == "subagent"
