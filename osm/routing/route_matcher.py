# osm/routing/route_matcher.py
import math

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Tính khoảng cách giữa 2 điểm GPS (tính bằng mét) sử dụng công thức Haversine.
    """
    R = 6371000  # Bán kính trái đất tính bằng mét
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def check_off_route(current_gps, planned_route_coords, threshold_meters=50.0):
    """
    Kiểm tra xem vị trí GPS hiện tại của xe có bị lệch (off-route) 
    so với tuyến đường dự kiến hay không.
    
    :param current_gps: Tuple (lat, lon) vị trí hiện tại của xe.
    :param planned_route_coords: List các tọa độ [(lat, lon), ...] của tuyến đường dự kiến.
    :param threshold_meters: Ngưỡng khoảng cách cho phép (mét). Mặc định 50 mét.
    :return: dict chứa trạng thái is_off_route và khoảng cách nhỏ nhất tới tuyến đường.
    """
    if not planned_route_coords:
        return {"is_off_route": True, "min_distance_m": None, "error": "Khong co du lieu tuyen duong du kiến."}

    min_dist = float('inf')
    for pt in planned_route_coords:
        dist = calculate_haversine_distance(current_gps[0], current_gps[1], pt[0], pt[1])
        if dist < min_dist:
            min_dist = dist

    is_off = min_dist > threshold_meters
    return {
        "is_off_route": is_off,
        "min_distance_m": round(min_dist, 2),
        "threshold_meters": threshold_meters
    }