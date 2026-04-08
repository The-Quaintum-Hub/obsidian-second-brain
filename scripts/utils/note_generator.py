"""Generate Obsidian markdown notes from parsed Claude Code sessions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from utils.jsonl_parser import SessionData


@dataclass
class NoteResult:
    note_path: str          # relative path inside vault
    content: str            # full markdown text
    pages_created: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _short_path(file_path: str, cwd: str) -> str:
    """Return file_path relative to cwd when possible."""
    if not cwd:
        return file_path
    try:
        rel = Path(file_path).relative_to(cwd)
        return str(rel)
    except ValueError:
        return file_path


def _safe_title(text: str, max_len: int = 60) -> str:
    """Derive a short title from arbitrary text."""
    # Strip markdown, collapse whitespace
    title = re.sub(r"[#*`\[\]_]", "", text).strip()
    title = re.sub(r"\s+", " ", title)
    if len(title) > max_len:
        title = title[:max_len].rsplit(" ", 1)[0] + "…"
    return title or "Untitled session"


def _collect_vault_pages(vault_path: Path) -> dict[str, str]:
    """
    Walk concept/entity/project/decision dirs and return
    { stem_lowercase: "category/stem" } for every .md file found.
    """
    pages: dict[str, str] = {}
    for cat in ("concepts", "entities", "projects", "decisions"):
        cat_dir = vault_path / cat
        if not cat_dir.is_dir():
            continue
        for md in cat_dir.rglob("*.md"):
            stem = md.stem
            # relative path from vault root, no leading slash
            rel = md.relative_to(vault_path).with_suffix("")
            pages[stem.lower()] = str(rel)
    return pages


def _find_related_sessions(vault_path: Path, project: str, exclude_path: str,
                            limit: int = 5) -> list[str]:
    """Return wikilinks to the last `limit` session notes for the same project."""
    journal_dir = vault_path / "journal"
    if not journal_dir.is_dir():
        return []

    sessions = []
    for md in journal_dir.rglob("session-*.md"):
        rel = str(md.relative_to(vault_path).with_suffix(""))
        if rel == exclude_path:
            continue
        # Check if the note belongs to the same project by reading frontmatter quickly
        try:
            text = md.read_text(encoding="utf-8")
            if f"project: {project}" in text:
                sessions.append((md.stat().st_mtime, rel))
        except OSError:
            pass

    sessions.sort(key=lambda x: x[0], reverse=True)
    return [f"[[{rel}]]" for _, rel in sessions[:limit]]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_session_note(
    session: SessionData,
    vault_path: Path,
    enrichment: Optional[dict] = None,
) -> NoteResult:
    """
    Build a markdown note for *session* and return a NoteResult.

    Parameters
    ----------
    session:     Parsed session data.
    vault_path:  Absolute path to the Obsidian vault root.
    enrichment:  Optional dict with keys: title, summary, tags (list),
                 decisions (list), concepts (list).
                 When None the note is marked needs_enrichment: true.
    """
    # ------------------------------------------------------------------
    # Determine note path
    # ------------------------------------------------------------------
    start: datetime = session.start_time or datetime.now(timezone.utc)
    year  = start.strftime("%Y")
    month = start.strftime("%m")
    day   = start.strftime("%d")
    sid8  = (session.session_id or "unknown")[:8]
    rel_path = f"journal/{year}/{month}/{day}/session-{sid8}.md"

    # ------------------------------------------------------------------
    # Cross-link lookup
    # ------------------------------------------------------------------
    vault_pages = _collect_vault_pages(vault_path)

    # Gather candidate terms from enrichment or fall back to assistant text
    if enrichment and enrichment.get("concepts"):
        concept_terms: list[str] = enrichment["concepts"]
    else:
        # Simple word extraction from assistant text as fallback
        all_text = " ".join(session.assistant_text + session.user_messages)
        concept_terms = list({w for w in re.findall(r"\b[A-Za-z][\w-]{3,}\b", all_text)})

    wikilinks: list[str] = []
    for term in concept_terms:
        key = term.lower()
        if key in vault_pages:
            wikilinks.append(f"[[{vault_pages[key]}]]")
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_wikilinks: list[str] = []
    for wl in wikilinks:
        if wl not in seen:
            seen.add(wl)
            unique_wikilinks.append(wl)

    # Related sessions
    note_path_no_ext = rel_path.replace(".md", "")
    related = _find_related_sessions(vault_path, session.project, note_path_no_ext)

    # ------------------------------------------------------------------
    # Frontmatter
    # ------------------------------------------------------------------
    needs_enrichment = enrichment is None

    if needs_enrichment:
        title = _safe_title(session.user_messages[0]) if session.user_messages else "Untitled session"
        summary = ""
        tags: list[str] = [session.project, "session", f"classification/{session.classification}"]
        decisions: list[str] = []
    else:
        title    = enrichment.get("title") or _safe_title(session.user_messages[0] if session.user_messages else "")
        summary  = enrichment.get("summary", "")
        tags     = list(enrichment.get("tags") or []) + [session.project, "session"]
        decisions = list(enrichment.get("decisions") or [])

    # Deduplicate tags
    tags = list(dict.fromkeys(tags))

    date_str = start.strftime("%Y-%m-%d")
    time_str = start.strftime("%H:%M")

    fm_lines: list[str] = [
        "---",
        f"title: \"{title}\"",
        f"date: {date_str}",
        f"time: \"{time_str}\"",
        f"session_id: {session.session_id}",
        f"project: {session.project}",
        f"classification: {session.classification}",
        f"duration_min: {session.duration_min}",
        f"user_messages: {session.user_message_count}",
        f"files_edited: {len(session.files_edited)}",
        f"needs_enrichment: {'true' if needs_enrichment else 'false'}",
    ]
    if tags:
        fm_lines.append("tags:")
        for t in tags:
            fm_lines.append(f"  - {t}")
    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------
    lines: list[str] = [f"# {title}", ""]

    if summary:
        lines += [summary, ""]

    # Decisions
    if decisions:
        lines.append("## Decisions")
        for d in decisions:
            lines.append(f"- {d}")
        lines.append("")

    # Conversation excerpt
    if session.user_messages:
        lines.append("## Conversation")
        for i, msg in enumerate(session.user_messages[:5]):
            short = _safe_title(msg, max_len=120)
            lines.append(f"{i + 1}. {short}")
        if len(session.user_messages) > 5:
            lines.append(f"_…and {len(session.user_messages) - 5} more messages_")
        lines.append("")

    # Files
    if session.files_edited:
        lines.append("## Files Edited")
        for fp in session.files_edited[:20]:
            lines.append(f"- `{_short_path(fp, session.cwd)}`")
        lines.append("")
    elif session.files_touched:
        lines.append("## Files Touched")
        for fp in session.files_touched[:20]:
            lines.append(f"- `{_short_path(fp, session.cwd)}`")
        lines.append("")

    # Tools
    if session.tools_used:
        lines.append("## Tools Used")
        lines.append(", ".join(f"`{t}`" for t in sorted(session.tools_used)))
        lines.append("")

    # Cross-links
    if unique_wikilinks:
        lines.append("## Related Concepts")
        lines.append(" · ".join(unique_wikilinks))
        lines.append("")

    # Related sessions
    if related:
        lines.append("## Related Sessions")
        lines.append(" · ".join(related))
        lines.append("")

    body = "\n".join(lines)
    content = frontmatter + "\n\n" + body

    return NoteResult(
        note_path=rel_path,
        content=content,
        pages_created=[rel_path],
    )
