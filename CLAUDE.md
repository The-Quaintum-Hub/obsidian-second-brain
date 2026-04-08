# Obsidian Second Brain

This project turns Claude Code session history into a navigable Obsidian knowledge graph.

## Structure
- `scripts/` — Python scripts for JSONL parsing, session capture, batch ingestion
- `mcp-server/` — Node.js MCP server for vault queries (6 tools)
- `templates/` — Note templates
- `obsidian-config/` — Obsidian graph presets with color-coded categories
- `setup.sh` — Interactive multi-OS installer

## Key Commands
```bash
# Session capture (Stop hook)
python3 scripts/capture_session.py

# Context injection (SessionStart hook)
python3 scripts/session_context.py

# Batch operations
python3 scripts/batch_classify.py
python3 scripts/batch_ingest.py --manifest batch-manifest.json [--skip-enrichment]

# Maintenance
python3 scripts/weekly_digest.py [--week YYYY-WNN]
python3 scripts/stale_detect.py [--days 30] [--fix]
```

## Testing
```bash
cd scripts && python3 -m pytest -v
```

## Vault Location
Configured via `VAULT_PATH` in `.env` or environment variable.
