import json
import requests

def get_route_from_osrm(lon1, lat1, lon2, lat2, filename="result_route.json"):
    """
    Nhiệm vụ 9: Hàm gọi OSRM API lấy tuyến đường giữa 2 điểm (Longitude, Latitude).
    - Hỗ trợ alternatives=true để lấy nhiều tuyến thay thế.
    - Trả về dữ liệu JSON gốc, trích xuất geometry và lưu file JSON.
    """
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"

    # Cấu hình tham số để yêu cầu OSRM tìm kiếm các tuyến đường thay thế (alternatives)
    params = {
        "overview": "full",
        "alternatives": "true",  # Bật tính năng tìm tuyến đường thay thế
        "geometries": "geojson"
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == "Ok":
                routes = data.get("routes", [])
                print(f"Số lượng tuyến đường trả về: {len(routes)}")

                # Duyệt qua tất cả các tuyến đường trả về (có thể có nhiều hơn 2 tuyến tùy đoạn đường)
                for i, route in enumerate(routes):
                    print(f"  + Tuyến số {i+1}:")
                    print(f"    - Khoảng cách: {route.get('distance', 0) / 1000:.2f} km")
                    print(f"    - Thời gian dự kiến: {route.get('duration', 0) / 60:.1f} phút")

                    geometry = route.get("geometry", {})
                    coordinates = geometry.get("coordinates", [])
                    print(f"    - Số điểm geometry coordinates: {len(coordinates)} điểm")

                # Lưu dữ liệu response JSON ra file theo yêu cầu
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"Đã lưu thành công file JSON: {filename}\n")

                return data
            else:
                print("API trả về mã lỗi không thành công.")
        else:
            print(f"Lỗi kết nối HTTP: {response.status_code}")
    except Exception as e:
        print(f"Lỗi hệ thống: {e}")

    return None

if __name__ == "__main__":
    # Chạy thử với cặp tọa độ kiểm thử và lưu ra file JSON
    get_route_from_osrm(106.697935, 10.773233, 106.721950, 10.794820, filename="result_pair_2.json")