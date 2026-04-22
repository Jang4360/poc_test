from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from shapely.geometry import LineString, Polygon
from shapely.strtree import STRtree


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "07_slope_match_visualize.py"
SPEC = importlib.util.spec_from_file_location("etl_07_slope_match_visualize", MODULE_PATH)
VISUALIZE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = VISUALIZE
SPEC.loader.exec_module(VISUALIZE)


class SlopeMatchVisualizeTests(unittest.TestCase):
    def test_is_walkable_v2_extends_primary_without_sidewalk(self) -> None:
        self.assertTrue(VISUALIZE.is_walkable_v2({"highway": "primary"}))
        self.assertTrue(VISUALIZE.is_walkable_v2({"highway": "tertiary_link"}))
        self.assertFalse(VISUALIZE.is_walkable_v2({"highway": "primary", "foot": "no"}))

    def test_classify_slope_status_prefers_current_match_before_review(self) -> None:
        current_geom = LineString([(0, 0), (10, 0)])
        review_geom = LineString([(0, 5), (10, 5)])
        current_tree = STRtree([current_geom])
        v2_tree = STRtree([current_geom, review_geom])
        polygon = Polygon([(1, -1), (2, -1), (2, 1), (1, 1)])
        self.assertEqual(
            VISUALIZE.classify_slope_status(polygon, current_tree, [current_geom], v2_tree, [current_geom, review_geom]),
            "matched",
        )

    def test_classify_slope_status_marks_v2_only_intersection_as_review(self) -> None:
        current_geom = LineString([(0, 0), (10, 0)])
        review_geom = LineString([(0, 5), (10, 5)])
        current_tree = STRtree([current_geom])
        v2_tree = STRtree([current_geom, review_geom])
        polygon = Polygon([(1, 4), (2, 4), (2, 6), (1, 6)])
        self.assertEqual(
            VISUALIZE.classify_slope_status(polygon, current_tree, [current_geom], v2_tree, [current_geom, review_geom]),
            "review",
        )

    def test_rank_hotspots_sorts_issue_cells_first(self) -> None:
        ranked = VISUALIZE.rank_hotspots(
            {
                (0, 0): VISUALIZE.Counter({"matched": 10, "review": 1}),
                (1, 0): VISUALIZE.Counter({"unmatched": 3}),
                (2, 0): VISUALIZE.Counter({"matched": 100}),
            },
            top_n=2,
        )
        self.assertEqual([cell for cell, _ in ranked], [(1, 0), (0, 0)])


if __name__ == "__main__":
    unittest.main()
