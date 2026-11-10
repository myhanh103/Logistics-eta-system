from datetime import datetime
from typing import Dict, Any, Optional
from math import radians, cos, sin, asin, sqrt

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    return R * 2 * asin(sqrt(a))

class TripStateStore:
    def __init__(self):
        self._trips: Dict[str, Dict[str, Any]] = {
            "TRIP_101": {
                "trip_id": "TRIP_101",
                "vehicle_id": "TRUCK_01",
                "status": "IN_TRANSIT",
                "depot": {"lat": 10.7691, "lng": 106.7064},
                "stops": [
                    {"order_id": "ORD_01", "lat": 10.7760, "lng": 106.7062, "status": "COMPLETED"},
                    {"order_id": "ORD_02", "lat": 10.7843, "lng": 106.7064, "status": "PENDING"},
                    {"order_id": "ORD_03", "lat": 10.8021, "lng": 106.6438, "status": "PENDING"}
                ],
                "last_location": {"lat": 10.7760, "lng": 106.7062},
                "last_timestamp": "2026-11-10T14:10:00Z",
                "current_eta_min": 18.0,
                "remaining_distance_km": 5.2,
                "delay_risk": "on_time"
            }
        }

    def get_trip(self, trip_id: str) -> Optional[Dict[str, Any]]:
        return self._trips.get(trip_id)

    def process_gps_ping(
        self, 
        trip_id: str, 
        lat: float, 
        lng: float, 
        timestamp_str: str, 
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        trip = self.get_trip(trip_id)
        if not trip:
            trip = {
                "trip_id": trip_id,
                "vehicle_id": device_id or "TRUCK_DEFAULT",
                "status": "IN_TRANSIT",
                "depot": {"lat": lat, "lng": lng},
                "stops": [
                    {"order_id": "ORD_NEXT", "lat": lat + 0.015, "lng": lng + 0.015, "status": "PENDING"}
                ],
                "last_location": None,
                "last_timestamp": None,
                "current_eta_min": 20.0,
                "remaining_distance_km": 3.0,
                "delay_risk": "on_time"
            }
            self._trips[trip_id] = trip

        # Chặn GPS trùng hoặc cũ timestamp (4.5.6)
        if trip["last_timestamp"]:
            try:
                new_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(trip["last_timestamp"].replace('Z', '+00:00'))
                if new_dt <= last_dt:
                    raise ValueError("Tín hiệu GPS có timestamp cũ hoặc trùng lặp với thời gian trước đó")
            except ValueError as ve:
                if "timestamp cũ" in str(ve):
                    raise ve

        completed = []
        next_stop = None
        
        for stop in trip["stops"]:
            if stop["status"] == "COMPLETED":
                completed.append(stop["order_id"])
            elif stop["status"] == "PENDING":
                dist = haversine(lat, lng, stop["lat"], stop["lng"])
                if dist <= 0.15: # < 150m
                    stop["status"] = "COMPLETED"
                    completed.append(stop["order_id"])
                elif not next_stop:
                    next_stop = stop

        trip["last_location"] = {"lat": lat, "lng": lng}
        trip["last_timestamp"] = timestamp_str
        if device_id:
            trip["vehicle_id"] = device_id

        return {
            "trip": trip,
            "completed_stops": completed,
            "next_stop": next_stop
        }

trip_state_service = TripStateStore()