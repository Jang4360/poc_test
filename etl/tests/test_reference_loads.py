from __future__ import annotations

import importlib.util
import sys
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

    def test_extract_route_row_supports_common_bims_field_names(self) -> None:
        item = {"lineid": "5200000086", "buslinenum": "86", "lowplate": "1"}
        self.assertEqual(BUS.extract_route_row(item), ("5200000086", "86", True))
        bustype_item = {"lineid": "5200179000", "buslinenum": "179", "bustype": "저상버스"}
        self.assertEqual(BUS.extract_route_row(bustype_item), ("5200179000", "179", True))

    def test_normalize_route_rows_requires_low_floor_signal(self) -> None:
        with self.assertRaises(BUS.BimsLoadError):
            BUS.normalize_route_rows([{"routeId": "1", "routeNo": "1"}])

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
                            {"lineid": "5200000086", "buslinenum": "86", "lowplate": "1"},
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
