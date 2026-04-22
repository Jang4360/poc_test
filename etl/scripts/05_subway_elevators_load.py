from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.common.db import connect
from etl.scripts._shared import build_parser, csv_dict_reader, is_blank, print_stage_banner, print_summary


DEFAULT_ELEVATORS_CSV = ROOT_DIR / "etl" / "data" / "raw" / "subway_station_elevators_erd_ready.csv"


def parse_elevator_row(row: dict[str, str]) -> tuple[int, str, str, str, str | None, str]:
    elevator_id = int(str(row["elevatorId"]).strip())
    station_id = str(row["stationId"]).strip()
    station_name = str(row["stationName"]).strip()
    line_name = str(row["lineName"]).strip()
    entrance_no = str(row.get("entranceNo", "")).strip() or None
    point_wkt = str(row["point"]).strip()
    if not station_id or not station_name or not line_name or not point_wkt:
        raise ValueError("required elevator fields are blank")
    return elevator_id, station_id, station_name, line_name, entrance_no, point_wkt


def dedupe_elevator_rows(
    rows: list[tuple[int, str, str, str, str | None, str]]
) -> tuple[list[tuple[int, str, str, str, str | None, str]], int]:
    deduped: dict[tuple[str, str | None, str], tuple[int, str, str, str, str | None, str]] = {}
    duplicates = 0
    for row in rows:
        natural_key = (row[1], row[4], row[5])
        current = deduped.get(natural_key)
        if current is None or row[0] < current[0]:
            if current is not None:
                duplicates += 1
            deduped[natural_key] = row
        else:
            duplicates += 1
    return list(deduped.values()), duplicates


def load_elevator_rows(csv_path: Path) -> tuple[list[tuple[int, str, str, str, str | None, str]], int, int]:
    parsed: list[tuple[int, str, str, str, str | None, str]] = []
    skipped = 0
    for i, raw in enumerate(csv_dict_reader(csv_path), start=2):
        try:
            parsed.append(parse_elevator_row(raw))
        except (ValueError, KeyError) as e:
            skipped += 1
            print(f"  [SKIP] row {i}: {e}", file=sys.stderr)
    deduped, duplicates = dedupe_elevator_rows(parsed)
    return deduped, skipped, duplicates


def upsert_elevators(rows: list[tuple[int, str, str, str, str | None, str]]) -> None:
    from psycopg2.extras import execute_values

    with connect() as connection:
        with connection.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO subway_station_elevators
                    ("elevatorId", "stationId", "stationName", "lineName", "entranceNo", "point")
                VALUES %s
                ON CONFLICT ("elevatorId") DO UPDATE
                SET "stationId" = EXCLUDED."stationId",
                    "stationName" = EXCLUDED."stationName",
                    "lineName" = EXCLUDED."lineName",
                    "entranceNo" = EXCLUDED."entranceNo",
                    "point" = EXCLUDED."point"
                """,
                rows,
                template="(%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))",
                page_size=1000,
            )
        connection.commit()


def main() -> int:
    parser = build_parser("Load subway elevator entrances into subway_station_elevators.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_ELEVATORS_CSV, help="Path to the subway elevator CSV.")
    args = parser.parse_args()

    print_stage_banner(
        "05_subway_elevators_load.py",
        str(args.csv.relative_to(ROOT_DIR)),
    )
    if not args.csv.exists():
        parser.error(f"CSV file does not exist: {args.csv}")

    rows, skipped, duplicates = load_elevator_rows(args.csv)
    print_summary(
        [
            ("rows_read", len(rows) + skipped + duplicates),
            ("rows_valid", len(rows)),
            ("rows_skipped", skipped),
            ("natural_key_duplicates", duplicates),
        ]
    )
    if args.dry_run:
        print("- action: validated input only")
        return 0

    upsert_elevators(rows)
    print("- status: subway_station_elevators upsert complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
