from __future__ import annotations

import gzip
import json
import os
import pickle
import subprocess
import sys
import time
import traceback
from collections import Counter
from dataclasses import asdict, dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Mapping, Sequence

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.common.db import connect
from etl.scripts._shared import build_parser, print_stage_banner

try:
    from pyproj import Geod
except ImportError:  # pragma: no cover - optional dependency for runtime accuracy
    Geod = None


DEFAULT_PBF_PATH = ROOT_DIR / "etl" / "data" / "raw" / "busan.osm.pbf"
DEFAULT_SCHEMA_PATH = ROOT_DIR / "etl" / "sql" / "schema.sql"
DEFAULT_SNAPSHOT_PATH = ROOT_DIR / "runtime" / "etl" / "osm-network-snapshot.pkl.gz"
DEFAULT_BATCH_SIZE = 5_000
WORKER_SENTINEL_GRACE_SECONDS = 2.0
WORKER_POLL_INTERVAL_SECONDS = 0.5
INCLUDE_HIGHWAY = frozenset(
    {
        "footway",
        "path",
        "pedestrian",
        "living_street",
        "residential",
        "service",
        "unclassified",
        "crossing",
        "steps",
        "elevator",
    }
)
EXCLUDE_HIGHWAY = frozenset({"motorway", "trunk"})
SIDEWALK_VALUES = frozenset({"left", "right", "both", "yes"})
FOOT_VALUES = frozenset({"yes", "designated"})
GEOD = Geod(ellps="WGS84") if Geod is not None else None


class NetworkBuildError(RuntimeError):
    """Raised when the PBF cannot be turned into a coherent road network."""


@dataclass(frozen=True)
class WayRecord:
    way_id: int
    node_ids: tuple[int, ...]
    tags: dict[str, str]


@dataclass(frozen=True)
class SegmentCandidate:
    way_id: int
    from_osm_node_id: int
    to_osm_node_id: int
    ordinal: int
    path_node_ids: tuple[int, ...]


@dataclass(frozen=True)
class TargetState:
    road_node_count: int
    road_segment_count: int
    segment_feature_count: int


@dataclass(frozen=True)
class PreflightReport:
    road_nodes_exists: bool
    road_segments_exists: bool
    segment_features_exists: bool
    road_nodes_osm_unique: bool
    road_segments_source_unique: bool
    road_segments_geom_gist: bool
    target_state: TargetState


def default_sentinel_path(snapshot_path: Path) -> Path:
    return snapshot_path.with_name(snapshot_path.name + ".done.json")


def is_walkable(tags: Mapping[str, str]) -> bool:
    if tags.get("foot") == "no" or tags.get("access") == "private":
        return False
    if tags.get("highway") in EXCLUDE_HIGHWAY:
        return False
    return (
        tags.get("highway") in INCLUDE_HIGHWAY
        or tags.get("foot") in FOOT_VALUES
        or tags.get("sidewalk") in SIDEWALK_VALUES
    )


def is_anchor_node_tag(tags: Mapping[str, str]) -> bool:
    return "barrier" in tags or "crossing" in tags or tags.get("highway") == "crossing"


def dedupe_consecutive(node_ids: Sequence[int]) -> tuple[int, ...]:
    deduped: list[int] = []
    for node_id in node_ids:
        if not deduped or deduped[-1] != node_id:
            deduped.append(node_id)
    return tuple(deduped)


def identify_anchors(
    walkable_ways: Mapping[int, WayRecord],
    node_way_counts: Mapping[int, int],
    tagged_anchor_nodes: set[int],
) -> set[int]:
    anchors = set(tagged_anchor_nodes)
    for record in walkable_ways.values():
        anchors.add(record.node_ids[0])
        anchors.add(record.node_ids[-1])
    for node_id, count in node_way_counts.items():
        if count >= 2:
            anchors.add(node_id)
    return anchors


def split_way_to_segments(
    way_id: int,
    node_ids: Sequence[int],
    anchors: set[int],
) -> list[SegmentCandidate]:
    normalized = dedupe_consecutive(node_ids)
    if len(normalized) < 2:
        return []

    segments: list[SegmentCandidate] = []
    current_path = [normalized[0]]
    current_start = normalized[0]
    ordinal = 0

    for node_id in normalized[1:]:
        current_path.append(node_id)
        if node_id not in anchors:
            continue
        if current_start != node_id and len(current_path) >= 2:
            segments.append(
                SegmentCandidate(
                    way_id=way_id,
                    from_osm_node_id=current_start,
                    to_osm_node_id=node_id,
                    ordinal=ordinal,
                    path_node_ids=tuple(current_path),
                )
            )
            ordinal += 1
        current_start = node_id
        current_path = [node_id]

    return segments


