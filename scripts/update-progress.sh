#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROGRESS_FILE="$ROOT_DIR/.ai/PLANS/progress.json"

python3 - <<'PY' "$PROGRESS_FILE"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))

items = data.get("items", [])
planned = len(items)
completed = sum(1 for i in items if i.get("status") == "completed")
in_progress = sum(1 for i in items if i.get("status") == "in_progress")
blocked = sum(1 for i in items if i.get("status") == "blocked")
progress_pct = round((completed / planned * 100), 1) if planned > 0 else 0

summary = data.setdefault("summary", {})
summary["planned"] = planned
summary["completed"] = completed
summary["in_progress"] = in_progress
summary["blocked"] = blocked
summary["progress_percentage"] = progress_pct
data["updated_at"] = datetime.now(timezone.utc).date().isoformat()
# quality_adjusted_progress and confidence_score are not auto-computed; preserve existing values

path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"update-progress: {completed}/{planned} completed ({progress_pct}%), {in_progress} in-progress, {blocked} blocked")
PY
