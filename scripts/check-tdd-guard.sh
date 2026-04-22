#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="post"

collect_repo_changed_files() {
  git -C "$ROOT_DIR" status --porcelain=v1 --untracked-files=all 2>/dev/null \
    | sed -E 's/^...//' \
    | sed -E 's#.* -> ##' \
    || true
}

if [[ "${1:-}" == "--mode" ]]; then
  MODE="${2:-post}"
  shift 2
fi

changed_files=()
if [[ "$#" -gt 0 ]]; then
  changed_files=("$@")
  while IFS= read -r file; do
    [[ -n "$file" ]] && changed_files+=("$file")
  done < <(collect_repo_changed_files)
else
  while IFS= read -r file; do
    [[ -n "$file" ]] && changed_files+=("$file")
  done < <(collect_repo_changed_files)
fi

if [[ "${#changed_files[@]}" -eq 0 ]]; then
  echo "tdd-guard: no changed files detected"
  exit 0
fi

production_changed=0
tests_changed=0

for file in "${changed_files[@]}"; do
  case "$file" in
    .ai/*|.claude/*|.agents/*|README.md|AGENTS.md|CLAUDE.md|CONTRIBUTING.md|LICENSE|scripts/*)
      continue
      ;;
  esac

  case "$file" in
    *test*|*spec*|tests/*|__tests__/*)
      tests_changed=1
      ;;
    *.js|*.jsx|*.ts|*.tsx|*.py|*.rb|*.go|*.rs|*.java|*.kt|*.swift|*.php|*.c|*.cc|*.cpp)
      production_changed=1
      ;;
  esac
done

if [[ "$production_changed" -eq 1 && "$tests_changed" -eq 0 ]]; then
  if [[ "$MODE" == "pre" ]]; then
    echo "tdd-guard: blocked production edit because no related test changes were found"
    echo "hint: add or modify tests first, or explicitly accept an exception in the host policy"
  else
    echo "tdd-guard: production implementation changed without related test changes"
    echo "policy: warn or block depending on host-specific wiring"
  fi
  exit 2
fi

echo "tdd-guard: ok"
