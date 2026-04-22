from __future__ import annotations

import json
from pathlib import Path
import sys

import shapefile
from pyproj import Transformer

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.scripts._shared import build_parser, print_stage_banner, print_summary
DEFAULT_SHP_PATH = ROOT_DIR / "etl" / "data" / "raw" / "N3L_A0020000_26.shp"
DEFAULT_OUTPUT_HTML = ROOT_DIR / "runtime" / "etl" / "jangsan-road-centerlines-shp.html"
DEFAULT_CENTER_LON = 129.1769506
DEFAULT_CENTER_LAT = 35.1699309
DEFAULT_RADIUS_METERS = 5_000.0


def _build_svg_markup(payload: dict[str, object]) -> str:
    width = 1100
    height = 820
    padding = 24
    bbox = payload["bbox4326"]
    min_lon = float(bbox["minLon"])
    min_lat = float(bbox["minLat"])
    max_lon = float(bbox["maxLon"])
    max_lat = float(bbox["maxLat"])
    lon_span = max(max_lon - min_lon, 1e-9)
    lat_span = max(max_lat - min_lat, 1e-9)
    lines = []

    for feature in payload["roads"]["features"]:
        for line in feature["geometry"]["coordinates"]:
            points = []
            for lon, lat in line:
                x = padding + ((lon - min_lon) / lon_span) * (width - padding * 2)
                y = padding + (1 - ((lat - min_lat) / lat_span)) * (height - padding * 2)
                points.append(f"{x:.2f},{y:.2f}")
            if len(points) >= 2:
                lines.append(
                    f'<polyline points="{" ".join(points)}" fill="none" stroke="#dc2626" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />'
                )

    center = payload["center"]
    center_x = padding + ((float(center["lon"]) - min_lon) / lon_span) * (width - padding * 2)
    center_y = padding + (1 - ((float(center["lat"]) - min_lat) / lat_span)) * (height - padding * 2)

    return f"""
    <div class="svg-wrap">
      <svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img" aria-label="장산역 5km 도로 중심선">
        <rect x="0" y="0" width="{width}" height="{height}" fill="#f8fafc" />
        <rect x="{padding}" y="{padding}" width="{width - padding * 2}" height="{height - padding * 2}" fill="#ffffff" stroke="#cbd5e1" stroke-width="1" />
        {"".join(lines)}
        <circle cx="{center_x:.2f}" cy="{center_y:.2f}" r="5.5" fill="#1d4ed8" />
        <text x="{center_x + 10:.2f}" y="{center_y - 10:.2f}" font-size="18" fill="#1e293b" font-weight="700">{center["label"]}</text>
      </svg>
    </div>
    """


def build_html(payload: dict[str, object]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    map_markup = """
    <div id="map"></div>
  </div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script>
    const payload = PAYLOAD_PLACEHOLDER;
    const summary = document.getElementById("summary");
    function addCard(label, value, detail) {
      const el = document.createElement("div");
      el.className = "card";
      el.innerHTML = `<div>${label}</div><div class="value">${value}</div><div>${detail}</div>`;
      summary.appendChild(el);
    }
    addCard("Center", payload.center.label, `${payload.center.lat.toFixed(6)}, ${payload.center.lon.toFixed(6)}`);
    addCard("Radius", Math.round(payload.radiusMeters) + "m", "장산역 기준 bbox");
    addCard("Road centerlines", payload.featureCount, "bbox 안에 들어오는 SHP 선분 수");
    addCard("Source", payload.sourceLabel, payload.sourcePath);

    const map = L.map("map", { preferCanvas: true });
    if (payload.showBasemap) {
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);
    }

    const centerMarker = L.circleMarker([payload.center.lat, payload.center.lon], {
      radius: 7,
      color: "#1d4ed8",
      fillColor: "#1d4ed8",
      fillOpacity: 1,
    }).bindPopup(payload.center.label).addTo(map);

    const roadLayer = L.geoJSON(payload.roads, {
      style: () => ({
        color: "#dc2626",
        weight: 2.2,
        opacity: 0.9,
      }),
      onEachFeature: (feature, layer) => {
        const props = feature.properties || {};
        const rows = Object.entries(props)
          .filter(([, value]) => value !== null && value !== undefined && value !== "")
          .map(([key, value]) => `<div><strong>${key}</strong>: ${value}</div>`)
          .join("");
        if (rows) layer.bindPopup(rows);
      }
    }).addTo(map);

    const radiusCircle = L.circle([payload.center.lat, payload.center.lon], {
      radius: payload.radiusMeters,
      color: "#2563eb",
      weight: 2,
      fill: false,
      dashArray: "6 6",
    }).addTo(map);

    const group = L.featureGroup([centerMarker, roadLayer, radiusCircle]);
    const bounds = group.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds.pad(0.03));
    } else {
      map.setView([payload.center.lat, payload.center.lon], 13);
    }
  </script>
"""
    if not payload.get("showBasemap", True):
        map_markup = f"""
    <div id="map">
      {_build_svg_markup(payload)}
    </div>
  </div>
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
    addCard("Radius", Math.round(payload.radiusMeters) + "m", "장산역 기준 bbox");
    addCard("Road centerlines", payload.featureCount, "bbox 안에 들어오는 SHP 선분 수");
    addCard("Source", payload.sourceLabel, payload.sourcePath);
  </script>
"""
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <title>Jangsan Road Centerlines</title>
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
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
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
      height: 820px;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
      background: #f1f5f9;
    }}
    .svg-wrap {{
      height: 100%;
      background: #f8fafc;
    }}
  </style>