def walk_access_for_tags(tags: Mapping[str, str]) -> str:
    if tags.get("foot") == "designated":
        return "DESIGNATED"
    if tags.get("sidewalk") in SIDEWALK_VALUES:
        return "SIDEWALK"
    if tags.get("highway") in {"steps", "elevator"}:
        return "STRUCTURAL"
    return "ALLOWED"


def haversine_segment_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6_371_000
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def geodesic_length_m(coords: Sequence[tuple[float, float]]) -> float:
    if len(coords) < 2:
        return 0.0
    if GEOD is not None:
        lons = [lon for lon, _ in coords]
        lats = [lat for _, lat in coords]
        return float(abs(GEOD.line_length(lons, lats)))
    return sum(
        haversine_segment_m(lon1, lat1, lon2, lat2)
        for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:])
    )


def linestring_wkt(coords: Sequence[tuple[float, float]]) -> str:
    return "LINESTRING (" + ", ".join(f"{lon} {lat}" for lon, lat in coords) + ")"


def build_network_artifacts(
    walkable_ways: Mapping[int, WayRecord],
    node_way_counts: Mapping[int, int],
    node_coords: Mapping[int, tuple[float, float]],
    tagged_anchor_nodes: set[int],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    anchors = identify_anchors(walkable_ways, node_way_counts, tagged_anchor_nodes)
    if not anchors:
        raise NetworkBuildError("No anchor nodes were found. OSM filter is likely too strict.")

    missing_anchor_nodes = sorted(node_id for node_id in anchors if node_id not in node_coords)
    if missing_anchor_nodes:
        sample = ", ".join(str(node_id) for node_id in missing_anchor_nodes[:5])
        raise NetworkBuildError(f"Missing coordinates for anchor nodes: {sample}")

    vertex_id_by_osm = {osm_node_id: index for index, osm_node_id in enumerate(sorted(anchors), start=1)}
    road_nodes = [
        {
            "vertex_id": vertex_id_by_osm[osm_node_id],
            "osm_node_id": osm_node_id,
            "lon": node_coords[osm_node_id][0],
            "lat": node_coords[osm_node_id][1],
        }
        for osm_node_id in sorted(anchors)
    ]

    road_segments: list[dict[str, object]] = []
    missing_segment_nodes: set[int] = set()
    degenerate_segments = 0
    edge_id = 1

    for way_id in sorted(walkable_ways):
        record = walkable_ways[way_id]
        for candidate in split_way_to_segments(way_id, record.node_ids, anchors):
            if any(node_id not in node_coords for node_id in candidate.path_node_ids):
                missing_segment_nodes.update(
                    node_id for node_id in candidate.path_node_ids if node_id not in node_coords
                )
                continue

            coords = [node_coords[node_id] for node_id in candidate.path_node_ids]
            if len(coords) < 2 or len(set(coords)) < 2:
                degenerate_segments += 1
                continue

            length_m = geodesic_length_m(coords)
            if length_m <= 0:
                degenerate_segments += 1
                continue

            road_segments.append(
                {
                    "edge_id": edge_id,
                    "from_node_id": vertex_id_by_osm[candidate.from_osm_node_id],
                    "to_node_id": vertex_id_by_osm[candidate.to_osm_node_id],
                    "geom_wkt": linestring_wkt(coords),
                    "length_m": round(length_m, 2),
                    "source_way_id": candidate.way_id,
                    "source_osm_from_node_id": candidate.from_osm_node_id,
                    "source_osm_to_node_id": candidate.to_osm_node_id,
                    "segment_ordinal": candidate.ordinal,
                    "walk_access": walk_access_for_tags(record.tags),
                }
            )
            edge_id += 1

    if missing_segment_nodes:
        sample = ", ".join(str(node_id) for node_id in sorted(missing_segment_nodes)[:5])
        raise NetworkBuildError(f"Missing coordinates for segment nodes: {sample}")
    if not road_segments:
        raise NetworkBuildError("No road segments were built. OSM filter is likely too strict.")

    stats = {
        "way_count": len(walkable_ways),
        "anchor_count": len(road_nodes),
        "segment_count": len(road_segments),
        "tagged_anchor_count": len(tagged_anchor_nodes),
        "degenerate_segment_count": degenerate_segments,
    }
    return road_nodes, road_segments, stats


def require_osmium():
    try:
        import osmium
    except ImportError as exc:  # pragma: no cover - depends on local runtime
        raise NetworkBuildError(
            "The 'osmium' package is required for OSM parsing. Install etl/requirements.txt first."
        ) from exc
    return osmium


def collect_osm_snapshot(
    pbf_path: Path,
) -> tuple[dict[int, WayRecord], Counter[int], dict[int, tuple[float, float]], set[int]]:
    osmium = require_osmium()

    class WayCollector(osmium.SimpleHandler):
        def __init__(self) -> None:
            super().__init__()
            self.walkable_ways: dict[int, WayRecord] = {}
            self.node_way_counts: Counter[int] = Counter()
            self.referenced_nodes: set[int] = set()

        def way(self, way) -> None:
            tags = {tag.k: tag.v for tag in way.tags}
            if not is_walkable(tags):
                return
            node_ids = dedupe_consecutive([node.ref for node in way.nodes])
            if len(node_ids) < 2:
                return
            self.walkable_ways[way.id] = WayRecord(way_id=way.id, node_ids=node_ids, tags=tags)
            self.referenced_nodes.update(node_ids)
            self.node_way_counts.update(node_ids)

    class NodeCollector(osmium.SimpleHandler):
        def __init__(self, referenced_nodes: set[int]) -> None:
            super().__init__()
            self.referenced_nodes = referenced_nodes
            self.node_coords: dict[int, tuple[float, float]] = {}
            self.tagged_anchor_nodes: set[int] = set()

        def node(self, node) -> None:
            if node.id not in self.referenced_nodes or not node.location.valid():
                return
            self.node_coords[node.id] = (node.location.lon, node.location.lat)
            tags = {tag.k: tag.v for tag in node.tags}
            if is_anchor_node_tag(tags):
                self.tagged_anchor_nodes.add(node.id)

    way_collector = WayCollector()
    way_collector.apply_file(str(pbf_path), locations=False)

    node_collector = NodeCollector(way_collector.referenced_nodes)
    node_collector.apply_file(str(pbf_path), locations=False)

    return (
        way_collector.walkable_ways,
        way_collector.node_way_counts,
        node_collector.node_coords,
        node_collector.tagged_anchor_nodes,
    )


def atomic_write_bytes(target_path: Path, data: bytes) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(target_path.name + ".tmp")
    with open(tmp_path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, target_path)


def execute_schema(cursor, schema_path: Path) -> None:
    cursor.execute(schema_path.read_text(encoding="utf-8"))


def table_exists(cursor, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    return cursor.fetchone()[0] is not None


def table_row_count(cursor, table_name: str) -> int:
    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    return cursor.fetchone()[0]


def unique_constraint_exists(cursor, table_name: str, columns: Sequence[str]) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            JOIN LATERAL (
                SELECT array_agg(att.attname::text ORDER BY key_cols.ordinality) AS column_names
                FROM unnest(con.conkey) WITH ORDINALITY AS key_cols(attnum, ordinality)
                JOIN pg_attribute att
                  ON att.attrelid = rel.oid
                 AND att.attnum = key_cols.attnum
            ) cols ON true
            WHERE nsp.nspname = current_schema()
              AND rel.relname = %s
              AND con.contype IN ('p', 'u')
              AND cols.column_names = %s::text[]
        )
        """,
        (table_name, list(columns)),
    )
    return bool(cursor.fetchone()[0])


def gist_index_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = %s
              AND indexdef ILIKE %s
              AND (
                    indexdef ILIKE %s
                 OR indexdef ILIKE %s
              )
        )
        """,
        (table_name, "%USING gist%", f'%("{column_name}")%', f"%({column_name})%"),
    )
    return bool(cursor.fetchone()[0])


