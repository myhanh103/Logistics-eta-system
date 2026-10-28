import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import route_selector as rs

EXAMPLES = ROOT / "examples"


def make_request(routes, **extra):
    payload = {
        "schema_version": "1.0",
        "request_id": "REQ-T",
        "order_id": "ORD-T",
        "candidate_routes": routes,
    }
    payload.update(extra)
    return payload


def route(route_id, distance_km, eta):
    return {"route_id": route_id, "distance_km": distance_km, "predicted_eta_minutes": eta}


class SelectionRulesTests(unittest.TestCase):
    def test_01_single_candidate_is_selected(self):
        result = rs.handle_request(make_request([route("R1", 10.0, 30.0)]))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected_route"]["route_id"], "R1")
        self.assertEqual(result["candidates_evaluated"], 1)
        self.assertFalse(result["tie_break_applied"])

    def test_02_lowest_eta_is_selected(self):
        routes = [route("R1", 12.4, 38.5), route("R2", 9.8, 35.0), route("R3", 15.1, 41.2)]
        result = rs.handle_request(make_request(routes))
        self.assertEqual(result["selected_route"]["route_id"], "R2")

    def test_03_equal_eta_prefers_shorter_distance(self):
        routes = [route("R1", 12.0, 30.0), route("R2", 9.0, 30.0)]
        result = rs.handle_request(make_request(routes))
        self.assertEqual(result["selected_route"]["route_id"], "R2")
        self.assertTrue(result["tie_break_applied"])

    def test_04_equal_eta_and_distance_prefers_smaller_route_id(self):
        routes = [route("R9", 10.0, 30.0), route("R2", 10.0, 30.0)]
        result = rs.handle_request(make_request(routes))
        self.assertEqual(result["selected_route"]["route_id"], "R2")
        self.assertTrue(result["tie_break_applied"])

    def test_05_ranking_is_sorted_with_consecutive_ranks(self):
        routes = [route("R1", 12.4, 38.5), route("R2", 9.8, 35.0), route("R3", 15.1, 41.2)]
        result = rs.handle_request(make_request(routes))
        self.assertEqual([r["route_id"] for r in result["ranking"]], ["R2", "R1", "R3"])
        self.assertEqual([r["rank"] for r in result["ranking"]], [1, 2, 3])
        self.assertEqual(result["candidates_evaluated"], 3)

    def test_06_input_payload_is_not_mutated(self):
        payload = make_request([route("R1", 12.4, 38.5), route("R2", 9.8, 35.0)])
        snapshot = copy.deepcopy(payload)
        rs.handle_request(payload)
        self.assertEqual(payload, snapshot)


class ResponseContractTests(unittest.TestCase):
    def test_07_success_response_has_contract_keys(self):
        result = rs.handle_request(make_request([route("R1", 10.0, 30.0)]))
        self.assertEqual(
            set(result),
            {
                "schema_version",
                "request_id",
                "order_id",
                "status",
                "selected_route",
                "ranking",
                "candidates_evaluated",
                "tie_break_applied",
            },
        )
        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(
            set(result["selected_route"]),
            {"route_id", "distance_km", "predicted_eta_minutes"},
        )

    def test_08_request_and_order_id_are_echoed_or_null(self):
        result = rs.handle_request(make_request([route("R1", 10.0, 30.0)]))
        self.assertEqual(result["request_id"], "REQ-T")
        self.assertEqual(result["order_id"], "ORD-T")
        bare = {"candidate_routes": [route("R1", 10.0, 30.0)]}
        result = rs.handle_request(bare)
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["request_id"])
        self.assertIsNone(result["order_id"])


class ErrorHandlingTests(unittest.TestCase):
    def assert_error(self, result, code, field=None):
        self.assertEqual(result["status"], "error")
        self.assertEqual(set(result["error"]), {"code", "message", "field"})
        self.assertEqual(result["error"]["code"], code)
        self.assertTrue(result["error"]["message"])
        if field is not None:
            self.assertEqual(result["error"]["field"], field)
        self.assertNotIn("selected_route", result)

    def test_09_malformed_input_is_rejected(self):
        self.assert_error(rs.handle_request([1, 2, 3]), rs.ERR_INVALID_REQUEST)
        self.assert_error(rs.handle_request(None), rs.ERR_INVALID_REQUEST)
        output = json.loads(rs.handle_json("{not valid json"))
        self.assert_error(output, rs.ERR_INVALID_JSON)

    def test_10_missing_candidate_routes(self):
        payload = {"schema_version": "1.0", "request_id": "REQ-X"}
        result = rs.handle_request(payload)
        self.assert_error(result, rs.ERR_MISSING_FIELD, "candidate_routes")
        self.assertEqual(result["request_id"], "REQ-X")

    def test_11_empty_candidate_list(self):
        result = rs.handle_request(make_request([]))
        self.assert_error(result, rs.ERR_EMPTY_CANDIDATES, "candidate_routes")

    def test_12_missing_eta_reports_field_path(self):
        routes = [route("R1", 10.0, 30.0), {"route_id": "R2", "distance_km": 8.0}]
        result = rs.handle_request(make_request(routes))
        self.assert_error(
            result, rs.ERR_MISSING_FIELD, "candidate_routes[1].predicted_eta_minutes"
        )

    def test_13_string_number_is_invalid_type(self):
        result = rs.handle_request(make_request([route("R1", 10.0, "30")]))
        self.assert_error(
            result, rs.ERR_INVALID_TYPE, "candidate_routes[0].predicted_eta_minutes"
        )

    def test_14_boolean_is_not_accepted_as_number(self):
        result = rs.handle_request(make_request([route("R1", True, 30.0)]))
        self.assert_error(result, rs.ERR_INVALID_TYPE, "candidate_routes[0].distance_km")

    def test_15_non_positive_or_non_finite_values_are_invalid(self):
        for bad in (0, -5, -0.1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=bad):
                result = rs.handle_request(make_request([route("R1", 10.0, bad)]))
                self.assert_error(
                    result,
                    rs.ERR_INVALID_VALUE,
                    "candidate_routes[0].predicted_eta_minutes",
                )

    def test_16_duplicate_route_id(self):
        routes = [route("R1", 10.0, 30.0), route("R1", 9.0, 28.0)]
        result = rs.handle_request(make_request(routes))
        self.assert_error(result, rs.ERR_DUPLICATE_ROUTE_ID, "candidate_routes[1].route_id")

    def test_17_unsupported_schema_version(self):
        payload = make_request([route("R1", 10.0, 30.0)], schema_version="2.0")
        result = rs.handle_request(payload)
        self.assert_error(result, rs.ERR_UNSUPPORTED_SCHEMA_VERSION, "schema_version")


class SampleJsonTests(unittest.TestCase):
    def read_json(self, name):
        return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))

    def test_18_sample_json_files_match_actual_output(self):
        request = (EXAMPLES / "sample_request.json").read_text(encoding="utf-8")
        actual = json.loads(rs.handle_json(request))
        self.assertEqual(actual, self.read_json("sample_response.json"))
        self.assertEqual(actual["status"], "ok")

        bad_request = (EXAMPLES / "sample_request_error.json").read_text(encoding="utf-8")
        actual_error = json.loads(rs.handle_json(bad_request))
        self.assertEqual(actual_error, self.read_json("sample_response_error.json"))
        self.assertEqual(actual_error["status"], "error")


if __name__ == "__main__":
    unittest.main()
