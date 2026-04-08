#!/usr/bin/env bash
# setup.sh — Obsidian Second Brain installer
# Supports WSL2, macOS, and Linux
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colors ────────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[info]${RESET}  $*"; }
success() { echo -e "${GREEN}[ok]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${RESET}  $*"; }
error()   { echo -e "${RED}[error]${RESET} $*"; exit 1; }

echo -e "\n${BOLD}Obsidian Second Brain — Setup${RESET}\n"

# ── Detect OS ─────────────────────────────────────────────────────────────────
detect_os() {
  if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "wsl2"
  elif [[ "${OSTYPE:-}" == darwin* ]]; then
    echo "macos"
  else
    echo "linux"
  fi
}

OS=$(detect_os)
info "Detected OS: $OS"

# ── Suggest default vault path per OS ─────────────────────────────────────────
case "$OS" in
  wsl2)
    # Try to find the Windows user home via /mnt/c/Users
    WIN_USERS=$(ls /mnt/c/Users/ 2>/dev/null | grep -v 'Public\|Default\|All Users\|desktop.ini' | head -1)
    if [[ -n "$WIN_USERS" ]]; then
      DEFAULT_VAULT="/mnt/c/Users/${WIN_USERS}/Documents/ObsidianVault/SecondBrain"
    else
      DEFAULT_VAULT="$HOME/ObsidianVault/SecondBrain"
    fi
    ;;
  macos)
    DEFAULT_VAULT="$HOME/Documents/ObsidianVault/SecondBrain"
    ;;
  linux)
    DEFAULT_VAULT="$HOME/ObsidianVault/SecondBrain"
    ;;
esac

# ── Prompt for vault path ─────────────────────────────────────────────────────
echo ""
echo -e "Where should your Obsidian vault live?"
echo -e "  Default: ${BOLD}${DEFAULT_VAULT}${RESET}"
echo -n "  Vault path [press Enter to use default]: "
read -r USER_VAULT
VAULT_PATH="${USER_VAULT:-$DEFAULT_VAULT}"

# Expand ~ if present
VAULT_PATH="${VAULT_PATH/#\~/$HOME}"

info "Using vault path: $VAULT_PATH"

# ── Write .env ────────────────────────────────────────────────────────────────
ENV_FILE="$REPO_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  warn ".env already exists — updating VAULT_PATH only"
  # Remove existing VAULT_PATH line and append new one
  grep -v "^VAULT_PATH=" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
fi
echo "VAULT_PATH=${VAULT_PATH}" >> "$ENV_FILE"
success ".env written: $ENV_FILE"

# ── Create vault directory structure ─────────────────────────────────────────
DIRS=(
  "$VAULT_PATH/sessions"
  "$VAULT_PATH/concepts"
  "$VAULT_PATH/entities"
  "$VAULT_PATH/projects"
  "$VAULT_PATH/decisions"
  "$VAULT_PATH/journal"
)

for d in "${DIRS[@]}"; do
  if [[ ! -d "$d" ]]; then
    mkdir -p "$d"
    info "Created: $d"
  else
    info "Exists:  $d"
  fi
done
success "Vault directory structure ready"

# ── Copy Obsidian config (only if vault is fresh) ─────────────────────────────
OBSIDIAN_DIR="$VAULT_PATH/.obsidian"
if [[ ! -d "$OBSIDIAN_DIR" ]]; then
  mkdir -p "$OBSIDIAN_DIR"
  CONFIG_SRC="$REPO_DIR/obsidian-config"
  if [[ -f "$CONFIG_SRC/graph.json" ]]; then
    cp "$CONFIG_SRC/graph.json" "$OBSIDIAN_DIR/graph.json"
    success "Copied graph.json (color-coded graph presets)"
  fi
  if [[ -f "$CONFIG_SRC/app.json" ]]; then
    cp "$CONFIG_SRC/app.json" "$OBSIDIAN_DIR/app.json"
    success "Copied app.json (Obsidian app settings)"
  fi
else
  warn "Obsidian config dir already exists — skipping copy (no overwrite)"
fi

# ── Install MCP server dependencies ──────────────────────────────────────────
MCP_DIR="$REPO_DIR/mcp-server"
if [[ -f "$MCP_DIR/package.json" ]]; then
  info "Installing MCP server dependencies..."
  (cd "$MCP_DIR" && npm install --silent)
  success "npm install complete"
else
  warn "mcp-server/package.json not found — skipping npm install"
fi

# ── Check Python ──────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
  PYTHON_VER=$(python3 --version 2>&1)
  success "Python found: $PYTHON_VER"
else
  warn "python3 not found — scripts require Python 3.9+"
fi

# ── Print next steps ──────────────────────────────────────────────────────────
MCP_SERVER_PATH="$REPO_DIR/mcp-server/index.js"

echo ""
echo -e "${BOLD}─────────────────────────────────────────────${RESET}"
echo -e "${BOLD}  Setup complete! Next steps:${RESET}"
echo -e "${BOLD}─────────────────────────────────────────────${RESET}"
echo ""
echo -e "${BOLD}1. Configure Claude Code hooks${RESET}"
echo "   Add to ~/.claude/settings.json:"
echo ""
cat <<EOF
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${REPO_DIR}/scripts/capture_session.py"
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
            "command": "python3 ${REPO_DIR}/scripts/session_context.py"
          }
        ]
      }
    ]
  }
}
EOF

echo ""
echo -e "${BOLD}2. Add the MCP server to Claude Code${RESET}"
echo "   Add to ~/.claude/settings.json under \"mcpServers\":"
echo ""
cat <<EOF
{
  "mcpServers": {
    "obsidian-wiki": {
      "command": "node",
      "args": ["${MCP_SERVER_PATH}"],
      "env": {
        "VAULT_PATH": "${VAULT_PATH}"
      }
    }
  }
}
EOF

echo ""
echo -e "${BOLD}3. Open your vault in Obsidian${RESET}"
echo "   Vault path: ${VAULT_PATH}"
echo ""
echo -e "${BOLD}4. Run tests to verify everything works${RESET}"
echo "   cd ${REPO_DIR}/scripts && python3 -m pytest -v"
echo ""
echo -e "${GREEN}${BOLD}Done!${RESET} Your second brain is ready."
echo ""