def run_preflight_checks(cursor) -> PreflightReport:
    road_nodes_exists = table_exists(cursor, "road_nodes")
    road_segments_exists = table_exists(cursor, "road_segments")
    segment_features_exists = table_exists(cursor, "segment_features")

    target_state = TargetState(
        road_node_count=table_row_count(cursor, "road_nodes") if road_nodes_exists else 0,
        road_segment_count=table_row_count(cursor, "road_segments") if road_segments_exists else 0,
        segment_feature_count=table_row_count(cursor, "segment_features") if segment_features_exists else 0,
    )

    return PreflightReport(
        road_nodes_exists=road_nodes_exists,
        road_segments_exists=road_segments_exists,
        segment_features_exists=segment_features_exists,
        road_nodes_osm_unique=unique_constraint_exists(cursor, "road_nodes", ("osmNodeId",))
        if road_nodes_exists
        else False,
        road_segments_source_unique=unique_constraint_exists(
            cursor,
            "road_segments",
            ("sourceWayId", "sourceOsmFromNodeId", "sourceOsmToNodeId", "segmentOrdinal"),
        )
        if road_segments_exists
        else False,
        road_segments_geom_gist=gist_index_exists(cursor, "road_segments", "geom")
        if road_segments_exists
        else False,
        target_state=target_state,
    )


