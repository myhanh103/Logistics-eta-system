import os
import json
from osm.routing.route_service import get_route_with_error_handling
from osm.routing.matrix_service import calculate_travel_time_matrix, export_matrix_to_files

def run_tests():
    print("=== BẮT ĐẦU KIỂM THỬ HỆ THỐNG OSRM ===")

    # Đảm bảo thư mục data tồn tại trước khi ghi file
    os.makedirs("data", exist_ok=True)

    # 1. Test kịch bản ma trận (1 Kho + 3 Điểm giao)
    test_locations = [
        {"id": "Kho_Ben_Thanh", "lon": 106.697935, "lat": 10.773233},
        {"id": "Diem_Giao_1", "lon": 106.705100, "lat": 10.781200},
        {"id": "Diem_Giao_2", "lon": 106.698500, "lat": 10.788000},
        {"id": "Diem_Giao_3", "lon": 106.708200, "lat": 10.789500}
    ]

    print("\n--- [Test 1] Đang tính ma trận thời gian và khoảng cách ---")
    matrix_res = calculate_travel_time_matrix(test_locations)
    if matrix_res["success"]:
        print("Tính ma trận thành công!")
        export_matrix_to_files(matrix_res["matrix"])
    else:
        print(f"Lỗi tính ma trận: {matrix_res['error']}")

    print("\n--- [Test 2] Kiểm thử xử lý lỗi (Truyền tọa độ không hợp lệ) ---")
    invalid_coords = [
        (106.697935, 10.773233),
        (999.999999, 999.999999) # Tọa độ sai lệch ngoại biên
    ]
    error_test_res = get_route_with_error_handling(invalid_coords)
    print(f"Kết quả bắt lỗi hệ thống: {error_test_res}")

print("\n--- [Test 3] Lấy và lưu GeoJSON hành trình qua nhiều điểm (Multi-stop) ---")
multi_coords = [
        (106.697935, 10.773233), # Kho Bến Thành
        (106.705100, 10.781200), # Điểm giao 1
        (106.698500, 10.788000), # Điểm giao 2
        (106.708200, 10.789500)  # Điểm giao 3
    ]
    
route_res = get_route_with_error_handling(multi_coords)
if route_res["success"]:
        # Đóng gói kết quả thành chuẩn GeoJSON multi-stop hoàn chỉnh
        geojson_output = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "description": "Hành trình giao hàng đa điểm qua OSRM",
                        "total_routes": route_res["total_routes"]
                    },
                    "geometry": route_res["geometry"] # Lấy phần geometry chuẩn GeoJSON từ service
                }
            ]
        }
        
        # Lưu ra file JSON riêng biệt trong thư mục data/
        geojson_path = "data/multi_stop_geometry.json"
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson_output, f, ensure_ascii=False, indent=4)
            
        print(f"-> Đã lưu file GeoJSON multi-stop thành công tại: {geojson_path}")
else:
        print(f"Lỗi lấy tuyến đường multi-stop: {route_res['error']}")
        
print("\n=== HOÀN TẤT KIỂM THỬ TOÀN BỘ HỆ THỐNG ===")

if __name__ == "__main__":
    run_tests()