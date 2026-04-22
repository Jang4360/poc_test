#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${1:-$(basename "$ROOT_DIR")}"

replace_text() {
  local file="$1"
  local search="$2"
  local replace="$3"
  perl -0pi -e "s/\Q${search}\E/${replace}/g" "$file"
}

replace_text "$ROOT_DIR/.ai/PROJECT.md" "Template Project" "$PROJECT_NAME"
replace_text "$ROOT_DIR/.ai/PLANS/current-sprint.md" "Adopt the template into a real repository while preserving the end-to-end loop." "Establish the initial AI harness workflow for ${PROJECT_NAME}."
replace_text "$ROOT_DIR/.ai/PLANS/progress.json" "template-adoption" "${PROJECT_NAME}-adoption"

"$ROOT_DIR/scripts/sync-adapters.sh"

cat <<EOF
bootstrap: initialized first-pass project identity for ${PROJECT_NAME}

Next steps:
- customize project commands in scripts/smoke.sh
- update .ai/PLANS/progress.json and .ai/EVALS/metrics.json
- replace TODO(project) command slots in .ai/RUNBOOKS/
- adjust .ai/ADAPTERS/codex/hooks.json if you want repo-local Codex hook behavior, then rerun scripts/sync-adapters.sh
- use scripts/codex-preflight.sh for Codex sessions; use start for implementation-plus-validation and scripts/review-brief.sh only when validation moves to another host
- run scripts/verify.sh
EOF
