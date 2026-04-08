"""Parse Claude Code JSONL session files into structured data."""
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

@dataclass
class SessionData:
    session_id: str = ""
    project: str = "home"
    cwd: str = ""
    version: str = ""
    git_branch: str = ""
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_min: int = 0
    user_message_count: int = 0
    files_touched: list[str] = field(default_factory=list)
    files_edited: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    assistant_text: list[str] = field(default_factory=list)
    user_messages: list[str] = field(default_factory=list)
    classification: str = "trivial"

def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def _extract_project(cwd: str) -> str:
    if not cwd:
        return "home"
    parts = Path(cwd).parts
    for i, p in enumerate(parts):
        if p in ("etienne", "home") and i + 1 < len(parts):
            return parts[-1] if len(parts) > i + 2 else parts[i + 1]
    return parts[-1] if parts else "home"

def parse_session(jsonl_path: Path) -> SessionData:
    data = SessionData()
    if "subagents" in jsonl_path.parts or jsonl_path.parent.name == "subagents":
        data.classification = "subagent"
        return data

    timestamps, files_touched_set, files_edited_set, tools_set = [], set(), set(), set()

    for line in jsonl_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")
        if etype in ("progress", "file-history-snapshot", "permission-mode",
                      "system", "attachment", "queue-operation"):
            continue

        ts_str = event.get("timestamp")
        if ts_str:
            try:
                timestamps.append(_parse_ts(ts_str))
            except ValueError:
                pass

        if etype == "user":
            if not data.session_id:
                data.session_id = event.get("sessionId", "")
                data.cwd = event.get("cwd", "")
                data.version = event.get("version", "")
                data.git_branch = event.get("gitBranch", "")
                data.project = _extract_project(data.cwd)
            content = event.get("message", {}).get("content", "")
            if isinstance(content, str) and content.strip():
                data.user_messages.append(content)
                data.user_message_count += 1

        elif etype == "assistant":
            content = event.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    bt = block.get("type")
                    if bt == "text":
                        text = block.get("text", "").strip()
                        if text:
                            data.assistant_text.append(text)
                    elif bt == "tool_use":
                        tool = block.get("name", "")
                        if tool:
                            tools_set.add(tool)
                        fp = block.get("input", {}).get("file_path", "")
                        if fp:
                            files_touched_set.add(fp)
                            if tool in ("Edit", "Write", "NotebookEdit"):
                                files_edited_set.add(fp)

    data.files_touched = sorted(files_touched_set)
    data.files_edited = sorted(files_edited_set)
    data.tools_used = sorted(tools_set)

    if timestamps:
        data.start_time = min(timestamps)
        data.end_time = max(timestamps)
        data.duration_min = max(1, int((data.end_time - data.start_time).total_seconds() / 60))

    if data.user_message_count < 2:
        data.classification = "trivial"
    elif data.user_message_count >= 10 and len(data.files_edited) > 0:
        data.classification = "substantial"
    else:
        data.classification = "minor"

    return data
