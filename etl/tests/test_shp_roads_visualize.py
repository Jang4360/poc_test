from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "09_shp_roads_visualize.py"
SPEC = importlib.util.spec_from_file_location("etl_09_shp_roads_visualize", MODULE_PATH)
VISUALIZE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = VISUALIZE
SPEC.loader.exec_module(VISUALIZE)


class ShpRoadsVisualizeTests(unittest.TestCase):
    def test_build_html_embeds_counts_and_source(self) -> None:
        html = VISUALIZE.build_html(
            {
                "center": {"label": "장산역", "lon": 129.17, "lat": 35.16},
                "radiusMeters": 5000,
                "featureCount": 12,
                "sourceLabel": "N3L_A0020000_26",
                "sourcePath": "/tmp/N3L_A0020000_26.shp",
                "showBasemap": False,
                "bbox4326": {"minLon": 129.0, "minLat": 35.0, "maxLon": 129.3, "maxLat": 35.3},
                "roads": {"type": "FeatureCollection", "features": []},
            }
        )
        self.assertIn("장산역 5km 도로 중심선", html)
        self.assertIn("\"featureCount\": 12", html)
        self.assertIn("\"sourceLabel\": \"N3L_A0020000_26\"", html)
        self.assertIn("\"showBasemap\": false", html)


if __name__ == "__main__":
    unittest.main()
