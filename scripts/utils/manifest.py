"""Manage .manifest.json for tracking ingested sessions."""
import json
from datetime import datetime, timezone
from pathlib import Path

class Manifest:
    def __init__(self, vault_path: Path):
        self.path = vault_path / "_meta" / ".manifest.json"
        self._data = json.loads(self.path.read_text()) if self.path.exists() else {
            "version": 1, "last_updated": None, "sources": {}, "projects": {},
            "stats": {"total_sources_ingested": 0, "total_pages": 0,
                      "total_projects": 0, "last_full_rebuild": None}}

    @property
    def sources(self): return self._data["sources"]
    @property
    def stats(self): return self._data["stats"]

    def is_processed(self, session_id: str) -> bool:
        return session_id in self._data["sources"]

    def record_session(self, session_id: str, project: str, source_path: str,
                       pages_created: list[str], pages_updated: list[str]):
        now = datetime.now(timezone.utc).isoformat()
        self._data["sources"][session_id] = {
            "ingested_at": now, "source_path": source_path,
            "source_type": "claude_session", "project": project,
            "pages_created": pages_created, "pages_updated": pages_updated}
        self._data["stats"]["total_sources_ingested"] = len(self._data["sources"])
        self._data["last_updated"] = now
        if project and project not in self._data["projects"]:
            self._data["projects"][project] = {"conversations_ingested": 0, "last_ingested": None}
        if project:
            self._data["projects"][project]["conversations_ingested"] += 1
            self._data["projects"][project]["last_ingested"] = now

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2) + "\n")
