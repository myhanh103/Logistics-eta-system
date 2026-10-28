
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from requests.exceptions import RequestException

from app.services.osrm_adapter import get_candidate_routes

# Thuật toán Người 4
from src.route_selector import handle_request


router = APIRouter()


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class CompareRequest(BaseModel):
    origin: Point
    destination: Point
    departure_time: datetime


@router.post("/routes/compare")
def compare_routes(payload: CompareRequest):

    # BƯỚC 1: Lấy các tuyến thực tế từ OSRM
    try:
        routes = get_candidate_routes(
            payload.origin.model_dump(),
            payload.destination.model_dump()
        )

    except (RequestException, RuntimeError, ValueError) as error:
        raise HTTPException(
            status_code=502,
            detail=f"Không lấy được tuyến OSRM: {error}"
        )

    if not routes:
        raise HTTPException(
            status_code=502,
            detail="OSRM không trả về tuyến đường."
        )

    # BƯỚC 2: Gắn thời gian OSRM vào dữ liệu
    for route in routes:
        route["predicted_duration_min"] = route[
            "osrm_duration_min"
        ]

        route["prediction_source"] = "osrm_fallback_not_ml"

    # BƯỚC 3: Chuẩn hóa đầu vào cho Người 4
    selector_input = {
        "schema_version": "1.0",
        "candidate_routes": [
            {
                "route_id": route["route_id"],
                "distance_km": route["distance_km"],
                "predicted_eta_minutes": route[
                    "predicted_duration_min"
                ]
            }
            for route in routes
        ]
    }

    # BƯỚC 4: Gọi thuật toán chọn tuyến Người 4
    selection = handle_request(selector_input)

    if selection["status"] != "ok":
        raise HTTPException(
            status_code=422,
            detail=selection["error"]
        )

    # BƯỚC 5: Trả dữ liệu cho React
    return {
        "recommended_route_id": selection[
            "selected_route"
        ]["route_id"],

        "candidate_routes": routes,

        "ranking": selection["ranking"],

        "selection_reason": (
            "Chọn tuyến có thời gian OSRM thấp nhất; "
            "nếu bằng nhau thì xét khoảng cách."
        ),

        "prediction_source": "osrm_fallback_not_ml"
    }
