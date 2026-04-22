#!/usr/bin/env bash
# Claude Code PostToolUse hook — Edit and Write tools
# Called after every Edit or Write tool use. Receives tool result as JSON on stdin.
# Exit non-zero to surface a warning to Claude (action already happened; cannot block).
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

# Make path relative to project root for the guard
rel_path="${file_path#$ROOT_DIR/}"

exec "$ROOT_DIR/scripts/check-tdd-guard.sh" "$rel_path"
