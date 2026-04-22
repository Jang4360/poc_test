#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="${CIRCUIT_BREAKER_STATE_FILE:-$ROOT_DIR/.ai/EVALS/retry-log.jsonl}"
SIGNATURE="${1:-}"
WINDOW_MINUTES="${CIRCUIT_BREAKER_WINDOW_MINUTES:-30}"
THRESHOLD="${CIRCUIT_BREAKER_THRESHOLD:-3}"

if [[ -z "$SIGNATURE" ]]; then
  echo "usage: scripts/check-circuit-breaker.sh <failure signature>" >&2
  exit 1
fi

python3 - <<'PY' "$STATE_FILE" "$SIGNATURE" "$WINDOW_MINUTES" "$THRESHOLD"
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

path = Path(sys.argv[1])
signature = sys.argv[2]
window_minutes = int(sys.argv[3])
threshold = int(sys.argv[4])
now = datetime.now(timezone.utc)
window_start = now - timedelta(minutes=window_minutes)

count = 0
if path.exists():
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            ts = item.get("timestamp")
            sig = item.get("signature")
            if not ts or sig != signature:
                continue
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt >= window_start:
                count += 1
        except Exception:
            continue

if count >= threshold:
    print(f"circuit-breaker: open for signature '{signature}' with {count} recent failures")
    sys.exit(2)

print(f"circuit-breaker: ok for signature '{signature}' with {count} recent failures")
PY