def validate_preflight_report(report: PreflightReport, truncate: bool) -> None:
    missing_items: list[str] = []
    if not report.road_nodes_exists:
        missing_items.append("road_nodes table")
    if not report.road_segments_exists:
        missing_items.append("road_segments table")
    if not report.segment_features_exists:
        missing_items.append("segment_features table")
    if not report.road_nodes_osm_unique:
        missing_items.append('UNIQUE constraint on road_nodes("osmNodeId")')
    if not report.road_segments_source_unique:
        missing_items.append(
            'UNIQUE constraint on road_segments("sourceWayId", "sourceOsmFromNodeId", "sourceOsmToNodeId", "segmentOrdinal")'
        )
    if not report.road_segments_geom_gist:
        missing_items.append('GIST index on road_segments("geom")')

    if missing_items:
        raise NetworkBuildError("Schema preflight failed: " + "; ".join(missing_items))

    if not truncate and (
        report.target_state.road_node_count > 0
        or report.target_state.road_segment_count > 0
        or report.target_state.segment_feature_count > 0
    ):
        raise NetworkBuildError(
            "Target tables already contain data. Re-run with --truncate for a rebuild, "
            "or use --load-snapshot against a clean target."
        )


def save_snapshot(
    snapshot_path: Path,
    road_nodes: Sequence[Mapping[str, object]],
    road_segments: Sequence[Mapping[str, object]],
    build_stats: Mapping[str, int],
) -> None:
    payload = {
        "road_nodes": list(road_nodes),
        "road_segments": list(road_segments),
        "build_stats": dict(build_stats),
    }
    snapshot_bytes = gzip.compress(pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL))
    atomic_write_bytes(snapshot_path, snapshot_bytes)


def load_snapshot(snapshot_path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    with gzip.open(snapshot_path, "rb") as fh:
        payload = pickle.load(fh)
    return payload["road_nodes"], payload["road_segments"], payload["build_stats"]


def write_completion_marker(sentinel_path: Path, snapshot_path: Path, build_stats: Mapping[str, int]) -> None:
    marker = {
        "snapshot_path": str(snapshot_path),
        "build_stats": dict(build_stats),
        "written_at": time.time(),
    }
    atomic_write_bytes(sentinel_path, json.dumps(marker, ensure_ascii=False).encode("utf-8"))


def load_completion_marker(sentinel_path: Path) -> dict[str, object]:
    return json.loads(sentinel_path.read_text(encoding="utf-8"))


def remove_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:  # pragma: no cover - windows-focused session
        os.kill(pid, 15)


def run_parse_worker(pbf_path: Path, snapshot_path: Path, sentinel_path: Path) -> None:
    try:
        walkable_ways, node_way_counts, node_coords, tagged_anchor_nodes = collect_osm_snapshot(pbf_path)
        road_nodes, road_segments, build_stats = build_network_artifacts(
            walkable_ways,
            node_way_counts,
            node_coords,
            tagged_anchor_nodes,
        )
        save_snapshot(snapshot_path, road_nodes, road_segments, build_stats)
        write_completion_marker(sentinel_path, snapshot_path, build_stats)
        os._exit(0)
    except BaseException:  # pragma: no cover - process teardown path
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(1)


def run_parse_only_subprocess(pbf_path: Path, snapshot_path: Path, sentinel_path: Path) -> dict[str, object]:
    remove_if_exists(snapshot_path)
    remove_if_exists(sentinel_path)

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--internal-parse-worker",
        "--pbf",
        str(pbf_path),
        "--snapshot",
        str(snapshot_path),
        "--sentinel",
        str(sentinel_path),
    ]
    process = subprocess.Popen(command, cwd=str(ROOT_DIR))
    sentinel_detected_at: float | None = None

    while True:
        if sentinel_path.exists():
            if sentinel_detected_at is None:
                sentinel_detected_at = time.time()
            elif process.poll() is None and time.time() - sentinel_detected_at >= WORKER_SENTINEL_GRACE_SECONDS:
                terminate_process_tree(process.pid)
                process.wait(timeout=10)
                break

        return_code = process.poll()
        if return_code is not None:
            break
        time.sleep(WORKER_POLL_INTERVAL_SECONDS)

    if not sentinel_path.exists():
        raise NetworkBuildError("Parse worker exited without writing the completion marker.")

    marker = load_completion_marker(sentinel_path)
    if not snapshot_path.exists():
        raise NetworkBuildError("Parse worker reported success but the snapshot file is missing.")

    return marker


