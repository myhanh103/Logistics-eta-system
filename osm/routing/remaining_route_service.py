# osm/routing/remaining_route_service.py
import requests
from osm.routing.route_matcher import check_off_route

def get_remaining_route(current_gps, next_stop_gps, trip_id="T001", next_stop_id="O002", threshold_meters=50.0):
    """
    Tính toán quãng đường và thời gian OSRM còn lại từ vị trí hiện tại đến điểm giao tiếp theo.
    
    :param current_gps: Tuple (lat, lon) của xe hiện tại.
    :param next_stop_gps: Tuple (lat, lon) của điểm giao tiếp theo.
    :param trip_id: Mã chuyến.
    :param next_stop_id: Mã điểm giao tiếp theo.
    :param threshold_meters: Ngưỡng lệch tuyến.
    :return: Dictionary chuẩn định dạng JSON mẫu yêu cầu của tuần 4.
    """
    # URL OSRM public server
    url = f"http://router.project-osrm.org/route/v1/driving/{current_gps[1]},{current_gps[0]};{next_stop_gps[1]},{next_stop_gps[0]}?overview=full&geometries=geojson"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                distance_m = route["distance"] # mét
                duration_s = route["duration"] # giây
                
                remaining_distance_km = round(distance_m / 1000.0, 2)
                remaining_duration_min = round(duration_s / 60.0, 2)
                geometry = route.get("geometry", {})
                
                # Giả định kiểm tra lệch tuyến (so với điểm bắt đầu/hoặc kiểm tra nhanh)
                off_route_check = check_off_route(current_gps, [next_stop_gps], threshold_meters)
                
                return {
                    "success": True,
                    "data": {
                        "trip_id": trip_id,
                        "next_stop_id": next_stop_id,
                        "remaining_distance_km": remaining_distance_km,
                        "remaining_osrm_duration_min": remaining_duration_min,
                        "is_off_route": off_route_check["is_off_route"],
                        "route_source": "osrm",
                        "geometry": geometry
                    }
                }
            else:
                return {"success": False, "error": "OSRM khong tra ve tuyen duong hop le."}
        else:
            return {"success": False, "error": f"Loi ket noi OSRM status code: {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Loi exception khi goi OSRM API: {str(e)}"}