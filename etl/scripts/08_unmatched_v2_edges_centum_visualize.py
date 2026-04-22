from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import osmium
from pyproj import Transformer
from shapely import wkt
from shapely.geometry import LineString, Point, box, mapping
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.scripts._shared import build_parser, print_stage_banner, print_summary


DEFAULT_PBF_PATH = ROOT_DIR / "etl" / "data" / "raw" / "busan.osm.pbf"
DEFAULT_SLOPE_CSV = ROOT_DIR / "etl" / "data" / "raw" / "slope_analysis_staging.csv"
DEFAULT_OUTPUT_HTML = ROOT_DIR / "runtime" / "etl" / "centum-unmatched-v2-edges.html"
DEFAULT_CENTER_LON = 129.1323624
DEFAULT_CENTER_LAT = 35.1692748
DEFAULT_RADIUS_METERS = 1_200.0
EDGE_COLOR = "#dc2626"
CENTER_COLOR = "#1d4ed8"


def load_script(name: str):
    module_path = ROOT_DIR / "etl" / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", "").replace("-", "_"), module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


OSM_LOAD = load_script("01_osm_load.py")
SEGMENTS = load_script("04_segment_features_load.py")


def is_walkable_v2(tags: Mapping[str, str]) -> bool:
    if OSM_LOAD.is_walkable(tags):
        return True
    if tags.get("foot") == "no" or tags.get("access") == "private":
        return False
    highway = tags.get("highway", "")
    if highway in {"primary", "secondary", "tertiary", "road", "track", "platform"}:
        return True
    if highway.endswith("_link") and highway[:-5] in {"motorway", "trunk", "primary", "secondary", "tertiary"}:
        return True
    return False


class CentumWayCollector(osmium.SimpleHandler):
    def __init__(self, project_transform, bbox_proj):
        super().__init__()
        self.project_transform = project_transform
        self.bbox_proj = bbox_proj
        self.v2_entries: list[dict[str, Any]] = []

    def way(self, way) -> None:
        tags = {key: value for key, value in way.tags}
        if not is_walkable_v2(tags):
            return

        coords: list[tuple[float, float]] = []
        try:
            for node in way.nodes:
                if node.location.valid():
                    coords.append((node.location.lon, node.location.lat))
        except Exception:
            return
        if len(coords) < 2:
            return

        geom_ll = LineString(coords)
        geom_proj = transform(self.project_transform, geom_ll)
        if geom_proj.is_empty or not geom_proj.intersects(self.bbox_proj):
            return

        self.v2_entries.append(
            {
                "wayId": int(way.id),
                "geom_ll": geom_ll,
                "geom_proj": geom_proj,
                "properties": {
                    "wayId": int(way.id),
                    "highway": tags.get("highway"),
                    "name": tags.get("name"),
                    "foot": tags.get("foot"),
                    "sidewalk": tags.get("sidewalk"),
                    "area": tags.get("area"),
                },
            }
        )


def build_html(payload: dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>Centum Unmatched v2 Edges</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f8fafc;
      color: #0f172a;
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 18px 0 24px;
    }}
    .card {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
    }}
    .value {{
      font-size: 28px;
      font-weight: 700;
      margin-top: 6px;
    }}
    #map {{
      height: 760px;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>센텀시티 주변 slope 미매칭 v2 보행 edge</h1>
    <p>기준: <strong>v2 필터로 포함되는 OSM 보행 edge</strong> 중에서 <strong>slope polygon과 한 번도 교차하지 않는 선</strong>만 표시합니다.</p>
    <div class="summary" id="summary"></div>
    <div id="map"></div>
  </div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script>
    const payload = {payload_json};
    const summary = document.getElementById("summary");
    function addCard(label, value, detail) {{
      const el = document.createElement("div");
      el.className = "card";
      el.innerHTML = `<div>${{label}}</div><div class="value">${{value}}</div><div>${{detail}}</div>`;
      summary.appendChild(el);
    }}
    addCard("Center", payload.center.label, `${{payload.center.lat.toFixed(6)}}, ${{payload.center.lon.toFixed(6)}}`);
    addCard("Radius", Math.round(payload.radiusMeters) + "m", "센텀시티 기준 bbox");
    addCard("v2 edges in bbox", payload.v2EdgeCount, "bbox 안의 전체 v2 edge");
    addCard("unmatched edges", payload.unmatchedEdgeCount, "slope polygon과 교차하지 않는 edge");

    const map = L.map("map", {{ preferCanvas: true }});
    L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }}).addTo(map);

    const centerMarker = L.circleMarker([payload.center.lat, payload.center.lon], {{
      radius: 7,
      color: "{CENTER_COLOR}",
      fillColor: "{CENTER_COLOR}",
      fillOpacity: 1,
    }}).bindPopup("센텀시티 기준점").addTo(map);

    const unmatchedLayer = L.geoJSON(payload.unmatchedEdges, {{
      style: () => ({{
        color: "{EDGE_COLOR}",
        weight: 3,
        opacity: 0.95,
      }}),
      onEachFeature: (feature, layer) => {{
        const props = feature.properties || {{}};
        const rows = Object.entries(props)
          .filter(([, value]) => value !== null && value !== undefined && value !== "")
          .map(([key, value]) => `<div><strong>${{key}}</strong>: ${{value}}</div>`)
          .join("");
        if (rows) layer.bindPopup(rows);
      }}
    }}).addTo(map);

    const group = L.featureGroup([centerMarker, unmatchedLayer]);
    const bounds = group.getBounds();
    if (bounds.isValid()) {{
      map.fitBounds(bounds.pad(0.08));
    }} else {{
      map.setView([payload.center.lat, payload.center.lon], 15);
    }}
  </script>
