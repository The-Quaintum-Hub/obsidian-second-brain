"""Shared configuration for obsidian-wiki scripts."""
import os
from pathlib import Path

def get_vault_path() -> Path:
    vault = os.environ.get("VAULT_PATH")
    if not vault:
        env_file = Path(__file__).parent.parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("VAULT_PATH="):
                    vault = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not vault:
        raise RuntimeError("VAULT_PATH not set. Set it in ~/.obsidian-wiki/.env")
    return Path(vault)

def get_claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"

def get_pending_dir() -> Path:
    d = Path.home() / ".obsidian-wiki" / "pending"
    d.mkdir(parents=True, exist_ok=True)
    return d
