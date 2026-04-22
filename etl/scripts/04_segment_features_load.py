from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.common.db import connect
from etl.scripts._shared import build_parser, csv_dict_reader, is_blank, print_stage_banner, print_summary


DEFAULT_AUDIO_CSV = ROOT_DIR / "etl" / "data" / "raw" / "stg_audio_signals_ready.csv"
DEFAULT_CROSSWALK_CSV = ROOT_DIR / "etl" / "data" / "raw" / "stg_crosswalks_ready.csv"
DEFAULT_SLOPE_CSV = ROOT_DIR / "etl" / "data" / "raw" / "slope_analysis_staging.csv"
DEFAULT_ELEVATOR_CSV = ROOT_DIR / "etl" / "data" / "raw" / "subway_station_elevators_erd_ready.csv"
DEFAULT_MAX_DISTANCE_METERS = 15.0
DEFAULT_REVIEW_DISTANCE_METERS = 30.0


def parse_numeric(value: object) -> float | None:
    try:
        raw = str(value).strip()
        if not raw:
            return None
        return float(raw)
    except Exception:
        return None


def meters_to_degrees(distance_m: float) -> float:
    # Equator-based approximation (111,320 m/°). ~0.4% error at Busan (35°N).
    # Used only for bbox pre-filtering; geography ST_DWithin enforces real distance.
    return distance_m / 111_320.0


def is_point_wkt(value: object) -> bool:
    return str(value).strip().upper().startswith("POINT(")


def is_polygon_wkt(value: object) -> bool:
    normalized = str(value).strip().upper()
    return normalized.startswith("POLYGON(") or normalized.startswith("MULTIPOLYGON(")


def normalize_audio_row(row: dict[str, str]) -> tuple[str, str, str, bool] | None:
    source_id = str(row.get("sourceId", "")).strip()
    point_wkt = str(row.get("point", "")).strip()
    audio_state = str(row.get("audioSignalState", "")).strip().upper() or "UNKNOWN"
    stat = str(row.get("stat", "")).strip()
    if not source_id or not is_point_wkt(point_wkt):
        return None
    should_update = stat == "정상동작" and audio_state in {"YES", "NO"}
    return source_id, point_wkt, audio_state, should_update


def normalize_crosswalk_row(row: dict[str, str]) -> tuple[str, str, str, float | None] | None:
    source_id = str(row.get("sourceId", "")).strip()
    point_wkt = str(row.get("point", "")).strip()
    crossing_state = str(row.get("crossingState", "")).strip().upper() or "UNKNOWN"
    if not source_id or not is_point_wkt(point_wkt):
        return None
    return source_id, point_wkt, crossing_state, parse_numeric(row.get("widthMeter"))


def normalize_slope_row(row: dict[str, str], index: int) -> tuple[str, str, float | None, float | None] | None:
    polygon_wkt = str(row.get("geometry_wkt_4326", "")).strip()
    if not is_polygon_wkt(polygon_wkt):
        return None
    return (
        f"slope:{index}",
        polygon_wkt,
        parse_numeric(row.get("metric_mean")),
        parse_numeric(row.get("width_meter")),
    )


def normalize_elevator_row(row: dict[str, str]) -> tuple[str, str] | None:
    elevator_id = str(row.get("elevatorId", "")).strip()
    point_wkt = str(row.get("point", "")).strip()
    if not elevator_id or not is_point_wkt(point_wkt):
        return None
    return f"elevator:{elevator_id}", point_wkt


def classify_distance_band(distance_m: float | None, max_distance_m: float, review_distance_m: float) -> str:
    if distance_m is None:
        return "UNMATCHED"
    if distance_m <= max_distance_m:
        return "AUTO_UPDATE"
    if distance_m <= review_distance_m:
        return "REVIEW_REQUIRED"
    return "UNMATCHED"


def load_audio_rows(csv_path: Path) -> tuple[list[tuple[str, str, str, bool]], int]:
    rows: list[tuple[str, str, str, bool]] = []
    skipped = 0
    for raw in csv_dict_reader(csv_path):
        normalized = normalize_audio_row(raw)
        if normalized is None:
            skipped += 1
            continue
        rows.append(normalized)
    return rows, skipped


