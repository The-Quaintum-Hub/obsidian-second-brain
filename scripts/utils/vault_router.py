"""Deterministic note-type -> folder routing. The 'where to save' is a metadata
lookup, never the model's in-the-moment judgment."""
from __future__ import annotations

FOLDER_BY_TYPE = {
    "project": "projects",
    "decision": "decisions",
    "pattern": "patterns",
    "reference": "references",
    "concept": "concepts",
    "journal": "journal",
}

def folder_for_type(note_type: str) -> str:
    try:
        return FOLDER_BY_TYPE[note_type]
    except KeyError:
        raise ValueError(
            f"Unknown note type: {note_type!r}. Valid: {sorted(FOLDER_BY_TYPE)}"
        )
