from typing import Dict, Any, Optional
from app.services.route_selector import calculate_haversine_distance
from app.schemas.route import Location
from ml.inference.predict_eta import predict_eta

def calculate_realtime_eta_and_risk(
    current_lat: float,
    current_lng: float,
    next_stop_lat: float,
    next_stop_lng: float,
    speed_kmh: float = 0.0,
    departure_time: str = "2026-11-10T14:30:00Z",
    deadline_iso: Optional[str] = None
) -> Dict[str, Any]:
    loc1 = Location(lat=current_lat, lng=current_lng)
    loc2 = Location(lat=next_stop_lat, lng=next_stop_lng)
    
    remaining_dist_km = calculate_haversine_distance(loc1, loc2)
    if remaining_dist_km == 0:
        remaining_dist_km = 0.05

    try:
        ml_res = predict_eta(
            route_id="REALTIME_TRACK",
            distance_km=remaining_dist_km,
            departure_time=departure_time
        )
        calculated_eta = float(ml_res.get("predicted_eta_min", 15.0))
        source = "ML_RANDOM_FOREST"
    except Exception:
        calculated_eta = round((remaining_dist_km / 25.0) * 60, 2)
        source = "FALLBACK_HAVERSINE"

    traffic_warning = False
    warning_msg = None
    if 0 < speed_kmh < 10.0 and remaining_dist_km > 0.3:
        traffic_warning = True
        calculated_eta += 4.0
        warning_msg = "Phát hiện tốc độ di chuyển chậm (<10 km/h). ETA đã được cộng thêm 4 phút."

    delay_risk = "on_time"
    if calculated_eta > 30.0:
        delay_risk = "late"
    elif calculated_eta > 20.0:
        delay_risk = "at_risk"

    return {
        "remaining_distance_km": round(remaining_dist_km, 2),
        "updated_eta_min": round(calculated_eta, 1),
        "source": source,
        "delay_risk": delay_risk,
        "traffic_delay_warning": traffic_warning,
        "warning_message": warning_msg
    }