def load_crosswalk_rows(csv_path: Path) -> tuple[list[tuple[str, str, str, float | None]], int]:
    rows: list[tuple[str, str, str, float | None]] = []
    skipped = 0
    for raw in csv_dict_reader(csv_path):
        normalized = normalize_crosswalk_row(raw)
        if normalized is None:
            skipped += 1
            continue
        rows.append(normalized)
    return rows, skipped


def load_slope_rows(csv_path: Path) -> tuple[list[tuple[str, str, float | None, float | None]], int]:
    rows: list[tuple[str, str, float | None, float | None]] = []
    skipped = 0
    for index, raw in enumerate(csv_dict_reader(csv_path), start=1):
        normalized = normalize_slope_row(raw, index)
        if normalized is None:
            skipped += 1
            continue
        rows.append(normalized)
    return rows, skipped


def load_elevator_rows(csv_path: Path) -> tuple[list[tuple[str, str]], int]:
    rows: list[tuple[str, str]] = []
    skipped = 0
    for raw in csv_dict_reader(csv_path):
        normalized = normalize_elevator_row(raw)
        if normalized is None:
            skipped += 1
            continue
        rows.append(normalized)
    return rows, skipped


def bulk_insert_values(cursor, sql: str, rows: list[tuple], template: str, page_size: int = 1000) -> None:
    from psycopg2.extras import execute_values

    if not rows:
        return
    execute_values(cursor, sql, rows, template=template, page_size=page_size)


def ensure_road_segments_exist(cursor) -> None:
    cursor.execute('SELECT COUNT(*) FROM road_segments')
    if cursor.fetchone()[0] == 0:
        raise RuntimeError("road_segments is empty. Run 02_osm_schema_and_network_load first.")


def reset_segment_enrichment(cursor) -> None:
    cursor.execute(
        """
        UPDATE road_segments
        SET "audioSignalState" = 'UNKNOWN',
            "crossingState" = 'UNKNOWN',
            "avgSlopePercent" = NULL,
            "widthMeter" = NULL,
            "elevatorState" = 'UNKNOWN'
        """
    )
    cursor.execute(
        """
        DELETE FROM segment_features
        WHERE "featureType" IN ('AUDIO_SIGNAL', 'CROSSWALK', 'SLOPE_ANALYSIS', 'SUBWAY_ELEVATOR')
        """
    )




