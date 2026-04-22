#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/update-progress.sh"
"$ROOT_DIR/scripts/update-metrics.sh"
"$ROOT_DIR/scripts/sync-adapters.sh"
"$ROOT_DIR/scripts/verify.sh"
"$ROOT_DIR/scripts/score.sh"
"$ROOT_DIR/scripts/dashboard.sh"
