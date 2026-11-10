import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_gps_ingest_success():
    payload = {
        "trip_id": "TRIP_101",
        "device_id": "TRUCK_01",
        "lat": 10.7769,
        "lng": 106.7009,
        "speed_kmh": 35.0,
        "timestamp": "2026-11-10T14:30:00Z"
    }
    response = client.post("/api/v1/gps/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["trip_id"] == "TRIP_101"

def test_gps_ingest_duplicate_timestamp_error():
    payload = {
        "trip_id": "TRIP_101",
        "device_id": "TRUCK_01",
        "lat": 10.7769,
        "lng": 106.7009,
        "speed_kmh": 35.0,
        "timestamp": "2026-11-10T14:00:00Z"
    }
    response = client.post("/api/v1/gps/ingest", json=payload)
    assert response.status_code == 422

def test_get_trip_status_success():
    response = client.get("/api/v1/trips/TRIP_101/status")
    assert response.status_code == 200
    assert response.json()["trip_id"] == "TRIP_101"

def test_get_trip_status_not_found():
    response = client.get("/api/v1/trips/NON_EXISTENT_TRIP/status")
    assert response.status_code == 404