</head>
<body>
  <div class="page">
    <h1>장산역 5km 도로 중심선</h1>
    <p>입력: <strong>국토교통부 도로 중심선 SHP</strong>. 장산역 기준 5km bbox 안에 걸리는 선형 geometry만 표시합니다.</p>
    <div class="summary" id="summary"></div>
{map_markup.replace("PAYLOAD_PLACEHOLDER", payload_json)}
</body>
</html>
"""


def main() -> int:
    parser = build_parser("Render a Leaflet HTML from a road-centerline SHP around a station bbox.")
    parser.add_argument("--shp", type=Path, default=DEFAULT_SHP_PATH)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_OUTPUT_HTML)
    parser.add_argument("--center-lon", type=float, default=DEFAULT_CENTER_LON)
    parser.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    parser.add_argument("--radius-meters", type=float, default=DEFAULT_RADIUS_METERS)
    parser.add_argument("--center-label", default="장산역")
    parser.add_argument("--encoding", default="cp949")
    parser.add_argument("--no-basemap", action="store_true", help="Render without OSM tiles so file:// previews still work.")
    args = parser.parse_args()

    print_stage_banner("09_shp_roads_visualize.py", args.shp.name)
    print(f"- output_html: {args.output_html}")

    if not args.shp.exists():
        raise FileNotFoundError(f"SHP not found: {args.shp}")

    project = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    inverse = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

    center_x, center_y = project.transform(args.center_lon, args.center_lat)
    minx = center_x - args.radius_meters
    miny = center_y - args.radius_meters
    maxx = center_x + args.radius_meters
    maxy = center_y + args.radius_meters

    reader = shapefile.Reader(str(args.shp), encoding=args.encoding)
    features = []
    for shape_record in reader.iterShapeRecords(fields=["UFID", "RDNM", "NAME", "RVWD", "RDLN", "RDDV", "DVYN", "ONSD"]):
        bx1, by1, bx2, by2 = shape_record.shape.bbox
        if bx2 < minx or bx1 > maxx or by2 < miny or by1 > maxy:
            continue

        points = shape_record.shape.points
        if len(points) < 2:
            continue

        parts = list(shape_record.shape.parts) + [len(points)]
        coordinates = []
        for start, end in zip(parts, parts[1:]):
            line = []
            for x, y in points[start:end]:
                lon, lat = inverse.transform(x, y)
                line.append([lon, lat])
            if len(line) >= 2:
                coordinates.append(line)
        if not coordinates:
            continue

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "MultiLineString", "coordinates": coordinates},
                "properties": shape_record.record.as_dict(),
            }
        )

    payload = {
        "center": {"label": args.center_label, "lon": args.center_lon, "lat": args.center_lat},
        "radiusMeters": args.radius_meters,
        "featureCount": len(features),
        "sourceLabel": args.shp.stem,
        "sourcePath": str(args.shp),
        "showBasemap": not args.no_basemap,
        "bbox4326": {
            "minLon": float(center_x - args.radius_meters),
            "minLat": float(center_y - args.radius_meters),
            "maxLon": float(center_x + args.radius_meters),
            "maxLat": float(center_y + args.radius_meters),
        },
        "roads": {"type": "FeatureCollection", "features": features},
    }

    # Replace projected bbox with geographic bbox for the SVG fallback.
    min_lon, min_lat = inverse.transform(center_x - args.radius_meters, center_y - args.radius_meters)
    max_lon, max_lat = inverse.transform(center_x + args.radius_meters, center_y + args.radius_meters)
    payload["bbox4326"] = {
        "minLon": min(min_lon, max_lon),
        "minLat": min(min_lat, max_lat),
        "maxLon": max(min_lon, max_lon),
        "maxLat": max(min_lat, max_lat),
    }

    if args.dry_run:
        print_summary(
            [
                ("center", args.center_label),
                ("radius_meters", args.radius_meters),
                ("feature_count", len(features)),
                ("output_html", args.output_html),
            ]
        )
        return 0

    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(build_html(payload), encoding="utf-8")

    print_summary(
        [
            ("center", args.center_label),
            ("radius_meters", args.radius_meters),
            ("feature_count", len(features)),
            ("output_html", args.output_html),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