def truncate_network_tables(cursor) -> None:
    cursor.execute('TRUNCATE TABLE segment_features, road_segments, road_nodes RESTART IDENTITY CASCADE')


def insert_road_nodes(cursor, road_nodes: Sequence[Mapping[str, object]], batch_size: int) -> None:
    from psycopg2.extras import execute_values

    execute_values(
        cursor,
        """
        INSERT INTO road_nodes ("vertexId", "osmNodeId", "point")
        VALUES %s
        ON CONFLICT ("osmNodeId") DO NOTHING
        """,
        [
            (
                row["vertex_id"],
                row["osm_node_id"],
                row["lon"],
                row["lat"],
            )
            for row in road_nodes
        ],
        template="(%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))",
        page_size=batch_size,
    )


def insert_road_segments(cursor, road_segments: Sequence[Mapping[str, object]], batch_size: int) -> None:
    from psycopg2.extras import execute_values

    execute_values(
        cursor,
        """
        INSERT INTO road_segments (
            "edgeId",
            "fromNodeId",
            "toNodeId",
            "geom",
            "lengthMeter",
            "sourceWayId",
            "sourceOsmFromNodeId",
            "sourceOsmToNodeId",
            "segmentOrdinal",
            "walkAccess"
        )
        VALUES %s
        ON CONFLICT ("sourceWayId", "sourceOsmFromNodeId", "sourceOsmToNodeId", "segmentOrdinal") DO NOTHING
        """,
        [
            (
                row["edge_id"],
                row["from_node_id"],
                row["to_node_id"],
                row["geom_wkt"],
                row["length_m"],
                row["source_way_id"],
                row["source_osm_from_node_id"],
                row["source_osm_to_node_id"],
                row["segment_ordinal"],
                row["walk_access"],
            )
            for row in road_segments
        ],
        template="(%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s, %s)",
        page_size=batch_size,
    )


