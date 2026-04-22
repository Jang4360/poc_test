from __future__ import annotations

import csv
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.common.db import connect
from etl.scripts._shared import build_parser, print_stage_banner, print_summary


DEFAULT_BIMS_BASE_URL = "https://apis.data.go.kr/6260000/BusanBIMS"
DEFAULT_ROUTES_CSV = ROOT_DIR / "etl" / "data" / "raw" / "부산광역시_시내버스 업체별 연도별 버스 등록대수_20260330.csv"
DEFAULT_REPORTS_DIR = ROOT_DIR / "etl" / "reports"
ROUTE_LIST_PATH = "busInfo"
STATIC_CSV_ENCODING = "cp949"
STATIC_CSV_REQUIRED_HEADERS = ("인가노선", "운행구분")


class BimsLoadError(RuntimeError):
    pass


def load_bims_config() -> tuple[str, str]:
    decoded_service_key = os.getenv("BUSAN_BIMS_SERVICE_KEY_DECODING")
    encoded_service_key = (
        os.getenv("BUSAN_BIMS_SERVICE_KEY_ENCODING")
        or os.getenv("BUSAN_BIMS_SERVICE_KEY")
        or os.getenv("BIMS_SERVICE_KEY")
    )
    service_key = decoded_service_key or (unquote(encoded_service_key) if encoded_service_key else None)
    base_url = (
        os.getenv("BUSAN_BIMS_API_BASE_URL")
        or os.getenv("BIMS_BASE_URL")
        or DEFAULT_BIMS_BASE_URL
    )
    if not service_key:
        raise BimsLoadError("Missing BUSAN_BIMS service key in .env.")
    return service_key, base_url.rstrip("/")


def normalize_exact_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_json_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        current = payload
        for key in ("response", "body", "items"):
            next_value = current.get(key)
            if next_value is None:
                break
            current = next_value
        if isinstance(current, dict):
            item = current.get("item")
            if item is None:
                return []
            if isinstance(item, list):
                return [row for row in item if isinstance(row, dict)]
            if isinstance(item, dict):
                return [item]
        elif isinstance(current, list):
            return [row for row in current if isinstance(row, dict)]
    return []


def parse_xml_items(text: str) -> list[dict[str, str]]:
    root = ET.fromstring(text)
    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        rows = {child.tag: normalize_exact_text(child.text or "") for child in item}
        if rows:
            items.append(rows)
    return items


def extract_catalog_route_identity(item: dict[str, Any]) -> tuple[str, str]:
    route_id = (
        item.get("routeId")
        or item.get("routeid")
        or item.get("lineid")
        or item.get("busRouteId")
        or item.get("busrouteid")
    )
    route_no = (
        item.get("routeNo")
        or item.get("routeno")
        or item.get("lineNo")
        or item.get("lineno")
        or item.get("busNo")
        or item.get("buslinenum")
    )
    route_id_text = normalize_exact_text(route_id)
    route_no_text = normalize_exact_text(route_no)
    if not route_id_text or not route_no_text:
        raise BimsLoadError(f"Could not extract BIMS route identity from item keys: {sorted(item.keys())}")
    return route_id_text, route_no_text


def fetch_bims_route_items(service_key: str, base_url: str) -> list[dict[str, Any]]:
    session = requests.Session()
    # The current Busan BIMS busInfo endpoint ignores pageNo and returns the full
    # route catalog on the first response, so repeated paging loops never terminate.
    response = session.get(
        f"{base_url}/{ROUTE_LIST_PATH}",
        params={"serviceKey": service_key},
        timeout=20,
    )
    response.raise_for_status()
    try:
        items = parse_json_items(response.json())
    except json.JSONDecodeError:
        items = parse_xml_items(response.text)
    if not items:
        raise BimsLoadError("BIMS route list returned no items.")
    return items


def build_bims_route_catalog(items: list[dict[str, Any]]) -> tuple[dict[str, str], int]:
    catalog: dict[str, str] = {}
    duplicate_route_nos = 0
    conflicts: dict[str, set[str]] = {}
    for item in items:
        route_id, route_no = extract_catalog_route_identity(item)
        existing = catalog.get(route_no)
        if existing is None:
            catalog[route_no] = route_id
            continue
        if existing == route_id:
            duplicate_route_nos += 1
            continue
        conflicts.setdefault(route_no, {existing}).add(route_id)
    if conflicts:
        samples = {route_no: sorted(route_ids) for route_no, route_ids in sorted(conflicts.items())[:10]}
        raise BimsLoadError(f"Conflicting BIMS routeId values for identical routeNo: {samples}")
    return catalog, duplicate_route_nos


