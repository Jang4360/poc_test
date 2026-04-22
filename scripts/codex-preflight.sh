#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT_DIR/scripts/update-progress.sh" >/dev/null
"$ROOT_DIR/scripts/update-metrics.sh" >/dev/null

python3 - <<'PY' "$ROOT_DIR"
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(sys.argv[1])
progress = json.loads((root / ".ai" / "PLANS" / "progress.json").read_text(encoding="utf-8"))
metrics = json.loads((root / ".ai" / "EVALS" / "metrics.json").read_text(encoding="utf-8"))
project_md = (root / ".ai" / "PROJECT.md").read_text(encoding="utf-8")
smoke_sh = (root / "scripts" / "smoke.sh").read_text(encoding="utf-8")
retry_log = root / ".ai" / "EVALS" / "retry-log.jsonl"

items = progress.get("items", [])
summary = progress.get("summary", {})
blocked = [item for item in items if item.get("status") == "blocked"]
in_progress = [item for item in items if item.get("status") == "in_progress"]

hot_clusters = Counter()
window_start = datetime.now(timezone.utc) - timedelta(hours=24)
if retry_log.exists():
    for line in retry_log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            sig = item.get("signature", "")
            ts = item.get("timestamp", "")
            note = item.get("note", "")
            if not sig or sig == "placeholder" or note:
                continue
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= window_start:
                hot_clusters[sig] += 1
        except Exception:
            continue

warnings = []
if "Template Project" in project_md:
    warnings.append("project identity is still default")
if "TODO(project)" in smoke_sh:
    warnings.append("smoke command is still placeholder")
if blocked:
    warnings.append(f"{len(blocked)} blocked work item(s)")
if hot_clusters:
    clusters = [sig for sig, count in hot_clusters.items() if count >= 3]
    if clusters:
        warnings.append(f"{len(clusters)} repeated failure cluster(s) need strategy change")
if metrics.get("release_readiness_confidence") is None:
    warnings.append("release readiness confidence is not recorded yet")

print("Codex Preflight")
print("")
print("Status")
print(f"- Sprint: {progress.get('sprint_name', 'unknown')}")
print(f"- Planned: {summary.get('planned', 0)}")
print(f"- Completed: {summary.get('completed', 0)}")
print(f"- In progress: {len(in_progress)}")
print(f"- Blocked: {len(blocked)}")
print(f"- Harness health: {metrics.get('harness_health_score')}")

print("")
print("Guard Commands")
print('- Before shell mutations: scripts/check-dangerous-command.sh "<command>"')
print("- Before implementation edits: scripts/check-tdd-guard.sh --mode pre <paths>")
print("- After failed attempts: scripts/record-retry.sh <signature>")
print("- Before another repeated attempt: scripts/check-circuit-breaker.sh <signature>")

print("")
print("Validation Route")
print("- Implement, review, and QA in the same host when that is the simplest credible path")
print("- If another host should validate, use check with a cross-host route; it generates the handoff brief via scripts/review-brief.sh as part of its procedure")

if warnings:
    print("")
    print("Warnings")
    for warning in warnings:
        print(f"- {warning}")
PY
