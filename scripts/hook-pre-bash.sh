#!/usr/bin/env bash
# Claude Code PreToolUse hook — Bash tool
# Called before every Bash tool use. Receives tool input as JSON on stdin.
# Exit non-zero to block the command (stdout becomes the reason shown to Claude).
set -euo pipefail

ROOT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

input=$(cat)
command=$(echo "$input" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('command', ''))
except Exception:
    pass
" 2>/dev/null || true)

if [[ -z "$command" ]]; then
  exit 0
fi

"$ROOT_DIR/scripts/check-dangerous-command.sh" "$command"
