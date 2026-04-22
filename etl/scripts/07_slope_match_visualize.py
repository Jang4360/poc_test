from __future__ import annotations

import importlib.util
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import osmium
from pyproj import Transformer
from shapely import wkt
from shapely.geometry import LineString, Point, mapping, box
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.scripts._shared import build_parser, print_stage_banner, print_summary


DEFAULT_PBF_PATH = ROOT_DIR / "etl" / "data" / "raw" / "busan.osm.pbf"
DEFAULT_SLOPE_CSV = ROOT_DIR / "etl" / "data" / "raw" / "slope_analysis_staging.csv"
DEFAULT_OUTPUT_HTML = ROOT_DIR / "runtime" / "etl" / "slope-match-v2-hotspots.html"
DEFAULT_GRID_SIZE_METERS = 500.0
DEFAULT_BBOX_MARGIN_METERS = 250.0
DEFAULT_TOP_HOTSPOTS = 6
HOTSPOT_STATUSES = ("matched", "review", "unmatched")

EDGE_COLOR = "#1d4ed8"
MATCHED_COLOR = "#16a34a"
REVIEW_COLOR = "#f59e0b"
UNMATCHED_COLOR = "#dc2626"


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


def query_tree_indexes(tree: STRtree, geom) -> list[int]:
    result = tree.query(geom)
    if len(result) == 0:
        return []
    first = result[0]
    if isinstance(first, int):
        return [int(index) for index in result]
    return list(result)


def classify_slope_status(polygon_proj, current_tree: STRtree, current_geoms: list, v2_tree: STRtree, v2_geoms: list) -> str:
    current_candidates = query_tree_indexes(current_tree, polygon_proj)
    if any(current_geoms[index].intersects(polygon_proj) for index in current_candidates):
        return "matched"
    v2_candidates = query_tree_indexes(v2_tree, polygon_proj)
    if any(v2_geoms[index].intersects(polygon_proj) for index in v2_candidates):
        return "review"
    return "unmatched"


def hotspot_key(x_m: float, y_m: float, grid_size_m: float) -> tuple[int, int]:
    return (math.floor(x_m / grid_size_m), math.floor(y_m / grid_size_m))


def rank_hotspots(cell_counts: Mapping[tuple[int, int], Counter], top_n: int) -> list[tuple[tuple[int, int], Counter]]:
    ranked = [(cell, counts) for cell, counts in cell_counts.items() if counts["review"] + counts["unmatched"] > 0]
    ranked.sort(
        key=lambda item: (
            item[1]["review"] + item[1]["unmatched"],
            item[1]["unmatched"],
            item[1]["review"],
            item[1]["matched"],
        ),
        reverse=True,
    )
    return ranked[:top_n]


def as_feature(geom, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": mapping(geom),
        "properties": properties,
    }


