#!/usr/bin/env bash
set -euo pipefail

COMMAND_STRING="${*:-}"

if [[ -z "$COMMAND_STRING" ]]; then
  echo "usage: scripts/check-dangerous-command.sh <command string>" >&2
  exit 1
fi

blocked_patterns=(
  '(^|[[:space:]])rm[[:space:]]+-rf([[:space:]]|$)'
  'git[[:space:]]+reset[[:space:]]+--hard'
  'git[[:space:]]+clean([[:space:]].*)?-fd'
  'git[[:space:]]+push([[:space:]].*)?[[:space:]]+--force($|[[:space:]])'
  'git[[:space:]]+push([[:space:]].*)?[[:space:]]+-f($|[[:space:]])'
  'find[[:space:]].*-delete'
  'terraform[[:space:]]+destroy'
  '(^|[[:space:]])mkfs'
  '(^|[[:space:]])dd[[:space:]]+if='
)

for pattern in "${blocked_patterns[@]}"; do
  if [[ "$COMMAND_STRING" =~ $pattern ]]; then
    echo "dangerous-command-guard: blocked command"
    echo "$COMMAND_STRING"
    exit 2
  fi
done

echo "dangerous-command-guard: ok"
