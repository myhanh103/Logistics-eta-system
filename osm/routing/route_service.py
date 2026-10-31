import json
import requests

def get_route_with_error_handling(coordinates_list):
    """
    Nhận vào danh sách tọa độ dạng [(lon1, lat1), (lon2, lat2), ...]
    Xử lý toàn bộ các lỗi: timeout, tọa độ sai, không tìm thấy tuyến.
    """
    if not coordinates_list or len(coordinates_list) < 2:
        return {"success": False, "error": "Cần ít nhất 2 điểm tọa độ (điểm đi và điểm đến)."}

    # Format chuỗi tọa độ cho OSRM: lon1,lat1;lon2,lat2;...
    coords_str = ";".join([f"{lon},{lat}" for lon, lat in coordinates_list])
    url = f"http://router.project-osrm.org/route/v1/driving/{coords_str}"
    
    params = {
        "overview": "full",
        "alternatives": "true",
        "geometries": "geojson"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        
        # Kiểm tra mã trạng thái HTTP
        if response.status_code != 200:
            return {
                "success": False, 
                "error": f"Lỗi HTTP từ OSRM Server: Mã trạng thái {response.status_code}"
            }
            
        data = response.json()
        
        if data.get("code") != "Ok":
            return {
                "success": False, 
                "error": f"OSRM không thể tính toán lộ trình. Mã lỗi: {data.get('code')}"
            }
            
        routes = data.get("routes", [])
        if not routes:
            return {"success": False, "error": "Không tìm thấy tuyến đường hợp lệ giữa các điểm đã cho."}

        # Trả về thành công kèm dữ liệu tuyến đường và multi-stop geometry
        return {
            "success": True,
            "total_routes": len(routes),
            "routes": routes,
            "geometry": routes[0].get("geometry", {}) # Multi-stop geometry chính của tuyến tối ưu nhất
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Yêu cầu tới OSRM Server bị quá thời gian (Timeout)."}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Không thể kết nối đến OSRM Server. Kiểm tra lại mạng."}
    except Exception as e:
        return {"success": False, "error": f"Lỗi không xác định: {str(e)}"}