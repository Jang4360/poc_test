#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/verify.sh"

echo "smoke: validating docker compose configuration"
docker compose -f "$ROOT_DIR/docker-compose.yml" config >/dev/null

echo "smoke: running backend tests"
(cd "$ROOT_DIR/poc" && ./gradlew test --no-daemon)

if [[ -d "$ROOT_DIR/etl/tests" ]]; then
  echo "smoke: running etl unit tests"
  python -m unittest discover -s "$ROOT_DIR/etl/tests" -p 'test_*.py'
fi

echo "smoke: checking canonical place CSV selection"
python3 - <<'PY' "$ROOT_DIR"
import csv
import sys
from pathlib import Path

root = Path(sys.argv[1])
raw = root / "etl" / "data" / "raw"

def count_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        return sum(1 for _ in reader)

base = raw / "place_merged_final.csv"
canonical = raw / "place_merged_broad_category_final.csv"
print(f"smoke: place_merged_final.csv rows={count_rows(base)}")
print(f"smoke: place_merged_broad_category_final.csv rows={count_rows(canonical)}")
PY

echo "smoke: ok"
