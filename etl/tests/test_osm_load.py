from __future__ import annotations

import importlib.util
import tempfile
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "01_osm_load.py"
SPEC = importlib.util.spec_from_file_location("etl_01_osm_load", MODULE_PATH)
OSM_LOAD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = OSM_LOAD
SPEC.loader.exec_module(OSM_LOAD)


WayRecord = OSM_LOAD.WayRecord
NetworkBuildError = OSM_LOAD.NetworkBuildError


class OsmLoadTests(unittest.TestCase):
    def test_is_walkable_respects_include_and_exclude_rules(self) -> None:
        self.assertTrue(OSM_LOAD.is_walkable({"highway": "footway"}))
        self.assertTrue(OSM_LOAD.is_walkable({"highway": "primary", "sidewalk": "both"}))
        self.assertTrue(OSM_LOAD.is_walkable({"foot": "designated"}))
        self.assertFalse(OSM_LOAD.is_walkable({"highway": "motorway"}))
        self.assertFalse(OSM_LOAD.is_walkable({"highway": "footway", "foot": "no"}))
        self.assertFalse(OSM_LOAD.is_walkable({"highway": "service", "access": "private"}))

    def test_identify_anchors_includes_endpoints_intersections_and_tagged_nodes(self) -> None:
        ways = {
            10: WayRecord(10, (1, 2, 3), {"highway": "footway"}),
            20: WayRecord(20, (3, 4, 5), {"highway": "residential"}),
        }
        anchors = OSM_LOAD.identify_anchors(ways, {1: 1, 2: 1, 3: 2, 4: 1, 5: 1}, {4})
        self.assertEqual(anchors, {1, 3, 4, 5})

    def test_split_way_to_segments_breaks_on_anchor_nodes(self) -> None:
        segments = OSM_LOAD.split_way_to_segments(77, (1, 2, 3, 4, 5), {1, 3, 5})
        self.assertEqual(
            [
                (segment.from_osm_node_id, segment.to_osm_node_id, segment.ordinal, segment.path_node_ids)
                for segment in segments
            ],
            [
                (1, 3, 0, (1, 2, 3)),
                (3, 5, 1, (3, 4, 5)),
            ],
        )

    def test_build_network_artifacts_creates_deterministic_nodes_and_segments(self) -> None:
        ways = {
            100: WayRecord(100, (1, 2, 3), {"highway": "footway"}),
            200: WayRecord(200, (3, 4), {"highway": "residential", "sidewalk": "both"}),
        }
        road_nodes, road_segments, stats = OSM_LOAD.build_network_artifacts(
            walkable_ways=ways,
            node_way_counts={1: 1, 2: 1, 3: 2, 4: 1},
            node_coords={
                1: (129.0, 35.0),
                2: (129.0003, 35.0002),
                3: (129.0006, 35.0004),
                4: (129.0010, 35.0006),
            },
            tagged_anchor_nodes=set(),
        )

        self.assertEqual([node["osm_node_id"] for node in road_nodes], [1, 3, 4])
        self.assertEqual(stats["segment_count"], 2)
        self.assertEqual(
            [
                (
                    segment["source_way_id"],
                    segment["source_osm_from_node_id"],
                    segment["source_osm_to_node_id"],
                    segment["segment_ordinal"],
                    segment["walk_access"],
                )
                for segment in road_segments
            ],
            [
                (100, 1, 3, 0, "ALLOWED"),
                (200, 3, 4, 0, "SIDEWALK"),
            ],
        )
        self.assertGreater(road_segments[0]["length_m"], 0)
        self.assertTrue(str(road_segments[0]["geom_wkt"]).startswith("LINESTRING ("))

    def test_build_network_artifacts_raises_when_network_is_empty(self) -> None:
        with self.assertRaises(NetworkBuildError):
            OSM_LOAD.build_network_artifacts({}, {}, {}, set())

    def test_validate_preflight_report_rejects_nonempty_targets_without_truncate(self) -> None:
        report = OSM_LOAD.PreflightReport(
            road_nodes_exists=True,
            road_segments_exists=True,
            segment_features_exists=True,
            road_nodes_osm_unique=True,
            road_segments_source_unique=True,
            road_segments_geom_gist=True,
            target_state=OSM_LOAD.TargetState(road_node_count=1, road_segment_count=0, segment_feature_count=0),
        )

        with self.assertRaises(NetworkBuildError):
            OSM_LOAD.validate_preflight_report(report, truncate=False)

    def test_snapshot_round_trip_preserves_build_payload(self) -> None:
        road_nodes = [{"vertex_id": 1, "osm_node_id": 100, "lon": 129.1, "lat": 35.1}]
        road_segments = [
            {
                "edge_id": 1,
                "from_node_id": 1,
                "to_node_id": 2,
                "geom_wkt": "LINESTRING (129.1 35.1, 129.2 35.2)",
                "length_m": 15.5,
                "source_way_id": 11,
                "source_osm_from_node_id": 100,
                "source_osm_to_node_id": 200,
                "segment_ordinal": 0,
                "walk_access": "ALLOWED",
            }
        ]
        build_stats = {"segment_count": 1}

        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.pkl.gz"
            OSM_LOAD.save_snapshot(snapshot_path, road_nodes, road_segments, build_stats)
            loaded_nodes, loaded_segments, loaded_stats = OSM_LOAD.load_snapshot(snapshot_path)

        self.assertEqual(loaded_nodes, road_nodes)
        self.assertEqual(loaded_segments, road_segments)
        self.assertEqual(loaded_stats, build_stats)


if __name__ == "__main__":
    unittest.main()
