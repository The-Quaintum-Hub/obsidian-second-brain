# Obsidian Second Brain

> Turn your Claude Code sessions into a navigable Obsidian knowledge graph

Every Claude Code session you run gets automatically captured, parsed, and converted into interlinked Markdown notes inside an Obsidian vault. Concepts, projects, entities, and decisions surface as first-class nodes in a color-coded graph you can explore, search, and query — without any manual journaling.

## Features

- **Auto-capture via hooks** — Stop and SessionStart hooks run silently after every Claude Code session
- **Batch ingestion of history** — Import your entire existing Claude Code JSONL history in one command
- **MCP server for queries** — 6 tools for searching, browsing, and aggregating vault notes from inside Claude
- **Cross-linking** — Wikilinks are generated automatically between related sessions, concepts, and projects
- **Weekly digests** — Auto-generated summaries of the week's sessions grouped by project and concept
- **Stale detection** — Find and optionally auto-fix notes that haven't been touched in N days
- **Graph presets** — Color-coded Obsidian graph config ships out of the box
- **Multi-OS support** — Works on WSL2/Windows, macOS, and Linux via an interactive installer

## How It Works

```
Claude Code session
      │
      ▼
  JSONL file (~/.claude/projects/...)
      │
      ▼
  Python parser (scripts/utils/jsonl_parser.py)
      │  extracts: summary, concepts, entities, decisions, tools used
      ▼
  Note generator (scripts/utils/note_generator.py)
      │  produces: Markdown + YAML frontmatter + [[wikilinks]]
      ▼
  Obsidian vault
      │  folders: sessions/, concepts/, entities/, projects/, decisions/
      ▼
  MCP server (mcp-server/index.js)
      │  6 tools: search, get page, list sessions, get links, recent, stats
      ▼
  Claude Code (queries the vault mid-session)
```

The Stop hook fires after every session and captures the just-finished JSONL. The SessionStart hook injects relevant context from the vault into the next session's system prompt.

## Quick Start

### WSL2 / Windows

```bash
# Clone the repo
git clone https://github.com/TheQuaintumHub/obsidian-second-brain ~/.obsidian-wiki

# Run the installer
cd ~/.obsidian-wiki && ./setup.sh
```

The installer will detect WSL2 automatically and suggest a vault path under `/mnt/c/Users/<you>/Documents/ObsidianVault/SecondBrain` so Obsidian (running on Windows) can open it natively.

### macOS

```bash
git clone https://github.com/TheQuaintumHub/obsidian-second-brain ~/.obsidian-wiki
cd ~/.obsidian-wiki && ./setup.sh
```

Default vault path: `~/Documents/ObsidianVault/SecondBrain`

### Linux

```bash
git clone https://github.com/TheQuaintumHub/obsidian-second-brain ~/.obsidian-wiki
cd ~/.obsidian-wiki && ./setup.sh
```

Default vault path: `~/ObsidianVault/SecondBrain`

---

After setup, follow the printed instructions to:
1. Add the Stop and SessionStart hooks to `~/.claude/settings.json`
2. Register the MCP server in Claude Code settings
3. Open the vault folder in Obsidian
4. Run `cd scripts && python3 -m pytest -v` to verify everything works

## Graph Presets

The `obsidian-config/graph.json` file ships with color-coded node groups so your graph is meaningful from the first session:

| Color | Category | Description |
|-------|----------|-------------|
| Blue | `sessions/` | Individual Claude Code sessions |
| Purple | `concepts/` | Technical concepts extracted from sessions |
| Orange | `entities/` | People, tools, libraries, services |
| Green | `projects/` | Project-level rollup notes |
| Red | `decisions/` | Architectural and design decisions |

Screenshots coming soon.

## Scripts Reference

| Script | Trigger | Description |
|--------|---------|-------------|
| `capture_session.py` | Stop hook | Parses the latest JSONL, generates notes, cross-links |
| `session_context.py` | SessionStart hook | Injects relevant vault context into the new session |
| `batch_classify.py` | Manual | Scans all JSONL history, writes `batch-manifest.json` |
| `batch_ingest.py` | Manual | Ingests sessions listed in the manifest into the vault |
| `weekly_digest.py` | Cron / manual | Generates a weekly summary note (`--week YYYY-WNN`) |
| `stale_detect.py` | Cron / manual | Finds notes older than N days; `--fix` auto-updates them |

## MCP Tools

Register the MCP server in Claude Code to query your vault from inside any session:

| Tool | Description |
|------|-------------|
| `wiki_search` | Full-text search with optional category, project, and tag filters |
| `wiki_get_page` | Fetch the full content and frontmatter of a note by path |
| `wiki_list_sessions` | List session notes filtered by project or date range |
| `wiki_get_links` | Return all wikilinks in a note (outgoing and backlinks) |
| `wiki_recent` | Return the N most recently modified notes |
| `wiki_stats` | Aggregate stats: note counts per category, total sessions, top projects |

## Configuration

### Hooks (`~/.claude/settings.json`)

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.obsidian-wiki/scripts/capture_session.py"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/.obsidian-wiki/scripts/session_context.py"
          }
        ]
      }
    ]
  }
}
```

### MCP Server (`~/.claude/settings.json`)

```json
{
  "mcpServers": {
    "obsidian-wiki": {
      "command": "node",
      "args": ["/path/to/.obsidian-wiki/mcp-server/index.js"],
      "env": {
        "VAULT_PATH": "/path/to/your/ObsidianVault/SecondBrain"
      }
    }
  }
}
```

Run `./setup.sh` and it will print these snippets with your actual paths pre-filled.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `VAULT_PATH` | Absolute path to your Obsidian vault directory |

Set in `~/.obsidian-wiki/.env` (created by `setup.sh`) or export before running scripts.

## Requirements

- Python 3.9+
- Node.js 18+
- Claude Code (for hooks and MCP)
- Obsidian (to view the vault)

No additional Python packages are required beyond the standard library.

## Credits

Based on [Ar9av/obsidian-wiki](https://github.com/Ar9av/obsidian-wiki), enhanced and extended by [The Quaintum Hub](https://thequaintumhub.com) with:

- Multi-OS interactive installer
- Batch ingestion from JSONL history
- Cross-linker for automatic wikilinks
- MCP server for in-session vault queries
- Weekly digest and stale detection scripts
- SessionStart context injection hook
- Color-coded Obsidian graph presets

## License

MIT — see [LICENSE](LICENSE).
