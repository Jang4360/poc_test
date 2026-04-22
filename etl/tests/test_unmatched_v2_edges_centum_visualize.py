from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "08_unmatched_v2_edges_centum_visualize.py"
SPEC = importlib.util.spec_from_file_location("etl_08_unmatched_v2_edges_centum_visualize", MODULE_PATH)
VISUALIZE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = VISUALIZE
SPEC.loader.exec_module(VISUALIZE)


class UnmatchedV2EdgesCentumVisualizeTests(unittest.TestCase):
    def test_is_walkable_v2_includes_secondary_and_link(self) -> None:
        self.assertTrue(VISUALIZE.is_walkable_v2({"highway": "secondary"}))
        self.assertTrue(VISUALIZE.is_walkable_v2({"highway": "primary_link"}))
        self.assertFalse(VISUALIZE.is_walkable_v2({"highway": "secondary", "access": "private"}))

    def test_build_html_embeds_center_and_counts(self) -> None:
        html = VISUALIZE.build_html(
            {
                "center": {"label": "센텀시티역", "lon": 129.13, "lat": 35.16},
                "radiusMeters": 1200,
                "v2EdgeCount": 10,
                "unmatchedEdgeCount": 3,
                "unmatchedEdges": {"type": "FeatureCollection", "features": []},
            }
        )
        self.assertIn("센텀시티 주변 slope 미매칭 v2 보행 edge", html)
        self.assertIn("\"unmatchedEdgeCount\": 3", html)
        self.assertIn("\"label\": \"센텀시티역\"", html)


if __name__ == "__main__":
    unittest.main()
