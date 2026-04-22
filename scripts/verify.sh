#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

required_files=(
  "README.md"
  "AGENTS.md"
  "CLAUDE.md"
  "LICENSE"
  "CONTRIBUTING.md"
  ".gitignore"
  ".ai/PROJECT.md"
  ".ai/ARCHITECTURE.md"
  ".ai/WORKFLOW.md"
  ".ai/ADAPTERS/README.md"
  ".ai/ADAPTERS/claude/README.md"
  ".ai/ADAPTERS/claude/settings.json"
  ".ai/ADAPTERS/agents/README.md"
  ".ai/ADAPTERS/codex/README.md"
  ".ai/ADAPTERS/codex/config.toml"
  ".ai/ADAPTERS/codex/hooks.json"
  ".ai/GUARDS.md"
  ".ai/PROMOTION.md"
  ".ai/AUTOMATION.md"
  ".ai/MEMORY/MEMORY.md"
  ".ai/MEMORY/debugging.md"
  ".ai/MEMORY/conventions.md"
  ".ai/MEMORY/incidents.md"
  ".ai/DECISIONS/ADR-template.md"
  ".ai/PLANS/roadmap.md"
  ".ai/PLANS/backlog.md"
  ".ai/PLANS/current-sprint.md"
  ".ai/PLANS/subplan-template.md"
  ".ai/PLANS/current-sprint/README.md"
  ".ai/PLANS/progress.json"
  ".ai/EVALS/done-criteria.md"
  ".ai/EVALS/exception-checklist.md"
  ".ai/EVALS/smoke-checklist.md"
  ".ai/EVALS/failure-patterns.md"
  ".ai/EVALS/scorecard.md"
  ".ai/EVALS/metrics.json"
  ".ai/EVALS/promotion-log.jsonl"
  ".ai/EVALS/retry-log.jsonl"
  ".ai/RUNBOOKS/local-setup.md"
  ".ai/RUNBOOKS/release.md"
  ".ai/RUNBOOKS/rollback.md"
  "scripts/sync-adapters.sh"
  "scripts/verify.sh"
  "scripts/smoke.sh"
  "scripts/score.sh"
  "scripts/detect-project-stack.sh"
  "scripts/scaffold-specs.sh"
  "scripts/scaffold-plan.sh"
  "scripts/dashboard.sh"
  "scripts/check-tdd-guard.sh"
  "scripts/check-dangerous-command.sh"
  "scripts/check-circuit-breaker.sh"
  "scripts/codex-hook-session-start.sh"
  "scripts/codex-preflight.sh"
  "scripts/codex-review-brief.sh"
  "scripts/review-brief.sh"
  "scripts/hook-pre-edit.sh"
  "scripts/record-retry.sh"
  "scripts/record-promotion.sh"
  "scripts/bootstrap-template.sh"
  "scripts/update-progress.sh"
  "scripts/update-metrics.sh"
  "scripts/pipeline-check.sh"
  "scripts/hook-pre-bash.sh"
  "scripts/hook-post-edit.sh"
  ".claude/settings.json"
  ".claude/README.md"
  ".agents/README.md"
  ".codex/config.toml"
  ".codex/hooks.json"
  ".codex/README.md"
)

required_skills=(
  "office-hours"
  "plan-ceo"
  "plan-eng"
  "plan-design"
  "docs"
  "plan"
  "autoplan"
  "start"
  "implement-feature"
  "fix-bug"
  "refactor-module"
  "write-test"
  "review"
  "investigate"
  "check"
  "qa"
  "qa-only"
  "design-review"
  "benchmark"
  "security-review"
  "ship"
  "canary"
  "deploy-check"
  "document-release"
  "retro"
  "learn"
  "dashboard"
)

required_sections=(
  "## purpose"
  "## when to use"
  "## inputs"
  "## procedure"
  "## outputs"
  "## escalation rules"
  "## handoff rules"
)

for file in "${required_files[@]}"; do
  if [[ ! -f "$ROOT_DIR/$file" ]]; then
    echo "missing required file: $file" >&2
    exit 1
  fi
done

required_plan_sections=(
  "## Goal"
  "## Success Criteria"
  "## Workstream Index"
)

for section in "${required_plan_sections[@]}"; do
  if ! grep -q "^${section}$" "$ROOT_DIR/.ai/PLANS/current-sprint.md"; then
    echo "missing sprint section '$section' in .ai/PLANS/current-sprint.md" >&2
    exit 1
  fi
done

required_subplan_sections=(
  "## Goal"
  "## Success Criteria"
  "## Implementation Plan"
  "## Validation Plan"
  "## Handoff"
)

while IFS= read -r plan_file; do
  [[ -z "$plan_file" ]] && continue
  for section in "${required_subplan_sections[@]}"; do
    if ! grep -q "^${section}$" "$plan_file"; then
      echo "missing subplan section '$section' in ${plan_file#$ROOT_DIR/}" >&2
      exit 1
    fi
  done
