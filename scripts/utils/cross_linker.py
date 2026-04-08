"""
cross_linker.py — Scan the vault and add [[wikilinks]] for known concepts.

Public API
----------
run_cross_linker(vault_path: Path) -> dict
    Scans every .md file and replaces the first occurrence of each registered
    term (that is not already linked) with a [[target|display]] wikilink.

    Returns:
        {
            "files_scanned": int,
            "links_added": int,
            "files_modified": int,
        }
"""
from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Registry builder
# ---------------------------------------------------------------------------

_SOURCE_DIRS = ("concepts", "entities", "projects", "decisions", "synthesis")
_EXISTING_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _build_registry(vault_path: Path) -> dict[str, tuple[str, str]]:
    """
    Return a mapping:
        lowercase_term -> (relative_path_without_md, display_name)

    Registers:
        1. filename stem (lowercase) → path
        2. frontmatter ``title`` value (lowercase) → same path  (first 300 chars)
    """
    registry: dict[str, tuple[str, str]] = {}

    fm_title_re = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)

    for dir_name in _SOURCE_DIRS:
        src_dir = vault_path / dir_name
        if not src_dir.is_dir():
            continue
        for md in src_dir.rglob("*.md"):
            # relative path without .md extension
            rel = str(md.relative_to(vault_path).with_suffix(""))
            stem = md.stem  # display name = stem

            # Register by stem
            registry[stem.lower()] = (rel, stem)

            # Also register by frontmatter title if different from stem
            try:
                head = md.read_text(encoding="utf-8", errors="replace")[:300]
            except OSError:
                continue
            m = fm_title_re.search(head)
            if m:
                fm_title = m.group(1).strip()
                key = fm_title.lower()
                if key != stem.lower() and key not in registry:
                    registry[key] = (rel, fm_title)

    return registry


# ---------------------------------------------------------------------------
# Existing-link extraction
# ---------------------------------------------------------------------------

def _existing_link_targets(text: str) -> set[str]:
    """Return the set of wikilink targets already present in *text*."""
    targets: set[str] = set()
    for m in _EXISTING_LINK_RE.finditer(text):
        inner = m.group(1)
        # Handle [[target|alias]] and [[target]]
        target = inner.split("|")[0].strip().lower()
        targets.add(target)
    return targets


# ---------------------------------------------------------------------------
# Frontmatter / body split
# ---------------------------------------------------------------------------

def _split_fm_body(content: str) -> tuple[str, str]:
    """
    Return (frontmatter_block, body).

    If content starts with ``---``, the first ``---``-delimited block is the
    frontmatter; everything after the closing ``---`` is the body.
    Otherwise frontmatter is empty and body is the full content.
    """
    if not content.startswith("---"):
        return "", content

    # Find the closing ---
    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return "", content  # malformed — treat all as body

    fm = content[: end_idx + 4]   # includes closing ---
    body = content[end_idx + 4:]  # everything after
    return fm, body


# ---------------------------------------------------------------------------
# Per-file linker
# ---------------------------------------------------------------------------

def _link_file(
    md_path: Path,
    vault_path: Path,
    registry: dict[str, tuple[str, str]],
) -> int:
    """
    Add wikilinks to *md_path* for any registry terms not yet linked.

    Returns the number of new links added.
    """
    try:
        content = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    # Determine this file's own registry key so we don't self-link
    self_rel = str(md_path.relative_to(vault_path).with_suffix("")).lower()
    self_stem = md_path.stem.lower()

    fm, body = _split_fm_body(content)

    # Collect already-linked targets (from full content, including frontmatter)
    already_linked = _existing_link_targets(content)

    links_added = 0
    modified_body = body

    for term, (target_rel, display) in registry.items():
        # Skip self
        if target_rel.lower() == self_rel or term == self_stem:
            continue

        # Skip if already linked
        target_lower = target_rel.lower()
        if target_lower in already_linked or term in already_linked:
            continue

        # Replace first word-boundary occurrence in the body (case-insensitive)
        pattern = re.compile(
            r"(?<!\[)(?<!\|)\b(" + re.escape(term) + r")\b(?!\])",
            re.IGNORECASE,
        )
        new_body, count = pattern.subn(
            lambda m, t=target_rel, d=display: f"[[{t}|{m.group(0)}]]",
            modified_body,
            count=1,
        )
        if count:
            modified_body = new_body
            already_linked.add(target_lower)
            links_added += count

    if links_added:
        new_content = fm + modified_body
        try:
            md_path.write_text(new_content, encoding="utf-8")
        except OSError:
            return 0

    return links_added


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_cross_linker(vault_path: Path) -> dict:
    """
    Scan all .md files in *vault_path* (except dot-files and _archives) and
    add [[wikilinks]] for known registry terms.

    Returns stats dict with keys: files_scanned, links_added, files_modified.
    """
    registry = _build_registry(vault_path)

    files_scanned = 0
    total_links_added = 0
    files_modified = 0

    for md_path in vault_path.rglob("*.md"):
        # Skip dot-files and _archives
        parts = md_path.relative_to(vault_path).parts
        if any(p.startswith(".") or p == "_archives" for p in parts):
            continue

        files_scanned += 1
        added = _link_file(md_path, vault_path, registry)
        if added:
            total_links_added += added
            files_modified += 1

    return {
        "files_scanned": files_scanned,
        "links_added": total_links_added,
        "files_modified": files_modified,
    }


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from utils.config import get_vault_path
        vp = get_vault_path()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    stats = run_cross_linker(vp)
    print(
        f"Cross-linker done: {stats['files_scanned']} files scanned, "
        f"{stats['links_added']} links added across {stats['files_modified']} files."
    )
