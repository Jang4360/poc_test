#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="${RETRY_LOG_FILE:-$ROOT_DIR/.ai/EVALS/retry-log.jsonl}"
SIGNATURE="${1:-}"
OUTCOME="${2:-failed}"

if [[ -z "$SIGNATURE" ]]; then
  echo "usage: scripts/record-retry.sh <failure signature> [outcome]" >&2
  exit 1
fi

python3 - <<'PY' "$STATE_FILE" "$SIGNATURE" "$OUTCOME"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
record = {
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "signature": sys.argv[2],
    "outcome": sys.argv[3],
}
with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=True) + "\n")
PY

"$ROOT_DIR/scripts/update-metrics.sh" >/dev/null
echo "retry recorded: $SIGNATURE"

set +e
"$ROOT_DIR/scripts/check-circuit-breaker.sh" "$SIGNATURE"
status=$?
set -e

if [[ "$status" -eq 2 ]]; then
  echo "next-step: invoke learn immediately in this same pass — signature='$SIGNATURE' — do not retry this path again"
  exit 2
fi

exit "$status"
