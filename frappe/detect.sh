#!/usr/bin/env bash
# cadre pack detector — frappe. Silent unless this project is a Frappe context.
# Contract: fast, no output when not applicable (see ~/.claude/packs/README.md).
set -u
here="$(cd "$(dirname "$0")" && pwd)"

is_frappe=0
d="$PWD"
while [ "$d" != "/" ] && [ -n "$d" ]; do
  if [ -f "$d/sites/common_site_config.json" ] || [ -d "$d/apps/frappe" ]; then
    is_frappe=1; break
  fi
  d=$(dirname "$d")
done
# Standalone app repo (no bench above): <app>/<app>/hooks.py + modules.txt
if [ "$is_frappe" = 0 ]; then
  for h in "$PWD"/*/hooks.py; do
    [ -f "$h" ] && [ -f "$(dirname "$h")/modules.txt" ] && { is_frappe=1; break; }
  done
fi
[ "$is_frappe" = 1 ] || exit 0

echo "cadre pack:frappe — Frappe context detected. The kit lives at $here"
python3 "$here/probe.py" 2>/dev/null | head -40
echo ""
echo "Per action: read only the matching trigger section in $here/CONTRACTS.md (it opens with"
echo "'I am about to create a file — any file': take the lowest rung that fits, say why)."
echo "Before deciding what to build: python3 $here/frame.py --new-app <name>  |  frame.py \"<DocType>\" --app <path>"
echo "Before saying done: python3 $here/probe.py --gate <app path>   # exit 1 on a contract breach"
echo "Kit defect/improvement? Never edit $here — fix it in the packs repo (packs_repo in"
echo "~/.claude/cadre.json), run cadre sync; or log it in the project ledger as tooling:frappe."
if [ -d "$here/skills" ] && ! ls "$PWD"/.claude/skills/frappe-* >/dev/null 2>&1; then
  echo "Frappe skills are not linked in this folder — run: bash $here/link-skills.sh \"$PWD\"  (then restart the session)"
fi
