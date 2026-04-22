#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT_DIR/scripts/update-progress.sh" >/dev/null
"$ROOT_DIR/scripts/update-metrics.sh" >/dev/null
python3 - <<'PY' "$ROOT_DIR"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
score = 0
max_score = 17

def emit(points, earned, label, message):
    print(f"[{earned}/{points}] {label}: {message}")

verify_ok = (root / "scripts" / "verify.sh").exists()
if verify_ok:
    import subprocess
    result = subprocess.run(["bash", str(root / "scripts" / "verify.sh")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode == 0:
        score += 2
        emit(2, 2, "structure", "canonical files, json artifacts, and adapters verify")
    else:
        emit(2, 0, "structure", "run scripts/verify.sh and fix the reported issues")

project_md = (root / ".ai" / "PROJECT.md").read_text(encoding="utf-8")
if "Template Project" not in project_md:
    score += 2
    emit(2, 2, "identity", "project identity looks customized")
else:
    emit(2, 0, "identity", "replace the default project name in .ai/PROJECT.md")

runbook_points = 0
for runbook in ["local-setup.md", "release.md", "rollback.md"]:
    text = (root / ".ai" / "RUNBOOKS" / runbook).read_text(encoding="utf-8")
    if "TODO(project)" not in text:
        runbook_points += 1
score += runbook_points
emit(3, runbook_points, "runbooks", "project-specific commands documented")

smoke_text = (root / "scripts" / "smoke.sh").read_text(encoding="utf-8")
if "TODO(project)" not in smoke_text:
    score += 1
    emit(1, 1, "smoke", "placeholder smoke command was replaced")
else:
    emit(1, 0, "smoke", "replace the project-specific placeholder in scripts/smoke.sh or use HARNESS_SMOKE_COMMAND")

hooks_text = (root / ".codex" / "hooks.json").read_text(encoding="utf-8")
if '"SessionStart"' in hooks_text:
    score += 1
    emit(1, 1, "codex hooks", "minimal repo-local Codex hook wiring is present")
else:
    emit(1, 0, "codex hooks", "customize .ai/ADAPTERS/codex/hooks.json and resync if you want repo-local Codex hook behavior")

progress = json.loads((root / ".ai" / "PLANS" / "progress.json").read_text(encoding="utf-8"))
metrics = json.loads((root / ".ai" / "EVALS" / "metrics.json").read_text(encoding="utf-8"))

summary = progress.get("summary", {})
progress_points = 0
if progress.get("items"):
    progress_points += 1
if summary.get("planned", 0) > 0:
    progress_points += 1
if summary.get("completed", 0) > 0:
    progress_points += 1
score += progress_points
emit(3, progress_points, "progress", "structured progress state is present")

metric_points = 0
for key in [
    "first_pass_success_rate",
    "retry_count",
    "test_pass_rate",
    "unresolved_blocker_count",
    "release_readiness_confidence",
]:
    if metrics.get(key) is not None:
        metric_points += 1
score += metric_points
emit(5, metric_points, "metrics", "structured quality and readiness metrics are present")

print(f"score: {score}/{max_score}")
PY
