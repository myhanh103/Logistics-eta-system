
import requests

# Địa chỉ dịch vụ tìm đường OSRM
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


def get_route_from_osrm(lon1, lat1, lon2, lat2):
    """
    Lấy tuyến đường giữa 2 điểm.

    lon = kinh độ
    lat = vĩ độ

    Trả về danh sách tuyến đường đã chuẩn hóa.
    """

    # 1. Kiểm tra tọa độ đầu vào
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError("Kinh độ không hợp lệ")

    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("Vĩ độ không hợp lệ")

    # 2. Tạo URL gửi đến OSRM
    url = f"{OSRM_URL}/{lon1},{lat1};{lon2},{lat2}"

    params = {
        "overview": "full",
        "alternatives": "true",
        "geometries": "geojson"
    }

    # 3. Gọi API
    try:
        response = requests.get(
            url,
            params=params,
            timeout=15
        )
        response.raise_for_status()

        data = response.json()

    except requests.RequestException as error:
        raise RuntimeError(
            f"Không thể kết nối OSRM: {error}"
        ) from error

    # 4. Kiểm tra kết quả trả về
    if data.get("code") != "Ok":
        raise RuntimeError(
            f"OSRM không tìm được tuyến: {data.get('code')}"
        )

    # 5. Chuẩn hóa dữ liệu tuyến đường
    routes = []

    for index, route in enumerate(data.get("routes", [])):
        routes.append({
            "route_id": f"R{index + 1:02d}",
            "distance_km": round(route["distance"] / 1000, 2),
            "osrm_duration_min": round(route["duration"] / 60, 2),
            "geometry": route["geometry"]
        })

    return routes


# 6. Chạy thử với tuyến Chợ Bến Thành → Landmark 81
if __name__ == "__main__":

    try:
        result = get_route_from_osrm(
            106.697935, 10.773233,
            106.721950, 10.794820
        )

        print("Số tuyến tìm được:", len(result))

        for route in result:
            print("------------------------")
            print("Mã tuyến:", route["route_id"])
            print("Khoảng cách:", route["distance_km"], "km")
            print("Thời gian OSRM:", route["osrm_duration_min"], "phút")
            print(
                "Số điểm tọa độ:",
                len(route["geometry"]["coordinates"])
            )

    except (ValueError, RuntimeError) as error:
        print("LỖI:", error)