class WayCollector(osmium.SimpleHandler):
    def __init__(self, project_transform):
        super().__init__()
        self.project_transform = project_transform
        self.current_geoms: list[Any] = []
        self.v2_entries: list[dict[str, Any]] = []

    def way(self, way) -> None:
        tags = {key: value for key, value in way.tags}
        current_ok = OSM_LOAD.is_walkable(tags)
        v2_ok = is_walkable_v2(tags)
        if not current_ok and not v2_ok:
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
        if geom_proj.is_empty:
            return

        if current_ok:
            self.current_geoms.append(geom_proj)
        if v2_ok:
            self.v2_entries.append(
                {
                    "wayId": int(way.id),
                    "geom_ll": geom_ll,
                    "geom_proj": geom_proj,
                    "properties": {
                        "wayId": int(way.id),
                        "highway": tags.get("highway"),
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
  <title>Slope Match Hotspots (v2)</title>
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
      max-width: 1440px;
      margin: 0 auto;
      padding: 24px;
    }}
    h1, h2 {{
      margin: 0 0 12px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 20px 0 32px;
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
    .hotspot {{
      margin-bottom: 28px;
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }}
    .hotspot-header {{
      padding: 16px 18px;
      border-bottom: 1px solid #e2e8f0;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    .hotspot-meta {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      font-size: 14px;
      color: #334155;
    }}
    .chip {{
      padding: 4px 8px;
      border-radius: 999px;
      font-weight: 600;
      background: #eff6ff;
      color: #1d4ed8;
    }}
    .map {{
      height: 540px;
      width: 100%;
    }}
    .legend {{
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
      margin-top: 10px;
      font-size: 13px;
      color: #334155;
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 3px;
      display: inline-block;
    }}
    code {{
      background: #e2e8f0;
      padding: 2px 4px;
      border-radius: 6px;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>Slope Match Hotspots</h1>
    <p>
      분류 기준: <strong>matched</strong>는 현재 walkable 필터에서도 붙는 polygon,
      <strong>review</strong>는 <code>v2</code>에서만 새로 붙는 polygon,
      <strong>unmatched</strong>는 <code>v2</code> 기준으로도 OSM edge와 교차하지 않는 polygon입니다.
    </p>
    <div class="summary" id="summary"></div>
    <div id="hotspots"></div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script>
    const payload = {payload_json};
    const colors = {{
      matched: "{MATCHED_COLOR}",
      review: "{REVIEW_COLOR}",
      unmatched: "{UNMATCHED_COLOR}",
      edge: "{EDGE_COLOR}",
    }};

    function createSummaryCard(label, value, detail) {{
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `<div>${{label}}</div><div class="value">${{value}}</div><div>${{detail}}</div>`;
      return card;
    }}

    function styleSlope(feature) {{
      const status = feature.properties.status;
      return {{
        color: colors[status],
        weight: 1.5,
        fillColor: colors[status],
        fillOpacity: status === "matched" ? 0.14 : 0.24,
      }};
    }}

    function styleEdge() {{
      return {{
        color: colors.edge,
        weight: 2,
        opacity: 0.8,
      }};
    }}

    function bindPopup(layer, properties) {{
      const rows = Object.entries(properties)
        .filter(([, value]) => value !== null && value !== undefined && value !== "")
        .map(([key, value]) => `<div><strong>${{key}}</strong>: ${{value}}</div>`)
        .join("");
      if (rows) {{
        layer.bindPopup(rows);
      }}
    }}

    const summaryEl = document.getElementById("summary");
    summaryEl.appendChild(createSummaryCard("Slope Rows", payload.summary.totalSlopeRows, "loader 기준 유효 polygon 수"));
    summaryEl.appendChild(createSummaryCard("Matched", payload.summary.statusCounts.matched, "현재 필터에서도 교차"));
    summaryEl.appendChild(createSummaryCard("Review", payload.summary.statusCounts.review, "v2에서만 새로 교차"));
    summaryEl.appendChild(createSummaryCard("Unmatched", payload.summary.statusCounts.unmatched, "v2로도 교차 없음"));
    summaryEl.appendChild(createSummaryCard("v2 Edges", payload.summary.v2EdgeCount, "raw PBF에서 추출한 v2 eligible line 수"));

    const hotspotsEl = document.getElementById("hotspots");
    payload.hotspots.forEach((hotspot, index) => {{
      const section = document.createElement("section");
      section.className = "hotspot";
      section.innerHTML = `
        <div class="hotspot-header">
          <div>
            <h2>#${{index + 1}} ${{hotspot.title}}</h2>
            <div class="legend">
              <span><i class="swatch" style="background:{MATCHED_COLOR}"></i> matched</span>
              <span><i class="swatch" style="background:{REVIEW_COLOR}"></i> review</span>
              <span><i class="swatch" style="background:{UNMATCHED_COLOR}"></i> unmatched</span>
              <span><i class="swatch" style="background:{EDGE_COLOR}"></i> v2 edge</span>
            </div>
          </div>
          <div class="hotspot-meta">
            <span class="chip">issue=${{hotspot.summary.review + hotspot.summary.unmatched}}</span>
            <span>matched=${{hotspot.summary.matched}}</span>
            <span>review=${{hotspot.summary.review}}</span>
            <span>unmatched=${{hotspot.summary.unmatched}}</span>
            <span>edges=${{hotspot.v2Edges.features.length}}</span>
          </div>
        </div>
        <div class="map" id="map-${{index}}"></div>
      `;
      hotspotsEl.appendChild(section);

      const map = L.map(`map-${{index}}`, {{ preferCanvas: true }});
      L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
      }}).addTo(map);

      const edgeLayer = L.geoJSON(hotspot.v2Edges, {{
        style: styleEdge,
        onEachFeature: (feature, layer) => bindPopup(layer, feature.properties),
      }});
      const matchedLayer = L.geoJSON(hotspot.slope.matched, {{
        style: styleSlope,
        onEachFeature: (feature, layer) => bindPopup(layer, feature.properties),
      }});
      const reviewLayer = L.geoJSON(hotspot.slope.review, {{
        style: styleSlope,
        onEachFeature: (feature, layer) => bindPopup(layer, feature.properties),
      }});
      const unmatchedLayer = L.geoJSON(hotspot.slope.unmatched, {{
        style: styleSlope,
        onEachFeature: (feature, layer) => bindPopup(layer, feature.properties),
      }});

      edgeLayer.addTo(map);
      matchedLayer.addTo(map);
      reviewLayer.addTo(map);
      unmatchedLayer.addTo(map);

      L.control.layers(null, {{
        "v2 edge": edgeLayer,
        "matched": matchedLayer,
        "review": reviewLayer,
        "unmatched": unmatchedLayer,
      }}, {{ collapsed: false }}).addTo(map);

      const group = L.featureGroup([edgeLayer, matchedLayer, reviewLayer, unmatchedLayer]);
      const bounds = group.getBounds();
      if (bounds.isValid()) {{
        map.fitBounds(bounds.pad(0.12));
      }} else {{
        map.setView([35.1796, 129.0756], 13);
      }}
    }});
  </script>
</body>
</html>
"""


def main() -> int:
    parser = build_parser("Generate a Leaflet HTML that overlays v2 OSM edges with slope polygons.")
    parser.add_argument("--pbf", type=Path, default=DEFAULT_PBF_PATH)
    parser.add_argument("--slope-csv", type=Path, default=DEFAULT_SLOPE_CSV)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_OUTPUT_HTML)
    parser.add_argument("--grid-size-meters", type=float, default=DEFAULT_GRID_SIZE_METERS)
    parser.add_argument("--bbox-margin-meters", type=float, default=DEFAULT_BBOX_MARGIN_METERS)
    parser.add_argument("--top-hotspots", type=int, default=DEFAULT_TOP_HOTSPOTS)
    args = parser.parse_args()

    print_stage_banner("07_slope_match_visualize.py", args.slope_csv.name)
    print(f"- pbf: {args.pbf}")
    print(f"- output_html: {args.output_html}")

    if not args.pbf.exists():
        raise FileNotFoundError(f"PBF not found: {args.pbf}")
    if not args.slope_csv.exists():
        raise FileNotFoundError(f"Slope CSV not found: {args.slope_csv}")

    project = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True).transform

    collector = WayCollector(project)
    collector.apply_file(str(args.pbf), locations=True)
    current_tree = STRtree(collector.current_geoms)
    v2_geoms = [entry["geom_proj"] for entry in collector.v2_entries]
    v2_tree = STRtree(v2_geoms)

    slope_rows, skipped_rows = SEGMENTS.load_slope_rows(args.slope_csv)

    cell_counts: dict[tuple[int, int], Counter] = defaultdict(Counter)
    classified: list[dict[str, Any]] = []
    status_counts: Counter = Counter()
    for source_id, polygon_wkt, avg_slope_percent, width_meter in slope_rows:
        polygon_ll = wkt.loads(polygon_wkt)
        polygon_proj = transform(project, polygon_ll)
        status = classify_slope_status(polygon_proj, current_tree, collector.current_geoms, v2_tree, v2_geoms)
        centroid = polygon_proj.centroid
        cell = hotspot_key(centroid.x, centroid.y, args.grid_size_meters)
        cell_counts[cell][status] += 1
        status_counts[status] += 1
        classified.append(
            {
                "sourceId": source_id,
                "polygonWkt": polygon_wkt,
                "avgSlopePercent": avg_slope_percent,
                "widthMeter": width_meter,
                "status": status,
                "centroidX": centroid.x,
                "centroidY": centroid.y,
            }
        )

    ranked_hotspots = rank_hotspots(cell_counts, args.top_hotspots)
    hotspot_payload: list[dict[str, Any]] = []

    for rank, (cell, counts) in enumerate(ranked_hotspots, start=1):
        min_x = cell[0] * args.grid_size_meters
        min_y = cell[1] * args.grid_size_meters
        max_x = min_x + args.grid_size_meters
        max_y = min_y + args.grid_size_meters
        bbox_proj = box(
            min_x - args.bbox_margin_meters,
            min_y - args.bbox_margin_meters,
            max_x + args.bbox_margin_meters,
            max_y + args.bbox_margin_meters,
        )

        slope_features = {status: [] for status in HOTSPOT_STATUSES}
        hotspot_summary: Counter = Counter()
        for row in classified:
            centroid = Point(row["centroidX"], row["centroidY"])
            if not bbox_proj.contains(centroid):
                continue
            polygon_ll = wkt.loads(row["polygonWkt"])
            properties = {
                "sourceId": row["sourceId"],
                "status": row["status"],
                "avgSlopePercent": row["avgSlopePercent"],
                "widthMeter": row["widthMeter"],
            }
            slope_features[row["status"]].append(as_feature(polygon_ll, properties))
            hotspot_summary[row["status"]] += 1

        edge_features = []
        for entry in collector.v2_entries:
            if not entry["geom_proj"].intersects(bbox_proj):
                continue
            edge_features.append(as_feature(entry["geom_ll"], entry["properties"]))

        hotspot_payload.append(
            {
                "title": f"grid {cell[0]},{cell[1]}",
                "summary": {status: int(hotspot_summary[status]) for status in HOTSPOT_STATUSES},
                "slope": {
                    status: {
                        "type": "FeatureCollection",
                        "features": slope_features[status],
                    }
                    for status in HOTSPOT_STATUSES
                },
                "v2Edges": {
                    "type": "FeatureCollection",
                    "features": edge_features,
                },
                "issueCount": int(counts["review"] + counts["unmatched"]),
            }
        )

    payload = {
        "summary": {
            "totalSlopeRows": len(slope_rows),
            "skippedSlopeRows": skipped_rows,
            "statusCounts": {status: int(status_counts[status]) for status in HOTSPOT_STATUSES},
            "v2EdgeCount": len(collector.v2_entries),
            "currentEdgeCount": len(collector.current_geoms),
        },
        "hotspots": hotspot_payload,
    }

    if args.dry_run:
        print_summary(
            [
                ("total_slope_rows", len(slope_rows)),
                ("skipped_slope_rows", skipped_rows),
                ("matched", status_counts["matched"]),
                ("review", status_counts["review"]),
                ("unmatched", status_counts["unmatched"]),
                ("hotspot_count", len(hotspot_payload)),
            ]
        )
        return 0

    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(build_html(payload), encoding="utf-8")
    print_summary(
        [
            ("status", "html visualization written"),
            ("output_html", args.output_html),
            ("matched", status_counts["matched"]),
            ("review", status_counts["review"]),
            ("unmatched", status_counts["unmatched"]),
            ("hotspot_count", len(hotspot_payload)),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
