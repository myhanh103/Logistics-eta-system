import json
import requests


def get_route_from_osrm(lon1, lat1, lon2, lat2, pair_name=""):
  """Hàm gọi OSRM API để lấy tuyến đường giữa 2 điểm (lon, lat)"""
  url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
  params = {"overview": "full", "alternatives": "true", "geometries": "geojson"}

  print(f"\n--- Đang xử lý: {pair_name} ---")
  print(f"Endpoint API: {url}")

  try:
    response = requests.get(url, params=params)
    if response.status_code == 200:
      data = response.json()
      if data.get("code") == "Ok":
        routes = data.get("routes", [])
        print(f" Số tuyến đường trả về: {len(routes)}")

        for i, route in enumerate(routes):
          distance_km = route["distance"] / 1000  # Đổi mét sang km
          duration_min = route["duration"] / 60  # Đổi giây sang phút
          print(f"  + Tuyến số {i+1}:")
          print(f"    - Khoảng cách: {distance_km:.2f} km")
          print(f"    - Thời gian dự kiến: {duration_min:.1f} phút")
          print(f"    - Số lượng điểm tọa độ vẽ tuyến: {len(route['geometry']['coordinates'])}")
        
        return data
      else:
        print(f" Lỗi từ OSRM API: {data.get('code')}")
    else:
      print(f" HTTP Error: {response.status_code}")
  except Exception as e:
    print(f" Lỗi kết nối: {e}")
  return None


# THỬ NGHIỆM VỚI 2 CẶP ĐIỂM TẠI TP.HCM
# Cặp 1: Chợ Bến Thành -> Landmark 81
# (Thứ tự: Kinh độ (Longitude), Vĩ độ (Latitude))
p1_start = (106.698235, 10.773613)  # Chợ Bến Thành
p1_end = (106.795355, 10.795355)    # Landmark 81

# Cặp 2: Sân bay Tân Sơn Nhất -> ĐH Bách Khoa TP.HCM
p2_start = (106.656113, 10.818864)  # Tân Sơn Nhất
p2_end = (106.659750, 10.773510)    # ĐH Bách Khoa

# Thực thi gọi API cho Cặp 1
result_pair_1 = get_route_from_osrm(
    p1_start[0], p1_start[1], 
    p1_end[0], p1_end[1], 
    pair_name="Cặp 1: Chợ Bến Thành -> Landmark 81"
)

# Thực thi gọi API cho Cặp 2
result_pair_2 = get_route_from_osrm(
    p2_start[0], p2_start[1], 
    p2_end[0], p2_end[1], 
    pair_name="Cặp 2: Sân bay Tân Sơn Nhất -> ĐH Bách Khoa"
)

# (Tùy chọn) Lưu kết quả ra file JSON 
if result_pair_1:
  with open("result_pair_1.json", "w", encoding="utf-8") as f:
    json.dump(result_pair_1, f, ensure_ascii=False, indent=4)
  print("\n Đã lưu kết quả cặp 1 vào file 'result_pair_1.json'")