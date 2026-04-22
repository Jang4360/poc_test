from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
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
ROUTE_LIST_PATH = "busInfo"


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


def normalize_low_floor_flag(value: Any) -> bool:
    normalized = str(value).strip()
    if not normalized:
        return False
    if "저상" in normalized:
        return True
    return normalized.upper() in {"Y", "1", "TRUE", "YES", "LOW", "LOW_FLOOR"}


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
    items = []
    for item in root.findall(".//item"):
        rows = {child.tag: (child.text or "").strip() for child in item}
        if rows:
            items.append(rows)
    return items


def extract_route_row(item: dict[str, Any]) -> tuple[str, str, bool]:
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
    raw_flag = (
        item.get("hasLowFloor")
        or item.get("lowFloor")
        or item.get("lowfloor")
        or item.get("lowplate")
        or item.get("lowPlate")
        or item.get("lowFloorYn")
        or item.get("LOW_FLOOR_YN")
        or item.get("bustype")
    )
    if not route_id or not route_no:
        raise BimsLoadError(f"Could not extract route identity from BIMS item keys: {sorted(item.keys())}")
    return str(route_id).strip(), str(route_no).strip(), normalize_low_floor_flag(raw_flag)


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


def normalize_route_rows(items: list[dict[str, Any]]) -> tuple[list[tuple[str, str, bool]], int]:
    deduped: dict[str, tuple[str, str, bool]] = {}
    low_floor_field_hits = 0
    for item in items:
        row = extract_route_row(item)
        if any(
            key in item
            for key in ("hasLowFloor", "lowFloor", "lowfloor", "lowplate", "lowPlate", "lowFloorYn", "LOW_FLOOR_YN", "bustype")
        ):
            low_floor_field_hits += 1
        deduped[row[0]] = row
    if low_floor_field_hits == 0:
        raise BimsLoadError("BIMS route payload did not expose any low-floor field.")
    return list(deduped.values()), len(items) - len(deduped)


def upsert_bus_routes(rows: list[tuple[str, str, bool]]) -> None:
    from psycopg2.extras import execute_values

    with connect() as connection:
        with connection.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO low_floor_bus_routes ("routeId", "routeNo", "hasLowFloor")
                VALUES %s
                ON CONFLICT ("routeId") DO UPDATE
                SET "routeNo" = EXCLUDED."routeNo",
                    "hasLowFloor" = EXCLUDED."hasLowFloor"
                """,
                rows,
                template="(%s, %s, %s)",
                page_size=1000,
            )
        connection.commit()


def main() -> int:
    parser = build_parser("Sync low-floor bus catalog data from Busan BIMS into low_floor_bus_routes.")
    args = parser.parse_args()

    print_stage_banner("06_bims_bus_load.py", "BUSAN_BIMS_API_BASE_URL")
    service_key, base_url = load_bims_config()
    items = fetch_bims_route_items(service_key, base_url)
    rows, duplicates = normalize_route_rows(items)
    print_summary(
        [
            ("api_rows", len(items)),
            ("distinct_routes", len(rows)),
            ("duplicate_route_ids", duplicates),
            ("low_floor_routes", sum(1 for _, _, has_low_floor in rows if has_low_floor)),
        ]
    )
    if args.dry_run:
        print("- action: fetched and validated remote payload only")
        return 0

    upsert_bus_routes(rows)
    print("- status: low_floor_bus_routes upsert complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
