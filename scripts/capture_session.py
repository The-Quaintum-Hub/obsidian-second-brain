"""
capture_session.py — Claude Code Stop hook entry point.

Called automatically when a Claude Code session ends. Finds the latest JSONL
session, parses it, optionally enriches it with an LLM, generates an Obsidian
note and updates the manifest.
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a script from any directory
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import get_vault_path, get_claude_projects_dir
from utils.jsonl_parser import parse_session, SessionData
from utils.manifest import Manifest
from utils.note_generator import generate_session_note

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session discovery
# ---------------------------------------------------------------------------

def find_latest_session(projects_dir: Path) -> Path | None:
    """
    Return the most recently modified .jsonl file under *projects_dir*,
    skipping any path that contains a 'subagents' component.
    """
    if not projects_dir.is_dir():
        return None

    candidates: list[tuple[float, Path]] = []
    for p in projects_dir.rglob("*.jsonl"):
        # Skip subagent sessions
        if "subagents" in p.parts:
            continue
        try:
            mtime = p.stat().st_mtime
            candidates.append((mtime, p))
        except OSError:
            pass

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


# ---------------------------------------------------------------------------
# LLM enrichment
# ---------------------------------------------------------------------------

_ENRICH_PROMPT = textwrap.dedent("""\
    You are a knowledge-management assistant. Given the transcript of a
    Claude Code session, produce a JSON object with EXACTLY these keys:

    {
      "title": "<short, action-oriented title (≤60 chars)>",
      "summary": "<2-3 sentence summary of what was accomplished>",
      "tags": ["tag1", "tag2"],
      "decisions": ["decision or finding 1", "decision or finding 2"],
      "concepts": ["ConceptName1", "ConceptName2"]
    }

    Rules:
    - title: imperative verb phrase, no trailing period
    - tags: 3–6 lowercase kebab-case strings, no spaces
    - decisions: concrete technical choices or key findings, or []
    - concepts: proper nouns / named technologies extracted from the text, or []
    - Output ONLY the JSON object, no markdown fences, no extra text.

    SESSION TRANSCRIPT:
    ---
""")


def _enrich_with_llm(transcript: str) -> dict | None:
    """
    Call `claude -p` with an enrichment prompt and return parsed JSON,
    or None on any failure.
    """
    prompt = _ENRICH_PROMPT + transcript[:8000]  # cap to avoid huge inputs
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("claude -p returned non-zero: %s", result.stderr[:200])
            return None
        output = result.stdout.strip()
        # Strip markdown fences if present
        if output.startswith("```"):
            lines = output.splitlines()
            output = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])
        return json.loads(output)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as exc:
        logger.warning("Enrichment failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Log.md helpers
# ---------------------------------------------------------------------------

def _update_log(vault_path: Path, session: SessionData, note_path: str) -> None:
    """Append a one-line entry to journal/log.md."""
    log_file = vault_path / "journal" / "log.md"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    date_str = (session.start_time or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M")
    line = (
        f"| {date_str} | {session.project} | {session.classification} "
        f"| {session.duration_min}m | [[{note_path.replace('.md','')}]] |\n"
    )

    if not log_file.exists():
        header = (
            "# Session Log\n\n"
            "| Date | Project | Classification | Duration | Note |\n"
            "|------|---------|----------------|----------|------|\n"
        )
        log_file.write_text(header + line, encoding="utf-8")
    else:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_capture(
    jsonl_path: Path,
    vault_path: Path,
    skip_enrichment: bool = False,
) -> bool:
    """
    Run the full capture pipeline for *jsonl_path*.

    Returns True if a note was created, False if skipped.
    """
    # 1. Parse session
    session = parse_session(jsonl_path)

    # 2. Skip trivial / subagent
    if session.classification in ("trivial", "subagent"):
        logger.info("Skipping %s session: %s", session.classification, jsonl_path.name)
        return False

    # 3. Duplicate check
    manifest = Manifest(vault_path)
    if manifest.is_processed(session.session_id):
        logger.info("Session already processed: %s", session.session_id)
        return False

    # 4. Optional LLM enrichment
    enrichment: dict | None = None
    if not skip_enrichment:
        transcript_parts: list[str] = []
        for msg in session.user_messages:
            transcript_parts.append(f"User: {msg}")
        for txt in session.assistant_text:
            transcript_parts.append(f"Assistant: {txt[:500]}")
        transcript = "\n\n".join(transcript_parts)
        enrichment = _enrich_with_llm(transcript)

    # 5. Generate note
    note_result = generate_session_note(session, vault_path, enrichment=enrichment)

    # 6. Write note to vault
    note_full_path = vault_path / note_result.note_path
    note_full_path.parent.mkdir(parents=True, exist_ok=True)
    note_full_path.write_text(note_result.content, encoding="utf-8")
    logger.info("Created note: %s", note_result.note_path)

    # 7. Update manifest
    manifest.record_session(
        session_id=session.session_id,
        project=session.project,
        source_path=str(jsonl_path),
        pages_created=note_result.pages_created,
        pages_updated=[],
    )
    manifest.save()

    # 8. Append to log.md
    _update_log(vault_path, session, note_result.note_path)

    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Capture a Claude Code session into the Obsidian vault."
    )
    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="Skip LLM enrichment (faster, no claude -p call)",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Path to a specific JSONL file (default: latest in ~/.claude/projects/)",
    )
    args = parser.parse_args()

    vault_path = get_vault_path()

    if args.jsonl:
        jsonl_path = args.jsonl
        if not jsonl_path.exists():
            logger.error("JSONL file not found: %s", jsonl_path)
            sys.exit(1)
    else:
        projects_dir = get_claude_projects_dir()
        jsonl_path = find_latest_session(projects_dir)
        if jsonl_path is None:
            logger.error("No JSONL sessions found in %s", projects_dir)
            sys.exit(1)

    logger.info("Processing: %s", jsonl_path)
    created = run_capture(jsonl_path, vault_path, skip_enrichment=args.skip_enrichment)

    if created:
        logger.info("Done — note written to vault.")
    else:
        logger.info("Done — session skipped (trivial/duplicate/subagent).")


if __name__ == "__main__":
    main()
