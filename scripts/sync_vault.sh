#!/usr/bin/env bash
# One-way mirror: Linux primary -> Windows (Obsidian graph view only).
set -euo pipefail
SRC="$HOME/SecondBrain/"
DST="/mnt/c/Users/T-Raw/Documents/SecondBrain/"

# Safety guard: never sync if source looks empty/broken (avoid wiping the mirror).
count=$(find "$SRC" -name '*.md' 2>/dev/null | wc -l)
if [ "$count" -lt 5 ]; then
  echo "sync_vault: source has only $count md files (<5) — aborting to protect mirror." >&2
  exit 0
fi
[ -d "$DST" ] || { echo "sync_vault: Windows mirror dir missing, skipping." >&2; exit 0; }

# --delete keeps the mirror clean; .obsidian (Obsidian config) and .git are preserved on the Windows side.
rsync -a --delete --exclude='.obsidian/' --exclude='.git/' "$SRC" "$DST"
echo "sync_vault: mirrored $count notes to Windows."
