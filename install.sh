#!/usr/bin/env bash
# packs installer — lays packs into ~/.claude/packs/ (repo is the source of truth).
# Usage: ./install.sh            all packs
#        ./install.sh frappe …   only the named packs
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.claude/packs"

if [ "$#" -gt 0 ]; then
  names="$*"
else
  names=""
  for d in "$SRC"/*/; do
    [ -d "$d" ] && names="$names $(basename "$d")"
  done
fi

echo "Installing packs into $DEST ..."
mkdir -p "$DEST"

for name in $names; do
  pack="$SRC/$name/"
  [ -d "$pack" ] || { echo "  no such pack: $name"; continue; }
  find "$pack" -type f ! -name '.DS_Store' ! -path '*__pycache__*' ! -name '*.pyc' | while IFS= read -r f; do
    rel="${f#"$pack"}"
    mkdir -p "$DEST/$name/$(dirname "$rel")"
    cp "$f" "$DEST/$name/$rel"
  done
  [ -f "$DEST/$name/detect.sh" ] && chmod +x "$DEST/$name/detect.sh"
  echo "  installed pack: $name"
done

# Record what was laid down (for `cadre status`).
python3 - "$SRC" $names <<'PY'
import hashlib, json, os, sys
src = sys.argv[1]
names = sys.argv[2:]
home = os.path.expanduser("~/.claude")
manp = os.path.join(home, ".packs-manifest.json")
man = {}
if os.path.exists(manp):
    try:
        man = json.load(open(manp))
    except Exception:
        man = {}
for name in names:
    rec = {}
    root = os.path.join(src, name)
    for dp, _, fns in os.walk(root):
        if "__pycache__" in dp:
            continue
        for fn in fns:
            if fn == ".DS_Store" or fn.endswith(".pyc"):
                continue
            f = os.path.join(dp, fn)
            rec[os.path.relpath(f, root)] = hashlib.md5(open(f, "rb").read()).hexdigest()
    man[name] = rec
json.dump(man, open(manp, "w"))
PY

echo ""
echo "Done. Cadre's session-wiring runs each pack's detect.sh at session start."
