"""Chon tuyen giao hang tu nhieu tuyen ung vien (Smart Logistics - Tuan 2).

Hop dong input/output (schema_version 1.0) duoc mo ta o docs/API_CONTRACT.md.

Quy tac chon tuyen (xac dinh, co thu tu uu tien):
    1. predicted_eta_minutes nho nhat
    2. neu bang nhau: distance_km nho hon
    3. neu van bang nhau: route_id theo thu tu bang chu cai

Ba ham cong khai:
    select_route(payload)  -> dict ket qua, nem RouteSelectionError neu input sai
    handle_request(payload) -> dict, KHONG nem loi; loi tra ve dang status="error"
    handle_json(text)       -> str JSON, dung cho Backend nhan chuoi JSON
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from typing import Any

SCHEMA_VERSION = "1.0"

ERR_INVALID_JSON = "INVALID_JSON"
ERR_INVALID_REQUEST = "INVALID_REQUEST"
ERR_UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
ERR_MISSING_FIELD = "MISSING_FIELD"
ERR_INVALID_TYPE = "INVALID_TYPE"
ERR_INVALID_VALUE = "INVALID_VALUE"
ERR_EMPTY_CANDIDATES = "EMPTY_CANDIDATES"
ERR_DUPLICATE_ROUTE_ID = "DUPLICATE_ROUTE_ID"


class RouteSelectionError(Exception):
    """Loi input co ma loi on dinh de Backend xu ly."""

    def __init__(self, code: str, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _read_positive_number(route: dict, key: str, prefix: str) -> float:
    field = f"{prefix}.{key}"
    if key not in route:
        raise RouteSelectionError(ERR_MISSING_FIELD, f"Thieu truong '{key}'.", field)
    value = route[key]
    if not _is_number(value):
        raise RouteSelectionError(ERR_INVALID_TYPE, f"'{key}' phai la so.", field)
    if not math.isfinite(value) or value <= 0:
        raise RouteSelectionError(
            ERR_INVALID_VALUE, f"'{key}' phai la so huu han lon hon 0.", field
        )
    return value


def _validate_request(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        raise RouteSelectionError(ERR_INVALID_REQUEST, "Request phai la mot JSON object.")

    version = payload.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise RouteSelectionError(
            ERR_UNSUPPORTED_SCHEMA_VERSION,
            f"Chi ho tro schema_version '{SCHEMA_VERSION}'.",
            "schema_version",
        )

    if "candidate_routes" not in payload:
        raise RouteSelectionError(
            ERR_MISSING_FIELD, "Thieu truong 'candidate_routes'.", "candidate_routes"
        )
    candidates = payload["candidate_routes"]
    if not isinstance(candidates, list):
        raise RouteSelectionError(
            ERR_INVALID_TYPE, "'candidate_routes' phai la danh sach.", "candidate_routes"
        )
    if not candidates:
        raise RouteSelectionError(
            ERR_EMPTY_CANDIDATES,
            "Can it nhat mot tuyen ung vien.",
            "candidate_routes",
        )

    seen: set[str] = set()
    cleaned: list[dict] = []
    for index, route in enumerate(candidates):
        prefix = f"candidate_routes[{index}]"
        if not isinstance(route, dict):
            raise RouteSelectionError(
                ERR_INVALID_TYPE, "Moi tuyen phai la JSON object.", prefix
            )
        if "route_id" not in route:
            raise RouteSelectionError(
                ERR_MISSING_FIELD, "Thieu truong 'route_id'.", f"{prefix}.route_id"
            )
        route_id = route["route_id"]
        if not isinstance(route_id, str):
            raise RouteSelectionError(
                ERR_INVALID_TYPE, "'route_id' phai la chuoi.", f"{prefix}.route_id"
            )
        if not route_id.strip():
            raise RouteSelectionError(
                ERR_INVALID_VALUE, "'route_id' khong duoc rong.", f"{prefix}.route_id"
            )
        if route_id in seen:
            raise RouteSelectionError(
                ERR_DUPLICATE_ROUTE_ID,
                f"route_id '{route_id}' bi trung.",
                f"{prefix}.route_id",
            )
        seen.add(route_id)
        cleaned.append(
            {
                "route_id": route_id,
                "distance_km": _read_positive_number(route, "distance_km", prefix),
                "predicted_eta_minutes": _read_positive_number(
                    route, "predicted_eta_minutes", prefix
                ),
            }
        )
    return cleaned


def _sort_key(route: dict) -> tuple:
    return (route["predicted_eta_minutes"], route["distance_km"], route["route_id"])


def select_route(payload: Any) -> dict:
    """Chon tuyen tot nhat. Nem RouteSelectionError neu input khong hop le."""
    routes = _validate_request(payload)
    ranked = sorted(routes, key=_sort_key)

    best_eta = ranked[0]["predicted_eta_minutes"]
    tie_break_applied = sum(1 for r in ranked if r["predicted_eta_minutes"] == best_eta) > 1

    ranking = [{"rank": i, **route} for i, route in enumerate(ranked, start=1)]
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": payload.get("request_id"),
        "order_id": payload.get("order_id"),
        "status": "ok",
        "selected_route": dict(ranked[0]),
        "ranking": ranking,
        "candidates_evaluated": len(ranked),
        "tie_break_applied": tie_break_applied,
    }


def _error_response(payload: Any, error: RouteSelectionError) -> dict:
    meta = payload if isinstance(payload, dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": meta.get("request_id"),
        "order_id": meta.get("order_id"),
        "status": "error",
        "error": {"code": error.code, "message": error.message, "field": error.field},
    }


def handle_request(payload: Any) -> dict:
    """Giong select_route nhung khong nem loi; loi duoc dong goi trong response."""
    try:
        return select_route(payload)
    except RouteSelectionError as error:
        return _error_response(payload, error)


def handle_json(text: str) -> str:
    """Nhan chuoi JSON, tra ve chuoi JSON (UTF-8, indent=2)."""
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        error = RouteSelectionError(ERR_INVALID_JSON, "Chuoi dau vao khong phai JSON hop le.")
        return json.dumps(_error_response(None, error), ensure_ascii=False, indent=2)
    return json.dumps(handle_request(payload), ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chon tuyen giao hang tu file JSON request.")
    parser.add_argument("request_file", help="Duong dan file JSON request")
    args = parser.parse_args(argv)

    with open(args.request_file, encoding="utf-8") as handle:
        output = handle_json(handle.read())
    print(output)
    return 0 if json.loads(output)["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
