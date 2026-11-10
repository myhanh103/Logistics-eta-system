from pydantic import BaseModel, Field
from typing import Optional, Dict, List

# ==========================================
# Schemas Tuần 3 (API /gps/track)
# ==========================================
class GpsPingRequest(BaseModel):
    device_id: str = Field(..., description="Mã thiết bị", json_schema_extra={"example": "TRUCK_01"})
    lat: float = Field(..., ge=-90.0, le=90.0, description="Vĩ độ", json_schema_extra={"example": 10.7769})
    lng: float = Field(..., ge=-180.0, le=180.0, description="Kinh độ", json_schema_extra={"example": 106.7009})
    timestamp: str = Field(..., description="Thời gian ghi nhận GPS (ISO format)", json_schema_extra={"example": "2026-11-10T14:30:00Z"})

class GpsPingResponse(BaseModel):
    status: str
    device_id: str
    message: str
    recorded_at: str

# ==========================================
# Schemas Tuần 4 (API /gps/ingest)
# ==========================================
class GpsIngestRequest(BaseModel):
    trip_id: str = Field(..., description="Mã chuyến đi", json_schema_extra={"example": "TRIP_101"})
    device_id: Optional[str] = Field("TRUCK_DEFAULT", description="Mã thiết bị", json_schema_extra={"example": "TRUCK_01"})
    lat: float = Field(..., ge=-90.0, le=90.0, description="Vĩ độ", json_schema_extra={"example": 10.7769})
    lng: float = Field(..., ge=-180.0, le=180.0, description="Kinh độ", json_schema_extra={"example": 106.7009})
    speed_kmh: Optional[float] = Field(0.0, ge=0.0, description="Tốc độ (km/h)", json_schema_extra={"example": 35.5})
    timestamp: str = Field(..., description="Thời gian ghi nhận GPS (ISO format)", json_schema_extra={"example": "2026-11-10T14:30:00Z"})

class GpsIngestResponse(BaseModel):
    status: str
    trip_id: str
    current_location: Dict[str, float]
    next_stop_id: Optional[str]
    completed_stops: List[str]
    remaining_distance_km: float
    updated_eta_min: float
    delay_risk: str
    source: str
    traffic_delay_warning: bool
    message: str