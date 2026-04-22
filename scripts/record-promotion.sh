#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_FILE="${PROMOTION_LOG_FILE:-$ROOT_DIR/.ai/EVALS/promotion-log.jsonl}"
DESTINATION="${1:-}"
REASON="${2:-}"
ARTIFACT="${3:-}"
SOURCE="${4:-manual}"

if [[ -z "$DESTINATION" || -z "$REASON" || -z "$ARTIFACT" ]]; then
  echo "usage: scripts/record-promotion.sh <destination> <reason> <artifact> [source]" >&2
  exit 1
fi

python3 - <<'PY' "$STATE_FILE" "$DESTINATION" "$REASON" "$ARTIFACT" "$SOURCE"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
record = {
    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "destination": sys.argv[2],
    "reason": sys.argv[3],
    "artifact": sys.argv[4],
    "source": sys.argv[5],
}
with path.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, ensure_ascii=True) + "\n")
PY

"$ROOT_DIR/scripts/update-metrics.sh" >/dev/null
echo "promotion recorded: $DESTINATION -> $ARTIFACT"