</body>
</html>
"""


def intersects_any_slope(candidates, slope_polygons: list, edge_geom) -> bool:
    if len(candidates) == 0:
        return False
    first = candidates[0]
    if isinstance(first, int) or type(first).__name__.startswith("int"):
        return any(slope_polygons[int(index)].intersects(edge_geom) for index in candidates)
    return any(candidate.intersects(edge_geom) for candidate in candidates)


def main() -> int:
    parser = build_parser("Generate a Centum City HTML showing only v2 edges that do not intersect slope polygons.")
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF_PATH)
    parser.add_argument("--slope-csv", type=Path, default=DEFAULT_SLOPE_CSV)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_OUTPUT_HTML)
    parser.add_argument("--center-lon", type=float, default=DEFAULT_CENTER_LON)
    parser.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    parser.add_argument("--radius-meters", type=float, default=DEFAULT_RADIUS_METERS)
    parser.add_argument("--center-label", default="센텀시티역")
    args = parser.parse_args()

    print_stage_banner("08_unmatched_v2_edges_centum_visualize.py", args.slope_csv.name)
    print(f"- pbf: {args.pbf}")
    print(f"- output_html: {args.output_html}")

    if not args.pbf.exists():
        raise FileNotFoundError(f"PBF not found: {args.pbf}")
    if not args.slope_csv.exists():
        raise FileNotFoundError(f"Slope CSV not found: {args.slope_csv}")

    project = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True).transform
    inverse = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True).transform
    center_ll = Point(args.center_lon, args.center_lat)
    center_proj = transform(project, center_ll)
    bbox_proj = box(
        center_proj.x - args.radius_meters,
        center_proj.y - args.radius_meters,
        center_proj.x + args.radius_meters,
        center_proj.y + args.radius_meters,
    )

    collector = CentumWayCollector(project, bbox_proj)
    collector.apply_file(str(args.pbf), locations=True)

    slope_rows, skipped_rows = SEGMENTS.load_slope_rows(args.slope_csv)
    slope_polygons = []
    for _, polygon_wkt, _, _ in slope_rows:
        polygon_proj = transform(project, wkt.loads(polygon_wkt))
        if polygon_proj.is_empty or not polygon_proj.intersects(bbox_proj):
            continue
        slope_polygons.append(polygon_proj)
    slope_tree = STRtree(slope_polygons)

    unmatched_features = []
    for entry in collector.v2_entries:
        candidates = slope_tree.query(entry["geom_proj"])
        intersects = intersects_any_slope(candidates, slope_polygons, entry["geom_proj"])
        if intersects:
            continue
        unmatched_features.append(
            {
                "type": "Feature",
                "geometry": mapping(entry["geom_ll"]),
                "properties": entry["properties"],
            }
        )

    payload = {
        "center": {
            "label": args.center_label,
            "lon": args.center_lon,
            "lat": args.center_lat,
        },
        "radiusMeters": args.radius_meters,
        "v2EdgeCount": len(collector.v2_entries),
        "unmatchedEdgeCount": len(unmatched_features),
        "slopePolygonCountInBbox": len(slope_polygons),
        "skippedSlopeRows": skipped_rows,
        "unmatchedEdges": {
            "type": "FeatureCollection",
            "features": unmatched_features,
        },
    }

    if args.dry_run:
        print_summary(
            [
                ("v2_edge_count", len(collector.v2_entries)),
                ("unmatched_edge_count", len(unmatched_features)),
                ("slope_polygon_count_in_bbox", len(slope_polygons)),
                ("skipped_slope_rows", skipped_rows),
            ]
        )
        return 0

    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(build_html(payload), encoding="utf-8")
    print_summary(
        [
            ("status", "html visualization written"),
            ("output_html", args.output_html),
            ("v2_edge_count", len(collector.v2_entries)),
            ("unmatched_edge_count", len(unmatched_features)),
            ("slope_polygon_count_in_bbox", len(slope_polygons)),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
