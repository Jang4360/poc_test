from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str):
    module_path = SCRIPTS_DIR / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", "").replace("-", "_"), module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PLACES = load_script("02_places_load.py")
ACCESS = load_script("03_accessibility_features_load.py")
SEGMENTS = load_script("04_segment_features_load.py")
SUBWAY = load_script("05_subway_elevators_load.py")
BUS = load_script("06_bims_bus_load.py")


class ReferenceLoadTests(unittest.TestCase):
    def test_parse_place_row_requires_core_fields(self) -> None:
        row = {
            "placeId": "7",
            "name": "Place",
            "category": "TOILET",
            "address": "",
            "point": "POINT(129.1 35.1)",
            "providerPlaceId": "",
        }
        self.assertEqual(
            PLACES.parse_place_row(row),
            (7, "Place", "TOILET", None, "POINT(129.1 35.1)", None),
        )

    def test_parse_feature_row_normalizes_boolean(self) -> None:
        row = {"id": "1", "placeId": "2", "featureType": "accessibleToilet", "isAvailable": "true"}
        self.assertEqual(
            ACCESS.parse_feature_row(row),
            (1, 2, "accessibleToilet", True),
        )

    def test_normalize_audio_row_requires_point_and_marks_working_state(self) -> None:
        row = {
            "sourceId": "audio:1",
            "point": "POINT(129.1 35.1)",
            "audioSignalState": "YES",
            "stat": "정상동작",
        }
        self.assertEqual(
            SEGMENTS.normalize_audio_row(row),
            ("audio:1", "POINT(129.1 35.1)", "YES", True),
        )
        self.assertIsNone(SEGMENTS.normalize_audio_row({"sourceId": "audio:2", "point": ""}))

    def test_normalize_crosswalk_row_parses_optional_width(self) -> None:
        row = {
            "sourceId": "crosswalk:1",
            "point": "POINT(129.1 35.1)",
            "crossingState": "TRAFFIC_SIGNALS",
            "widthMeter": "6",
        }
        self.assertEqual(
            SEGMENTS.normalize_crosswalk_row(row),
            ("crosswalk:1", "POINT(129.1 35.1)", "TRAFFIC_SIGNALS", 6.0),
        )

    def test_normalize_slope_row_uses_4326_geometry_and_parses_numbers(self) -> None:
        row = {
            "geometry_wkt_4326": "MULTIPOLYGON(((129.0 35.0,129.1 35.0,129.1 35.1,129.0 35.0)))",
            "metric_mean": "4.5",
            "width_meter": "2.0",
        }
        self.assertEqual(
            SEGMENTS.normalize_slope_row(row, 3),
            ("slope:3", "MULTIPOLYGON(((129.0 35.0,129.1 35.0,129.1 35.1,129.0 35.0)))", 4.5, 2.0),
        )

    def test_normalize_elevator_row_requires_point(self) -> None:
        row = {
            "elevatorId": "17",
            "point": "POINT(129.1 35.1)",
        }
        self.assertEqual(
            SEGMENTS.normalize_elevator_row(row),
            ("elevator:17", "POINT(129.1 35.1)"),
        )
        self.assertIsNone(SEGMENTS.normalize_elevator_row({"elevatorId": "18", "point": ""}))

    def test_classify_distance_band_matches_plan_thresholds(self) -> None:
        self.assertEqual(SEGMENTS.classify_distance_band(10.0, 15.0, 30.0), "AUTO_UPDATE")
        self.assertEqual(SEGMENTS.classify_distance_band(22.0, 15.0, 30.0), "REVIEW_REQUIRED")
        self.assertEqual(SEGMENTS.classify_distance_band(31.0, 15.0, 30.0), "UNMATCHED")
        self.assertEqual(SEGMENTS.classify_distance_band(None, 15.0, 30.0), "UNMATCHED")

    def test_dedupe_elevator_rows_keeps_lowest_elevator_id(self) -> None:
        rows = [
            (2, "134", "노포", "1", "2", "POINT(1 2)"),
            (1, "134", "노포", "1", "2", "POINT(1 2)"),
            (3, "135", "범어사", "1", "1", "POINT(3 4)"),
        ]
        deduped, duplicates = SUBWAY.dedupe_elevator_rows(rows)
        self.assertEqual(duplicates, 1)
        self.assertEqual(len(deduped), 2)
        self.assertIn((1, "134", "노포", "1", "2", "POINT(1 2)"), deduped)

    def test_extract_catalog_route_identity_supports_common_bims_field_names(self) -> None:
        item = {"lineid": "5200000086", "buslinenum": "86", "bustype": "일반버스"}
        self.assertEqual(BUS.extract_catalog_route_identity(item), ("5200000086", "86"))

    def test_normalize_exact_text_returns_empty_string_for_none(self) -> None:
        self.assertEqual(BUS.normalize_exact_text(None), "")

    def test_load_static_route_aggregates_groups_low_floor_by_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "routes.csv"
            csv_path.write_bytes(
                (
                    "운수사,인가노선,차량번호,운행구분,상용구분,차량구분,연료,연식\r\n"
                    "국제여객,10,부산70자1001,일반,상용,대형,CNG,2022\r\n"
                    "국제여객,10,부산70자1004,저상,상용,대형,전기,2024\r\n"
                    "화신여객,131,부산70자2001,일반,상용,대형,CNG,2020\r\n"
                ).encode("cp949")
            )
            aggregates, source_row_count, skipped_rows = BUS.load_static_route_aggregates(csv_path)

        self.assertEqual(source_row_count, 3)
        self.assertEqual(skipped_rows, 0)
        self.assertEqual(
            aggregates,
            {
                "10": {"lowFloorVehicleCount": 1, "totalVehicleCount": 2},
                "131": {"lowFloorVehicleCount": 0, "totalVehicleCount": 1},
            },
        )

    def test_build_bims_route_catalog_rejects_conflicting_route_ids(self) -> None:
        with self.assertRaises(BUS.BimsLoadError):
            BUS.build_bims_route_catalog(
                [
                    {"lineid": "5200000010", "buslinenum": "10"},
                    {"lineid": "5200999999", "buslinenum": "10"},
                ]
            )

    def test_build_bims_route_catalog_counts_true_duplicates(self) -> None:
        catalog, duplicate_route_nos = BUS.build_bims_route_catalog(
            [
                {"lineid": "5200000010", "buslinenum": "10"},
                {"lineid": "5200000010", "buslinenum": "10"},
            ]
        )
        self.assertEqual(catalog, {"10": "5200000010"})
        self.assertEqual(duplicate_route_nos, 1)

    def test_load_elevator_rows_skips_invalid_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "elevators.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "elevatorId,stationId,stationName,lineName,entranceNo,point",
                        "1,134,노포,1,2,POINT(129.09 35.28)",
                        "2,133,범어사,1,4,",
                    ]
                ),
                encoding="utf-8",
            )
            rows, skipped = SEGMENTS.load_elevator_rows(csv_path)

        self.assertEqual(rows, [("elevator:1", "POINT(129.09 35.28)")])
        self.assertEqual(skipped, 1)

    def test_build_low_floor_rows_marks_unmatched_routes(self) -> None:
        rows, report_routes, unmatched_count = BUS.build_low_floor_rows(
            {
                "10": {"lowFloorVehicleCount": 1, "totalVehicleCount": 2},
                "131": {"lowFloorVehicleCount": 0, "totalVehicleCount": 1},
            },
            {"10": "5200000010"},
        )

        self.assertEqual(rows, [("5200000010", "10", True)])
        self.assertEqual(unmatched_count, 1)
        self.assertEqual(
            next(route for route in report_routes if route["routeNo"] == "131")["unmatchedReason"],
            "NO_BIMS_ROUTE_ID_MATCH",
        )

    def test_should_fail_on_unmatched_skips_failure_for_dry_run(self) -> None:
        self.assertFalse(BUS.should_fail_on_unmatched(1, allow_unmatched_skip=False, dry_run=True))
        self.assertFalse(BUS.should_fail_on_unmatched(1, allow_unmatched_skip=True, dry_run=False))
        self.assertTrue(BUS.should_fail_on_unmatched(1, allow_unmatched_skip=False, dry_run=False))

    def test_build_report_payload_includes_status(self) -> None:
        payload = BUS.build_report_payload(
            Path("/tmp/routes.csv"),
            {"10": {"lowFloorVehicleCount": 1, "totalVehicleCount": 2}},
            {"10": "5200000010"},
            [
                {
                    "routeNo": "10",
                    "routeId": "5200000010",
                    "hasLowFloor": True,
                    "lowFloorVehicleCount": 1,
                    "totalVehicleCount": 2,
                }
            ],
            source_row_count=2,
            skipped_rows=0,
            status="dry_run",
            error=None,
            unmatched_skip_applied=False,
        )
        self.assertEqual(payload["status"], "dry_run")
        self.assertEqual(payload["matchedRouteCount"], 1)

    def test_resolve_low_floor_table_layout_supports_camel_and_snake_case(self) -> None:
        self.assertEqual(
            BUS.resolve_low_floor_table_layout(["routeId", "routeNo", "hasLowFloor"]),
            ("routeId", "routeNo", "hasLowFloor"),
        )
        self.assertEqual(
            BUS.resolve_low_floor_table_layout(["route_id", "route_no", "has_low_floor"]),
            ("route_id", "route_no", "has_low_floor"),
        )

    def test_parse_place_row_raises_value_error_for_blank_name(self) -> None:
        with self.assertRaises(ValueError):
            PLACES.parse_place_row(
                {"placeId": "1", "name": "", "category": "TOILET", "point": "POINT(1 2)"}
            )

    def test_parse_feature_row_raises_value_error_for_blank_feature_type(self) -> None:
        with self.assertRaises(ValueError):
            ACCESS.parse_feature_row({"id": "1", "placeId": "2", "featureType": "", "isAvailable": "true"})

    def test_crosswalk_priority_traffic_signals_beats_unknown(self) -> None:
        # crossing_state priority: TRAFFIC_SIGNALS=2 > NO=1 > UNKNOWN=0.
        # Verify normalize_crosswalk_row returns the raw value without clamping (ordering is done in SQL).
        row = {
            "sourceId": "cw:1",
            "point": "POINT(129.1 35.1)",
            "crossingState": "TRAFFIC_SIGNALS",
            "widthMeter": "",
        }
        result = SEGMENTS.normalize_crosswalk_row(row)
        self.assertIsNotNone(result)
        self.assertEqual(result[2], "TRAFFIC_SIGNALS")

    def test_segments_module_has_no_feature_id_offset(self) -> None:
        """feature_id_offset must be removed after BIGSERIAL migration."""
        self.assertFalse(
            hasattr(SEGMENTS, "feature_id_offset"),
            "feature_id_offset should be removed after BIGSERIAL migration",
        )

    def test_shared_module_has_no_chunked(self) -> None:
        """chunked() must be removed; execute_values page_size handles batching."""
        import importlib.util as ilu

        shared_path = SCRIPTS_DIR / "_shared.py"
        spec = ilu.spec_from_file_location("_shared_test", shared_path)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertFalse(hasattr(mod, "chunked"), "chunked() should be removed from _shared.py")

    def test_fetch_bims_route_items_uses_single_request_for_bus_info(self) -> None:
        response = mock.Mock()
        response.json.return_value = {
            "response": {
                "body": {
                    "items": {
                        "item": [
                            {"lineid": "5200000086", "buslinenum": "86", "bustype": "일반버스"},
                        ]
                    }
                }
            }
        }
        response.raise_for_status.return_value = None

        session = mock.Mock()
        session.get.return_value = response

        with mock.patch.object(BUS.requests, "Session", return_value=session):
            items = BUS.fetch_bims_route_items("service-key", "https://example.test")

        self.assertEqual(len(items), 1)
        session.get.assert_called_once_with(
            "https://example.test/busInfo",
            params={"serviceKey": "service-key"},
            timeout=20,
        )


if __name__ == "__main__":
    unittest.main()
