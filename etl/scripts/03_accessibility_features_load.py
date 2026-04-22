from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.common.db import connect
from etl.scripts._shared import (
    build_parser,
    csv_dict_reader,
    normalize_bool,
    print_stage_banner,
    print_summary,
)


DEFAULT_FEATURES_CSV = ROOT_DIR / "etl" / "data" / "raw" / "place_accessibility_features_merged_final.csv"


def parse_feature_row(row: dict[str, str]) -> tuple[int, int, str, bool]:
    feature_id = int(str(row["id"]).strip())
    place_id = int(str(row["placeId"]).strip())
    feature_type = str(row["featureType"]).strip()
    if not feature_type:
        raise ValueError("featureType is blank")
    return feature_id, place_id, feature_type, normalize_bool(row.get("isAvailable"))


def load_feature_rows(csv_path: Path) -> tuple[list[tuple[int, int, str, bool]], int]:
    rows: list[tuple[int, int, str, bool]] = []
    skipped = 0
    for i, raw in enumerate(csv_dict_reader(csv_path), start=2):
        try:
            rows.append(parse_feature_row(raw))
        except (ValueError, KeyError) as e:
            skipped += 1
            print(f"  [SKIP] row {i}: {e}", file=sys.stderr)
    return rows, skipped


def upsert_features(rows: list[tuple[int, int, str, bool]]) -> None:
    from psycopg2.extras import execute_values

    with connect() as connection:
        with connection.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO place_accessibility_features ("id", "placeId", "featureType", "isAvailable")
                VALUES %s
                ON CONFLICT ("id") DO UPDATE
                SET "placeId" = EXCLUDED."placeId",
                    "featureType" = EXCLUDED."featureType",
                    "isAvailable" = EXCLUDED."isAvailable"
                """,
                rows,
                template="(%s, %s, %s, %s)",
                page_size=1000,
            )
        connection.commit()


def main() -> int:
    parser = build_parser("Load place accessibility features into place_accessibility_features.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_FEATURES_CSV, help="Path to the place accessibility CSV.")
    args = parser.parse_args()

    print_stage_banner(
        "03_accessibility_features_load.py",
        str(args.csv.relative_to(ROOT_DIR)),
    )
    if not args.csv.exists():
        parser.error(f"CSV file does not exist: {args.csv}")

    rows, skipped = load_feature_rows(args.csv)
    print_summary(
        [
            ("rows_read", len(rows) + skipped),
            ("rows_valid", len(rows)),
            ("rows_skipped", skipped),
        ]
    )
    if args.dry_run:
        print("- action: validated input only")
        return 0

    upsert_features(rows)
    print("- status: place_accessibility_features upsert complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
