#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROGRESS_FILE="$ROOT_DIR/.ai/PLANS/progress.json"
METRICS_FILE="$ROOT_DIR/.ai/EVALS/metrics.json"
RETRY_FILE="$ROOT_DIR/.ai/EVALS/retry-log.jsonl"
PROMOTION_FILE="$ROOT_DIR/.ai/EVALS/promotion-log.jsonl"

python3 - <<'PY' "$PROGRESS_FILE" "$METRICS_FILE" "$RETRY_FILE" "$PROMOTION_FILE"
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

progress_path = Path(sys.argv[1])
metrics_path = Path(sys.argv[2])
retry_path = Path(sys.argv[3])
promotion_path = Path(sys.argv[4])

progress = json.loads(progress_path.read_text(encoding="utf-8"))
metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

retry_events = []
if retry_path.exists():
    for line in retry_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("signature") == "placeholder" or event.get("note"):
            continue
        retry_events.append(event)

promotion_count = 0
if promotion_path.exists():
    for line in promotion_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("destination") == "none":
            continue
        promotion_count += 1

retry_count = len(retry_events)
counts = Counter(event.get("signature", "") for event in retry_events if event.get("signature"))
repeated = sum(count for _, count in counts.items() if count > 1)
repeated_failure_rate = round((repeated / retry_count), 3) if retry_count else None
blocked = int(progress.get("summary", {}).get("blocked", 0))

health = 100
health -= min(blocked * 10, 30)
health -= min(retry_count * 5, 25)
if repeated_failure_rate is not None:
    health -= int(repeated_failure_rate * 20)
health += min(promotion_count * 2, 10)
health = max(0, min(100, health))

summary = progress.setdefault("summary", {})
progress_pct = float(summary.get("progress_percentage", 0) or 0)
quality_adjusted_progress = round(progress_pct * (health / 100), 1)
confidence_score = round(max(0.0, min(1.0, (health / 100) - (blocked * 0.1))), 2)

metrics["updated_at"] = datetime.now(timezone.utc).date().isoformat()
metrics["retry_count"] = retry_count
metrics["repeated_failure_rate"] = repeated_failure_rate
metrics["unresolved_blocker_count"] = blocked
metrics["harness_health_score"] = health

summary["quality_adjusted_progress"] = quality_adjusted_progress
summary["confidence_score"] = confidence_score

progress_path.write_text(json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"update-metrics: retry_count={retry_count}, blocked={blocked}, health={health}, quality_adjusted_progress={quality_adjusted_progress}")
PY