done < <(find "$ROOT_DIR/.ai/PLANS/current-sprint" -mindepth 1 -maxdepth 1 -type f -name '*.md' ! -name 'README.md' | sort)

required_executables=(
  "scripts/sync-adapters.sh"
  "scripts/verify.sh"
  "scripts/smoke.sh"
  "scripts/score.sh"
  "scripts/detect-project-stack.sh"
  "scripts/scaffold-specs.sh"
  "scripts/scaffold-plan.sh"
  "scripts/dashboard.sh"
  "scripts/check-tdd-guard.sh"
  "scripts/check-dangerous-command.sh"
  "scripts/check-circuit-breaker.sh"
  "scripts/codex-hook-session-start.sh"
  "scripts/codex-preflight.sh"
  "scripts/codex-review-brief.sh"
  "scripts/review-brief.sh"
  "scripts/hook-pre-edit.sh"
  "scripts/record-retry.sh"
  "scripts/record-promotion.sh"
  "scripts/bootstrap-template.sh"
  "scripts/update-progress.sh"
  "scripts/update-metrics.sh"
  "scripts/pipeline-check.sh"
  "scripts/hook-pre-bash.sh"
  "scripts/hook-post-edit.sh"
)

for file in "${required_executables[@]}"; do
  if [[ ! -x "$ROOT_DIR/$file" ]]; then
    echo "required script is not executable: $file" >&2
    exit 1
  fi
done

for skill in "${required_skills[@]}"; do
  canonical_skill="$ROOT_DIR/.ai/SKILLS/$skill/SKILL.md"
  claude_skill="$ROOT_DIR/.claude/skills/$skill/SKILL.md"
  agents_skill="$ROOT_DIR/.agents/skills/$skill/SKILL.md"

  if [[ ! -f "$canonical_skill" ]]; then
    echo "missing canonical skill: .ai/SKILLS/$skill/SKILL.md" >&2
    exit 1
  fi

  if ! grep -q '^name:' "$canonical_skill"; then
    echo "missing skill name metadata: $canonical_skill" >&2
    exit 1
  fi

  if ! grep -q '^description:' "$canonical_skill"; then
    echo "missing skill description metadata: $canonical_skill" >&2
    exit 1
  fi

  for section in "${required_sections[@]}"; do
    if ! grep -q "^${section}$" "$canonical_skill"; then
      echo "missing section '$section' in $canonical_skill" >&2
      exit 1
    fi
  done

  if [[ ! -f "$claude_skill" ]]; then
    echo "missing Claude adapter skill: $claude_skill" >&2
    exit 1
  fi

  if [[ ! -f "$agents_skill" ]]; then
    echo "missing Codex adapter skill: $agents_skill" >&2
    exit 1
  fi

  if ! diff -qr "$ROOT_DIR/.ai/SKILLS/$skill" "$ROOT_DIR/.claude/skills/$skill" >/dev/null; then
    echo "Claude adapter is out of sync for skill: $skill" >&2
    exit 1
  fi

  if ! diff -qr "$ROOT_DIR/.ai/SKILLS/$skill" "$ROOT_DIR/.agents/skills/$skill" >/dev/null; then
    echo "Codex adapter is out of sync for skill: $skill" >&2
    exit 1
  fi
done

if ! python3 - <<'PY' "$ROOT_DIR/.ai/PLANS/progress.json" "$ROOT_DIR/.ai/EVALS/metrics.json" "$ROOT_DIR/.ai/ADAPTERS/claude/settings.json" "$ROOT_DIR/.ai/ADAPTERS/codex/hooks.json" "$ROOT_DIR/.claude/settings.json" "$ROOT_DIR/.codex/hooks.json"
import json
import sys

for path in sys.argv[1:]:
    with open(path, "r", encoding="utf-8") as fh:
        json.load(fh)
PY
then
  echo "one or more json artifacts are invalid" >&2
  exit 1
fi

if [[ -f "$ROOT_DIR/.claude/settings.local.json" ]]; then
  echo ".claude/settings.local.json should remain local-only and not be committed" >&2
  exit 1
fi

if ! grep -q '^\.claude/settings\.local\.json$' "$ROOT_DIR/.gitignore"; then
  echo ".gitignore should ignore .claude/settings.local.json" >&2
  exit 1
fi

if ! diff -q "$ROOT_DIR/.ai/ADAPTERS/claude/settings.json" "$ROOT_DIR/.claude/settings.json" >/dev/null; then
  echo "Claude settings adapter is out of sync" >&2
  exit 1
fi

if ! diff -q "$ROOT_DIR/.ai/ADAPTERS/codex/config.toml" "$ROOT_DIR/.codex/config.toml" >/dev/null; then
  echo "Codex config adapter is out of sync" >&2
  exit 1
fi

if ! diff -q "$ROOT_DIR/.ai/ADAPTERS/codex/hooks.json" "$ROOT_DIR/.codex/hooks.json" >/dev/null; then
  echo "Codex hooks adapter is out of sync" >&2
  exit 1
fi

echo "verify: repository structure and adapter sync look good"
