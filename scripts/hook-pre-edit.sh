#!/usr/bin/env bash
# Claude Code PreToolUse hook — Edit and Write tools
# Blocks production edits when no related test work exists yet.
set -euo pipefail

ROOT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

input=$(cat)
file_path=$(echo "$input" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    pass
" 2>/dev/null || true)

if [[ -z "$file_path" ]]; then
  exit 0
fi

rel_path="${file_path#$ROOT_DIR/}"
exec "$ROOT_DIR/scripts/check-tdd-guard.sh" --mode pre "$rel_path"