def load_audio_features(cursor, rows: list[tuple[str, str, str, bool]], max_distance_m: float) -> dict[str, int]:
    max_distance_deg = meters_to_degrees(max_distance_m)
    cursor.execute(
        """
        CREATE TEMP TABLE tmp_audio_signals (
            source_id TEXT PRIMARY KEY,
            geom geometry(POINT, 4326) NOT NULL,
            audio_state TEXT NOT NULL,
            should_update BOOLEAN NOT NULL
        ) ON COMMIT DROP
        """
    )
    bulk_insert_values(
        cursor,
        "INSERT INTO tmp_audio_signals (source_id, geom, audio_state, should_update) VALUES %s",
        rows,
        template="(%s, ST_GeomFromText(%s, 4326), %s, %s)",
    )
    cursor.execute(
        f"""
        CREATE TEMP TABLE tmp_audio_matched ON COMMIT DROP AS
        WITH candidates AS (
            SELECT
                src.source_id,
                src.geom,
                src.audio_state,
                src.should_update,
                seg."edgeId" AS edge_id,
                ST_Distance(seg."geom"::geography, src.geom::geography) AS distance_m,
                ROW_NUMBER() OVER (
                    PARTITION BY src.source_id
                    ORDER BY ST_Distance(seg."geom"::geography, src.geom::geography), seg."edgeId"
                ) AS rank_no,
                COUNT(*) OVER (PARTITION BY src.source_id) AS candidate_count
            FROM tmp_audio_signals src
            JOIN road_segments seg
              ON seg."geom" && ST_Expand(src.geom, %s)
             AND ST_DWithin(seg."geom", src.geom, %s)
             AND ST_DWithin(seg."geom"::geography, src.geom::geography, %s)
        )
        SELECT source_id, geom, audio_state, should_update, edge_id, distance_m, candidate_count
        FROM candidates
        WHERE rank_no = 1
        """,
        (max_distance_deg, max_distance_deg, max_distance_m),
    )
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM tmp_audio_signals),
            (SELECT COUNT(*) FROM tmp_audio_matched),
            (
                SELECT COUNT(*)
                FROM tmp_audio_signals src
                LEFT JOIN tmp_audio_matched matched ON matched.source_id = src.source_id
                WHERE matched.source_id IS NULL
            ),
            (
                SELECT COUNT(*)
                FROM (
                    SELECT source_id
                    FROM tmp_audio_matched
                    WHERE candidate_count > 1
                    GROUP BY source_id
                ) collisions
            )
        """
    )
    source_count, matched_count, unmatched_count, multi_candidate_count = cursor.fetchone()
    cursor.execute(
        """
        UPDATE road_segments seg
        SET "audioSignalState" = 'YES'
        FROM (
            SELECT DISTINCT edge_id
            FROM tmp_audio_matched
            WHERE should_update = TRUE AND audio_state = 'YES'
        ) updates
        WHERE seg."edgeId" = updates.edge_id
        """
    )
    cursor.execute(
        """
        INSERT INTO segment_features ("edgeId", "featureType", "geom")
        SELECT
            edge_id,
            'AUDIO_SIGNAL',
            geom
        FROM tmp_audio_matched
        """
    )
    return {
        "source_count": int(source_count),
        "matched_count": int(matched_count),
        "unmatched_count": int(unmatched_count),
        "multi_candidate_count": int(multi_candidate_count),
    }


def load_crosswalk_features(cursor, rows: list[tuple[str, str, str, float | None]], max_distance_m: float) -> dict[str, int]:
    max_distance_deg = meters_to_degrees(max_distance_m)
    cursor.execute(
        """
        CREATE TEMP TABLE tmp_crosswalks (
            source_id TEXT PRIMARY KEY,
            geom geometry(POINT, 4326) NOT NULL,
            crossing_state TEXT NOT NULL,
            width_meter DOUBLE PRECISION NULL
        ) ON COMMIT DROP
        """
    )
    bulk_insert_values(
        cursor,
        "INSERT INTO tmp_crosswalks (source_id, geom, crossing_state, width_meter) VALUES %s",
        rows,
        template="(%s, ST_GeomFromText(%s, 4326), %s, %s)",
    )
    cursor.execute(
        """
        CREATE TEMP TABLE tmp_crosswalk_matched ON COMMIT DROP AS
        WITH candidates AS (
            SELECT
                src.source_id,
                src.geom,
                src.crossing_state,
                src.width_meter,
                seg."edgeId" AS edge_id,
                ST_Distance(seg."geom"::geography, src.geom::geography) AS distance_m,
                ROW_NUMBER() OVER (
                    PARTITION BY src.source_id
                    ORDER BY ST_Distance(seg."geom"::geography, src.geom::geography), seg."edgeId"
                ) AS rank_no,
                COUNT(*) OVER (PARTITION BY src.source_id) AS candidate_count
            FROM tmp_crosswalks src
            JOIN road_segments seg
              ON seg."geom" && ST_Expand(src.geom, %s)
             AND ST_DWithin(seg."geom", src.geom, %s)
             AND ST_DWithin(seg."geom"::geography, src.geom::geography, %s)
        )
        SELECT source_id, geom, crossing_state, width_meter, edge_id, distance_m, candidate_count
        FROM candidates
        WHERE rank_no = 1
        """,
        (max_distance_deg, max_distance_deg, max_distance_m),
    )
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM tmp_crosswalks),
            (SELECT COUNT(*) FROM tmp_crosswalk_matched),
            (
                SELECT COUNT(*)
                FROM tmp_crosswalks src
                LEFT JOIN tmp_crosswalk_matched matched ON matched.source_id = src.source_id
                WHERE matched.source_id IS NULL
            ),
            (
                SELECT COUNT(*)
                FROM (
                    SELECT source_id
                    FROM tmp_crosswalk_matched
                    WHERE candidate_count > 1
                    GROUP BY source_id
                ) collisions
            )
        """
    )
    source_count, matched_count, unmatched_count, multi_candidate_count = cursor.fetchone()
    cursor.execute(
        """
        UPDATE road_segments seg
        SET "crossingState" = updates.crossing_state::crossing_state,
            "widthMeter" = COALESCE(seg."widthMeter", updates.width_meter)
        FROM (
            SELECT
                edge_id,
                (ARRAY_AGG(crossing_state ORDER BY
                    CASE crossing_state
                        WHEN 'TRAFFIC_SIGNALS' THEN 2
                        WHEN 'NO'              THEN 1
                        ELSE                       0
                    END DESC
                ))[1] AS crossing_state,
                MAX(width_meter) AS width_meter
            FROM tmp_crosswalk_matched
            GROUP BY edge_id
        ) updates
        WHERE seg."edgeId" = updates.edge_id
        """
    )
    cursor.execute(
        """
        INSERT INTO segment_features ("edgeId", "featureType", "geom")
        SELECT
            edge_id,
            'CROSSWALK',
            geom
        FROM tmp_crosswalk_matched
        """
    )
    return {
        "source_count": int(source_count),
        "matched_count": int(matched_count),
        "unmatched_count": int(unmatched_count),
        "multi_candidate_count": int(multi_candidate_count),
    }


