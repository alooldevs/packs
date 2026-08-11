#!/usr/bin/env bash
# packs installer — lays every pack into ~/.claude/packs/ (repo is the source of truth).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/packs"

echo "Installing packs into $DEST ..."
mkdir -p "$DEST"

for pack in "$SRC"/*/; do
  name=$(basename "$pack")
  find "$pack" -type f ! -name '.DS_Store' ! -path '*__pycache__*' ! -name '*.pyc' | while IFS= read -r f; do
    rel="${f#"$pack"}"
    mkdir -p "$DEST/$name/$(dirname "$rel")"
    cp "$f" "$DEST/$name/$rel"
  done
  [ -f "$DEST/$name/detect.sh" ] && chmod +x "$DEST/$name/detect.sh"
  echo "  installed pack: $name"
done

echo ""
echo "Done. Cadre's session-wiring runs each pack's detect.sh at session start."
