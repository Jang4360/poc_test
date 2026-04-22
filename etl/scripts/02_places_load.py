from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.common.db import connect
from etl.scripts._shared import build_parser, csv_dict_reader, is_blank, print_stage_banner, print_summary


DEFAULT_PLACES_CSV = ROOT_DIR / "etl" / "data" / "raw" / "place_merged_broad_category_final.csv"


def parse_place_row(row: dict[str, str]) -> tuple[int, str, str, str | None, str, str | None]:
    place_id = int(str(row["placeId"]).strip())
    name = str(row["name"]).strip()
    category = str(row["category"]).strip()
    point_wkt = str(row["point"]).strip()
    if not name or not category or not point_wkt:
        raise ValueError("place row is missing one of name/category/point")
    address = str(row.get("address", "")).strip() or None
    provider_place_id = str(row.get("providerPlaceId", "")).strip() or None
    return place_id, name, category, address, point_wkt, provider_place_id


def load_place_rows(csv_path: Path) -> tuple[list[tuple[int, str, str, str | None, str, str | None]], int]:
    rows: list[tuple[int, str, str, str | None, str, str | None]] = []
    skipped = 0
    for i, raw in enumerate(csv_dict_reader(csv_path), start=2):
        try:
            rows.append(parse_place_row(raw))
        except (ValueError, KeyError) as e:
            skipped += 1
            print(f"  [SKIP] row {i}: {e}", file=sys.stderr)
    return rows, skipped


def upsert_places(rows: list[tuple[int, str, str, str | None, str, str | None]]) -> None:
    from psycopg2.extras import execute_values

    with connect() as connection:
        with connection.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO places ("placeId", "name", "category", "address", "point", "providerPlaceId")
                VALUES %s
                ON CONFLICT ("placeId") DO UPDATE
                SET "name" = EXCLUDED."name",
                    "category" = EXCLUDED."category",
                    "address" = EXCLUDED."address",
                    "point" = EXCLUDED."point",
                    "providerPlaceId" = EXCLUDED."providerPlaceId"
                """,
                rows,
                template="(%s, %s, %s, %s, ST_GeomFromText(%s, 4326), %s)",
                page_size=1000,
            )
        connection.commit()


def main() -> int:
    parser = build_parser("Load canonical place CSV data into places.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_PLACES_CSV, help="Path to the canonical places CSV.")
    args = parser.parse_args()

    print_stage_banner("02_places_load.py", str(args.csv.relative_to(ROOT_DIR)))
    if not args.csv.exists():
        parser.error(f"CSV file does not exist: {args.csv}")

    rows, skipped = load_place_rows(args.csv)
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

    upsert_places(rows)
    print("- status: places upsert complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
