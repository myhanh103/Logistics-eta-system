from pydantic import BaseModel
from typing import Optional, List, Dict

class TripStatusResponse(BaseModel):
    trip_id: str
    vehicle_id: str
    status: str
    last_known_location: Optional[Dict[str, float]]
    last_timestamp: Optional[str]
    completed_stops: List[str]
    remaining_stops: List[str]
    current_next_stop: Optional[str]
    remaining_distance_km: float
    updated_eta_min: float
    delay_risk: str