def fetch_validation_stats(cursor) -> dict[str, int]:
    stats: dict[str, int] = {}
    cursor.execute('SELECT COUNT(*) FROM road_nodes')
    stats["db_road_node_count"] = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM road_segments')
    stats["db_road_segment_count"] = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM road_segments WHERE NOT ST_IsValid("geom")')
    stats["invalid_segment_count"] = cursor.fetchone()[0]
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT 1
            FROM road_segments
            GROUP BY "sourceWayId", "sourceOsmFromNodeId", "sourceOsmToNodeId", "segmentOrdinal"
            HAVING COUNT(*) > 1
        ) duplicate_rows
        """
    )
    stats["duplicate_segment_key_count"] = cursor.fetchone()[0]
    return stats


def print_summary(stats: Mapping[str, object], prefix: str = "-") -> None:
    for key, value in stats.items():
        print(f"{prefix} {key}: {value}")


def print_preflight_report(report: PreflightReport) -> None:
    print("- preflight:")
    print_summary(asdict(report), prefix="  *")


def main() -> int:
    parser = build_parser("Load busan.osm.pbf into road_nodes and road_segments.")
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF_PATH, help="Path to the source .osm.pbf file.")
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Path to the SQL schema bootstrap file.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT_PATH,
        help="Snapshot path for parse-only or load-snapshot mode.",
    )
    parser.add_argument(
        "--sentinel",
        type=Path,
        default=None,
        help="Internal completion marker for parse-only worker mode.",
    )
    parser.add_argument(
        "--load-snapshot",
        action="store_true",
        help="Skip OSM parsing and load road_nodes/road_segments from the snapshot file.",
    )
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Parse OSM and write the snapshot, but do not touch the database.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run DB and input validation only, then exit before parsing.",
    )
    parser.add_argument(
        "--internal-parse-worker",
        action="store_true",
        help="Internal worker mode. Do not call directly.",
    )
    parser.add_argument(
        "--bootstrap-schema",
        action="store_true",
        help="Apply schema.sql before running DB preflight. Use only for disposable local databases.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Bulk insert batch size for road_nodes and road_segments.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Explicit rebuild mode. Truncate road_nodes/road_segments/segment_features before loading.",
    )
    args = parser.parse_args()

    sentinel_path = args.sentinel or default_sentinel_path(args.snapshot)

    if args.batch_size < 1:
        parser.error("--batch-size must be a positive integer.")
    if args.parse_only and args.load_snapshot:
        parser.error("--parse-only and --load-snapshot cannot be used together.")
    if args.preflight_only and args.parse_only:
        parser.error("--preflight-only and --parse-only cannot be used together.")
    if args.preflight_only and args.internal_parse_worker:
        parser.error("--preflight-only and --internal-parse-worker cannot be used together.")
    if args.load_snapshot and not args.snapshot.exists():
        parser.error(f"Snapshot file does not exist: {args.snapshot}")
    if not args.load_snapshot and not args.pbf.exists():
        parser.error(f"PBF file does not exist: {args.pbf}")
    if not args.schema.exists():
        parser.error(f"Schema file does not exist: {args.schema}")

    if args.internal_parse_worker:
        run_parse_worker(args.pbf, args.snapshot, sentinel_path)
        return 0

    source_name = str(args.snapshot.relative_to(ROOT_DIR)) if args.load_snapshot else str(args.pbf.relative_to(ROOT_DIR))
    print_stage_banner("01_osm_load.py", source_name)
    mode_label = (
        "preflight-only"
        if args.preflight_only
        else "load-snapshot"
        if args.load_snapshot
        else "parse-only"
        if args.parse_only
        else "full-load"
    )
    print(f"- mode: {mode_label}")
    print(f"- batch_size: {args.batch_size}")
    print(f"- truncate: {args.truncate}")
    print(f"- bootstrap_schema: {args.bootstrap_schema}")

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            if args.bootstrap_schema:
                execute_schema(cursor, args.schema)
                connection.commit()
            report = run_preflight_checks(cursor)

        print_preflight_report(report)
        validate_preflight_report(report, truncate=args.truncate)

        if args.preflight_only:
            print("- action: preflight checks passed")
            return 0

        if args.parse_only:
            marker = run_parse_only_subprocess(args.pbf, args.snapshot, sentinel_path)
            print("- build_stats:")
            print_summary(marker["build_stats"], prefix="  *")
            print(f"- action: snapshot saved to {args.snapshot}")
            return 0

        if args.load_snapshot:
            road_nodes, road_segments, build_stats = load_snapshot(args.snapshot)
        else:
            walkable_ways, node_way_counts, node_coords, tagged_anchor_nodes = collect_osm_snapshot(args.pbf)
            road_nodes, road_segments, build_stats = build_network_artifacts(
                walkable_ways,
                node_way_counts,
                node_coords,
                tagged_anchor_nodes,
            )
            print("- build_stats:")
            print_summary(build_stats, prefix="  *")

        with connection.cursor() as cursor:
            if args.truncate:
                truncate_network_tables(cursor)
            insert_road_nodes(cursor, road_nodes, args.batch_size)
            insert_road_segments(cursor, road_segments, args.batch_size)

        connection.commit()

        with connection.cursor() as cursor:
            validation_stats = fetch_validation_stats(cursor)

    print("- validation_stats:")
    print_summary(validation_stats, prefix="  *")
    if validation_stats["invalid_segment_count"] > 0:
        raise NetworkBuildError("Loaded road_segments contain invalid geometries.")
    if validation_stats["duplicate_segment_key_count"] > 0:
        raise NetworkBuildError("Loaded road_segments contain duplicate natural keys.")

    print("- status: road_nodes and road_segments loaded successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
