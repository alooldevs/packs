#!/usr/bin/env bash
# Link the pack's frappe-* skills into one project's .claude/skills/, so they load only there.
# Usage: link-skills.sh [project dir]   (default: current directory). Safe to re-run.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
proj="$(cd "${1:-$PWD}" && pwd)"
dest="$proj/.claude/skills"
mkdir -p "$dest"

n=0
for s in "$here"/skills/*/; do
  name="$(basename "$s")"
  ln -sfn "${s%/}" "$dest/$name"
  n=$((n + 1))
done

# Inside a git repo, keep the links out of its status without touching tracked files.
if git -C "$proj" rev-parse --git-dir >/dev/null 2>&1; then
  ex="$(git -C "$proj" rev-parse --git-path info/exclude)"
  case "$ex" in /*) ;; *) ex="$proj/$ex" ;; esac
  mkdir -p "$(dirname "$ex")"
  rel="$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$dest" "$(git -C "$proj" rev-parse --show-toplevel)")"
  grep -qxF "/$rel/frappe-*" "$ex" 2>/dev/null || echo "/$rel/frappe-*" >> "$ex"
fi

echo "linked $n frappe skills into $dest"
