#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 - <<'PY' "$ROOT_DIR"
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
progress = json.loads((root / ".ai" / "PLANS" / "progress.json").read_text(encoding="utf-8"))
current_sprint = (root / ".ai" / "PLANS" / "current-sprint.md").read_text(encoding="utf-8").strip()

status = subprocess.run(
    ["git", "status", "--short"],
    cwd=root,
    check=False,
    capture_output=True,
    text=True,
).stdout.splitlines()

diff_stats = subprocess.run(
    ["git", "diff", "--stat"],
    cwd=root,
    check=False,
    capture_output=True,
    text=True,
).stdout.strip()

changed_files = []
tests_changed = False
for line in status:
    if not line.strip():
        continue
    path = line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    changed_files.append(path)
    lower = path.lower()
    if "test" in lower or "spec" in lower or path.startswith("tests/") or "__tests__/" in path:
        tests_changed = True

items = progress.get("items", [])
in_progress = [item for item in items if item.get("status") == "in_progress"]
blocked = [item for item in items if item.get("status") == "blocked"]

print("Validation Handoff Brief")
print("")
print("Scope")
if changed_files:
    for path in changed_files:
        print(f"- {path}")
else:
    print("- no local changes detected")

print("")
print("Checks")
print(f"- Tests changed in this workspace: {'yes' if tests_changed else 'no'}")
print(f"- In-progress plan items: {len(in_progress)}")
print(f"- Blocked plan items: {len(blocked)}")

if diff_stats:
    print("")
    print("Diff stat")
    for line in diff_stats.splitlines():
        print(f"- {line}")

print("")
print("Sprint context")
for line in current_sprint.splitlines()[:20]:
    print(f"- {line}" if line else "-")

if blocked:
    print("")
    print("Blocked items")
    for item in blocked:
        print(f"- {item.get('id')}: {item.get('title')}")

print("")
print("Validation request")
print("- Focus on correctness, maintainability, edge cases, missing tests, and production risk")
print("- Run the review skill and the appropriate QA path, or use check as the orchestration entrypoint")
print("- Same-host validation is acceptable; this brief exists only when another host is taking over")
PY