def load_slope_features(cursor, rows: list[tuple[str, str, float | None, float | None]]) -> dict[str, int]:
    cursor.execute(
        """
        CREATE TEMP TABLE tmp_slope_polygons (
            source_id TEXT PRIMARY KEY,
            geom geometry(Geometry, 4326) NOT NULL,
            avg_slope_percent DOUBLE PRECISION NULL,
            width_meter DOUBLE PRECISION NULL
        ) ON COMMIT DROP
        """
    )
    bulk_insert_values(
        cursor,
        "INSERT INTO tmp_slope_polygons (source_id, geom, avg_slope_percent, width_meter) VALUES %s",
        rows,
        template="(%s, ST_GeomFromText(%s, 4326), %s, %s)",
        page_size=500,
    )
    cursor.execute(
        """
        CREATE TEMP TABLE tmp_slope_matched ON COMMIT DROP AS
        SELECT
            src.source_id,
            src.geom,
            src.avg_slope_percent,
            src.width_meter,
            seg."edgeId" AS edge_id
        FROM tmp_slope_polygons src
        JOIN road_segments seg
          ON ST_Intersects(seg."geom", src.geom)
        """
    )
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM tmp_slope_polygons),
            (SELECT COUNT(*) FROM tmp_slope_matched),
            (
                SELECT COUNT(*)
                FROM tmp_slope_polygons src
                LEFT JOIN (
                    SELECT DISTINCT source_id
                    FROM tmp_slope_matched
                ) matched ON matched.source_id = src.source_id
                WHERE matched.source_id IS NULL
            ),
            (
                SELECT COUNT(*)
                FROM (
                    SELECT source_id
                    FROM tmp_slope_matched
                    GROUP BY source_id
                    HAVING COUNT(*) > 1
                ) collisions
            )
        """
    )
    source_count, matched_count, unmatched_count, multi_candidate_count = cursor.fetchone()
    cursor.execute(
        """
        UPDATE road_segments seg
        SET "avgSlopePercent" = updates.avg_slope_percent,
            "widthMeter" = COALESCE(updates.width_meter, seg."widthMeter")
        FROM (
            SELECT
                edge_id,
                AVG(avg_slope_percent) FILTER (WHERE avg_slope_percent IS NOT NULL) AS avg_slope_percent,
                MIN(width_meter) FILTER (WHERE width_meter IS NOT NULL) AS width_meter
            FROM tmp_slope_matched
            GROUP BY edge_id
        ) updates
        WHERE seg."edgeId" = updates.edge_id
        """
    )
    cursor.execute(
        """
        INSERT INTO segment_features ("edgeId", "featureType", "geom")
        SELECT
            edge_id,
            'SLOPE_ANALYSIS',
            geom
        FROM tmp_slope_matched
        """
    )
    return {
        "source_count": int(source_count),
        "matched_count": int(matched_count),
        "unmatched_count": int(unmatched_count),
        "multi_candidate_count": int(multi_candidate_count),
    }


def load_elevator_features(
    cursor,
    rows: list[tuple[str, str]],
    max_distance_m: float,
    review_distance_m: float,
) -> dict[str, int]:
    review_distance_deg = meters_to_degrees(review_distance_m)
    cursor.execute(
        """
        CREATE TEMP TABLE tmp_subway_elevators (
            source_id TEXT PRIMARY KEY,
            geom geometry(POINT, 4326) NOT NULL
        ) ON COMMIT DROP
        """
    )
    bulk_insert_values(
        cursor,
        "INSERT INTO tmp_subway_elevators (source_id, geom) VALUES %s",
        rows,
        template="(%s, ST_GeomFromText(%s, 4326))",
    )
    cursor.execute(
        """
        CREATE TEMP TABLE tmp_elevator_decisions ON COMMIT DROP AS
        WITH candidates AS (
            SELECT
                src.source_id,
                src.geom,
                seg."edgeId" AS edge_id,
                seg."lengthMeter" AS length_meter,
                ST_Distance(seg."geom"::geography, src.geom::geography) AS distance_m,
                ROW_NUMBER() OVER (
                    PARTITION BY src.source_id
                    ORDER BY
                        ST_Distance(seg."geom"::geography, src.geom::geography),
                        seg."lengthMeter",
                        seg."edgeId"
                ) AS rank_no,
                COUNT(*) OVER (PARTITION BY src.source_id) AS candidate_count
            FROM tmp_subway_elevators src
            JOIN road_segments seg
              ON seg."geom" && ST_Expand(src.geom, %s)
             AND ST_DWithin(seg."geom", src.geom, %s)
             AND ST_DWithin(seg."geom"::geography, src.geom::geography, %s)
        )
        SELECT
            src.source_id,
            src.geom,
            cand.edge_id,
            cand.distance_m,
            COALESCE(cand.candidate_count, 0) AS candidate_count
        FROM tmp_subway_elevators src
        LEFT JOIN candidates cand
          ON cand.source_id = src.source_id
         AND cand.rank_no = 1
        """,
        (review_distance_deg, review_distance_deg, review_distance_m),
    )
    cursor.execute(
        """
        ALTER TABLE tmp_elevator_decisions
        ADD COLUMN match_band TEXT
        """
    )
    cursor.execute(
        """
        UPDATE tmp_elevator_decisions
        SET match_band = CASE
            WHEN edge_id IS NULL THEN 'UNMATCHED'
            WHEN distance_m <= %s THEN 'AUTO_UPDATE'
            WHEN distance_m <= %s THEN 'REVIEW_REQUIRED'
            ELSE 'UNMATCHED'
        END
        """,
        (max_distance_m, review_distance_m),
    )
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM tmp_subway_elevators),
            (SELECT COUNT(*) FROM tmp_elevator_decisions WHERE match_band = 'AUTO_UPDATE'),
            (SELECT COUNT(*) FROM tmp_elevator_decisions WHERE match_band = 'REVIEW_REQUIRED'),
            (SELECT COUNT(*) FROM tmp_elevator_decisions WHERE match_band = 'UNMATCHED'),
            (
                SELECT COUNT(*)
                FROM (
                    SELECT source_id
                    FROM tmp_elevator_decisions
                    WHERE candidate_count > 1
                    GROUP BY source_id
                ) collisions
            )
        """
    )
    source_count, matched_count, review_required_count, unmatched_count, multi_candidate_count = cursor.fetchone()
    cursor.execute(
        """
        UPDATE road_segments seg
        SET "elevatorState" = 'YES'
        FROM (
            SELECT DISTINCT edge_id
            FROM tmp_elevator_decisions
            WHERE match_band = 'AUTO_UPDATE'
        ) updates
        WHERE seg."edgeId" = updates.edge_id
        """
    )
    cursor.execute(
        """
        INSERT INTO segment_features ("edgeId", "featureType", "geom")
        SELECT
            edge_id,
            'SUBWAY_ELEVATOR',
            geom
        FROM tmp_elevator_decisions
        WHERE match_band = 'AUTO_UPDATE'
        """
    )
    return {
        "source_count": int(source_count),
        "matched_count": int(matched_count),
        "review_required_count": int(review_required_count),
        "unmatched_count": int(unmatched_count),
        "multi_candidate_count": int(multi_candidate_count),
    }