def load_static_route_aggregates(csv_path: Path) -> tuple[dict[str, dict[str, int]], int, int]:
    with csv_path.open("r", encoding=STATIC_CSV_ENCODING, newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        missing_headers = [header for header in STATIC_CSV_REQUIRED_HEADERS if header not in headers]
        if missing_headers:
            raise BimsLoadError(f"Static low-floor CSV is missing required headers: {missing_headers}")

        aggregates: dict[str, dict[str, int]] = {}
        source_row_count = 0
        skipped_rows = 0
        for row_index, row in enumerate(reader, start=2):
            source_row_count += 1
            route_no = normalize_exact_text(row.get("인가노선"))
            run_type = normalize_exact_text(row.get("운행구분"))
            if not route_no or not run_type:
                skipped_rows += 1
                print(f"  [SKIP] row {row_index}: missing 인가노선 or 운행구분", file=sys.stderr)
                continue
            stats = aggregates.setdefault(route_no, {"lowFloorVehicleCount": 0, "totalVehicleCount": 0})
            stats["totalVehicleCount"] += 1
            if run_type == "저상":
                stats["lowFloorVehicleCount"] += 1
    return aggregates, source_row_count, skipped_rows


def build_low_floor_rows(
    aggregates: dict[str, dict[str, int]],
    route_catalog: dict[str, str],
) -> tuple[list[tuple[str, str, bool]], list[dict[str, Any]], int]:
    rows: list[tuple[str, str, bool]] = []
    report_routes: list[dict[str, Any]] = []
    unmatched_count = 0
    for route_no in sorted(aggregates):
        stats = aggregates[route_no]
        low_floor_vehicle_count = int(stats["lowFloorVehicleCount"])
        total_vehicle_count = int(stats["totalVehicleCount"])
        route_id = route_catalog.get(route_no)
        has_low_floor = low_floor_vehicle_count > 0
        report_row: dict[str, Any] = {
            "routeNo": route_no,
            "routeId": route_id,
            "hasLowFloor": has_low_floor,
            "lowFloorVehicleCount": low_floor_vehicle_count,
            "totalVehicleCount": total_vehicle_count,
        }
        if route_id is None:
            unmatched_count += 1
            report_row["unmatchedReason"] = "NO_BIMS_ROUTE_ID_MATCH"
        else:
            rows.append((route_id, route_no, has_low_floor))
        report_routes.append(report_row)
    return rows, report_routes, unmatched_count


def report_path_for(run_date: date) -> Path:
    return DEFAULT_REPORTS_DIR / f"low_floor_bus_routes_{run_date.isoformat()}.json"


def summarize_buslinenum_format(route_catalog: dict[str, str]) -> dict[str, Any]:
    route_nos = sorted(route_catalog)
    return {
        "sample": route_nos[:10],
        "contains_suffix_beon": any(route_no.endswith("번") for route_no in route_nos),
    }


def build_report_payload(
    csv_path: Path,
    aggregates: dict[str, dict[str, int]],
    route_catalog: dict[str, str],
    report_routes: list[dict[str, Any]],
    source_row_count: int,
    skipped_rows: int,
    status: str,
    error: str | None = None,
    unmatched_skip_applied: bool = False,
) -> dict[str, Any]:
    matched_count = sum(1 for route in report_routes if route.get("routeId"))
    unmatched_count = len(report_routes) - matched_count
    return {
        "status": status,
        "error": error,
        "sourceCsvPath": str(csv_path),
        "sourceCsvEncoding": STATIC_CSV_ENCODING,
        "sourceRowCount": source_row_count,
        "sourceRowsSkipped": skipped_rows,
        "distinctRouteCount": len(aggregates),
        "matchedRouteCount": matched_count,
        "unmatchedRouteCount": unmatched_count,
        "unmatchedSkipApplied": unmatched_skip_applied,
        "bimsRouteCount": len(route_catalog),
        "bimsBusLineNumFormat": summarize_buslinenum_format(route_catalog),
        "routes": report_routes,
    }


def write_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def should_fail_on_unmatched(unmatched_count: int, allow_unmatched_skip: bool, dry_run: bool) -> bool:
    return unmatched_count > 0 and not allow_unmatched_skip and not dry_run


def resolve_low_floor_table_layout(columns: list[str]) -> tuple[str, str, str]:
    actual = set(columns)
    camel_case = ("routeId", "routeNo", "hasLowFloor")
    snake_case = ("route_id", "route_no", "has_low_floor")
    if set(camel_case).issubset(actual):
        return camel_case
    if set(snake_case).issubset(actual):
        return snake_case
    raise BimsLoadError(f"Unsupported low_floor_bus_routes columns: {sorted(actual)}")


def upsert_bus_routes(rows: list[tuple[str, str, bool]]) -> None:
    from psycopg2.extras import execute_values

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'low_floor_bus_routes'
                ORDER BY ordinal_position
                """
            )
            route_id_column, route_no_column, has_low_floor_column = resolve_low_floor_table_layout(
                [row[0] for row in cursor.fetchall()]
            )
            execute_values(
                cursor,
                f"""
                INSERT INTO low_floor_bus_routes ("{route_id_column}", "{route_no_column}", "{has_low_floor_column}")
                VALUES %s
                ON CONFLICT ("{route_id_column}") DO UPDATE
                SET "{route_no_column}" = EXCLUDED."{route_no_column}",
                    "{has_low_floor_column}" = EXCLUDED."{has_low_floor_column}"
                """,
                rows,
                template="(%s, %s, %s)",
                page_size=1000,
            )
        connection.commit()


def format_source_name(csv_path: Path) -> str:
    try:
        return str(csv_path.relative_to(ROOT_DIR))
    except ValueError:
        return str(csv_path)


def main() -> int:
    parser = build_parser(
        "Load low-floor bus route catalog data from the static bus registration CSV plus Busan BIMS routeId mapping."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_ROUTES_CSV, help="Path to the static low-floor routes CSV.")
    parser.add_argument(
        "--allow-unmatched-skip",
        action="store_true",
        help="Skip unmatched routeNo values instead of failing when BIMS routeId mapping is missing.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional path for the JSON route report. Defaults to etl/reports/low_floor_bus_routes_<date>.json.",
    )
    args = parser.parse_args()

    print_stage_banner("06_bims_bus_load.py", f"{format_source_name(args.csv)} + BUSAN_BIMS_API_BASE_URL")
    if not args.csv.exists():
        parser.error(f"CSV file does not exist: {args.csv}")

    service_key, base_url = load_bims_config()
    aggregates, source_row_count, skipped_rows = load_static_route_aggregates(args.csv)
    items = fetch_bims_route_items(service_key, base_url)
    route_catalog, duplicate_route_nos = build_bims_route_catalog(items)
    rows, report_routes, unmatched_count = build_low_floor_rows(aggregates, route_catalog)
    report_path = args.report_path or report_path_for(date.today())
    low_floor_routes = sum(1 for _, _, has_low_floor in rows if has_low_floor)
    print_summary(
        [
            ("source_rows", source_row_count),
            ("source_rows_skipped", skipped_rows),
            ("distinct_routes", len(aggregates)),
            ("matched_routes", len(rows)),
            ("unmatched_routes", unmatched_count),
            ("bims_routes", len(route_catalog)),
            ("duplicate_bims_route_nos", duplicate_route_nos),
            ("low_floor_routes", low_floor_routes),
        ]
    )
    if args.dry_run:
        report_payload = build_report_payload(
            args.csv,
            aggregates,
            route_catalog,
            report_routes,
            source_row_count,
            skipped_rows,
            status="dry_run",
            unmatched_skip_applied=args.allow_unmatched_skip and unmatched_count > 0,
        )
        write_report(report_path, report_payload)
        print(f"- report_path: {report_path}")
        print("- action: validated static CSV plus BIMS route catalog mapping only")
        return 0

    if should_fail_on_unmatched(unmatched_count, args.allow_unmatched_skip, args.dry_run):
        error_message = (
            f"{unmatched_count} routes from the static CSV could not be matched to BIMS routeId. "
            "Run again with --allow-unmatched-skip only if the gap is explicitly accepted."
        )
        report_payload = build_report_payload(
            args.csv,
            aggregates,
            route_catalog,
            report_routes,
            source_row_count,
            skipped_rows,
            status="failed",
            error=error_message,
            unmatched_skip_applied=False,
        )
        write_report(report_path, report_payload)
        print(f"- report_path: {report_path}")
        raise BimsLoadError(error_message)

    try:
        upsert_bus_routes(rows)
    except Exception as exc:
        report_payload = build_report_payload(
            args.csv,
            aggregates,
            route_catalog,
            report_routes,
            source_row_count,
            skipped_rows,
            status="failed",
            error=str(exc),
            unmatched_skip_applied=args.allow_unmatched_skip and unmatched_count > 0,
        )
        write_report(report_path, report_payload)
        print(f"- report_path: {report_path}")
        raise

    report_payload = build_report_payload(
        args.csv,
        aggregates,
        route_catalog,
        report_routes,
        source_row_count,
        skipped_rows,
        status="upserted",
        unmatched_skip_applied=args.allow_unmatched_skip and unmatched_count > 0,
    )
    write_report(report_path, report_payload)
    print(f"- report_path: {report_path}")
    print("- status: low_floor_bus_routes upsert complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