def validation_stats(cursor) -> dict[str, int]:
    stats: dict[str, int] = {}
    cursor.execute('SELECT COUNT(*) FROM segment_features WHERE "featureType" = %s', ("AUDIO_SIGNAL",))
    stats["audio_signal_features"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM segment_features WHERE "featureType" = %s', ("CROSSWALK",))
    stats["crosswalk_features"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM segment_features WHERE "featureType" = %s', ("SLOPE_ANALYSIS",))
    stats["slope_features"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM segment_features WHERE "featureType" = %s', ("SUBWAY_ELEVATOR",))
    stats["subway_elevator_features"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM road_segments WHERE "audioSignalState" = %s', ("YES",))
    stats["audio_segments_yes"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM road_segments WHERE "crossingState" != %s', ("UNKNOWN",))
    stats["crossing_segments_tagged"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM road_segments WHERE "avgSlopePercent" IS NOT NULL')
    stats["slope_segments_tagged"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM road_segments WHERE "widthMeter" IS NOT NULL')
    stats["width_segments_tagged"] = int(cursor.fetchone()[0])
    cursor.execute('SELECT COUNT(*) FROM road_segments WHERE "elevatorState" = %s', ("YES",))
    stats["elevator_segments_tagged"] = int(cursor.fetchone()[0])
    return stats


def main() -> int:
    parser = build_parser("Load crosswalk, audio signal, slope, and subway elevator features against road_segments.")
    parser.add_argument("--audio-csv", type=Path, default=DEFAULT_AUDIO_CSV, help="Path to the audio signal CSV.")
    parser.add_argument("--crosswalk-csv", type=Path, default=DEFAULT_CROSSWALK_CSV, help="Path to the crosswalk CSV.")
    parser.add_argument("--slope-csv", type=Path, default=DEFAULT_SLOPE_CSV, help="Path to the slope polygon CSV.")
    parser.add_argument("--elevator-csv", type=Path, default=DEFAULT_ELEVATOR_CSV, help="Path to the subway elevator CSV.")
    parser.add_argument(
        "--max-distance-meters",
        type=float,
        default=DEFAULT_MAX_DISTANCE_METERS,
        help="Maximum distance in meters for point-to-segment matching.",
    )
    parser.add_argument(
        "--review-distance-meters",
        type=float,
        default=DEFAULT_REVIEW_DISTANCE_METERS,
        help="Maximum distance in meters for review-required point-to-segment matching.",
    )
    args = parser.parse_args()
    if args.review_distance_meters < args.max_distance_meters:
        parser.error("--review-distance-meters must be greater than or equal to --max-distance-meters")

    print_stage_banner(
        "04_segment_features_load.py",
        "stg_crosswalks_ready.csv + stg_audio_signals_ready.csv + slope_analysis_staging.csv + subway_station_elevators_erd_ready.csv",
    )
    for path in (args.audio_csv, args.crosswalk_csv, args.slope_csv, args.elevator_csv):
        if not path.exists():
            parser.error(f"Input file does not exist: {path}")

    audio_rows, audio_skipped = load_audio_rows(args.audio_csv)
    crosswalk_rows, crosswalk_skipped = load_crosswalk_rows(args.crosswalk_csv)
    slope_rows, slope_skipped = load_slope_rows(args.slope_csv)
    elevator_rows, elevator_skipped = load_elevator_rows(args.elevator_csv)
    print_summary(
        [
            ("audio_rows_valid", len(audio_rows)),
            ("audio_rows_skipped", audio_skipped),
            ("crosswalk_rows_valid", len(crosswalk_rows)),
            ("crosswalk_rows_skipped", crosswalk_skipped),
            ("slope_rows_valid", len(slope_rows)),
            ("slope_rows_skipped", slope_skipped),
            ("elevator_rows_valid", len(elevator_rows)),
            ("elevator_rows_skipped", elevator_skipped),
            ("max_distance_meters", args.max_distance_meters),
            ("review_distance_meters", args.review_distance_meters),
        ]
    )
    if args.dry_run:
        print("- action: validated input only")
        return 0

    with connect() as connection:
        with connection.cursor() as cursor:
            ensure_road_segments_exist(cursor)
            reset_segment_enrichment(cursor)
            audio_stats = load_audio_features(cursor, audio_rows, args.max_distance_meters)
            crosswalk_stats = load_crosswalk_features(cursor, crosswalk_rows, args.max_distance_meters)
            slope_stats = load_slope_features(cursor, slope_rows)
            elevator_stats = load_elevator_features(
                cursor,
                elevator_rows,
                args.max_distance_meters,
                args.review_distance_meters,
            )
            stats = validation_stats(cursor)
        connection.commit()

    print("- audio_match_stats:")
    print_summary(audio_stats.items())
    print("- crosswalk_match_stats:")
    print_summary(crosswalk_stats.items())
    print("- slope_match_stats:")
    print_summary(slope_stats.items())
    print("- elevator_match_stats:")
    print_summary(elevator_stats.items())
    print("- validation_stats:")
    print_summary(stats.items())
    print("- status: road_segments and segment_features enrichment complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
