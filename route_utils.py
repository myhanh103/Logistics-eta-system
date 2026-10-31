import json
import requests

def get_multiple_real_routes(filename="ben_thanh_to_landmark_multi_routes.json"):
    # Tọa độ gốc: Chợ Bến Thành và Landmark 81
    orig_lon, orig_lat = 106.697935, 10.773233  
    dest_lon, dest_lat = 106.721950, 10.794820  

    # Danh sách 5 tuyến đường thực tế qua các trục đường khác nhau (đã tinh chỉnh để không trùng thời gian)
    route_variants = [
        {
            "variant_name": "Đường Tôn Đức Thắng & Cầu Ba Son",
            "via_lon": 106.705100, 
            "via_lat": 10.781200
        },
        {
            "variant_name": "Đường Hai Bà Trưng",
            "via_lon": 106.698500, 
            "via_lat": 10.788000
        },
        {
            "variant_name": "Đường Điện Biên Phủ",
            "via_lon": 106.708200, 
            "via_lat": 10.789500
        },
        {
            "variant_name": "Đường Nguyễn Thị Minh Khai",
            "via_lon": 106.691200, 
            "via_lat": 10.780100
        },
        {
            "variant_name": "Đường Cách Mạng Tháng Tám & Điện Biên Phủ",
            "via_lon": 106.685200, 
            "via_lat": 10.779000
        }
    ]

    all_routes_collected = []

    print("=== BẮT ĐẦU TRUY VẤN 5 TUYẾN ĐƯỜNG THỰC TẾ ===")
    for variant in route_variants:
        print(f"\nĐang xử lý: {variant['variant_name']}...")
        
        url = f"http://router.project-osrm.org/route/v1/driving/{orig_lon},{orig_lat};{variant['via_lon']},{variant['via_lat']};{dest_lon},{dest_lat}"
        
        params = {
            "overview": "full",
            "alternatives": "true",
            "geometries": "geojson"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == "Ok":
                    routes = data.get("routes", [])
                    print(f"-> Số tuyến đường trả về: {len(routes)}")
                    
                    for idx, r in enumerate(routes):
                        distance_km = round(r.get("distance", 0) / 1000.0, 2)
                        duration_min = round(r.get("duration", 0) / 60.0, 1)
                        
                        print(f"  + Tuyến số {idx + 1}:")
                        print(f"    - Khoảng cách: {distance_km} km")
                        print(f"    - Thời gian dự kiến: {duration_min} phút")
                        print(f"    - Số lượng điểm tọa độ vẽ tuyến: {len(r.get('geometry', {}).get('coordinates', []))}")

                        all_routes_collected.append({
                            "route_id": f"ROUTE_{idx + 1}",
                            "variant_category": variant['variant_name'],
                            "distance_km": distance_km,
                            "duration_min": duration_min,
                            "geometry": r.get("geometry", {})
                        })
                else:
                    print("-> OSRM không tìm thấy tuyến đường hợp lệ.")
            else:
                print(f"-> Lỗi HTTP: {response.status_code}")
        except Exception as e:
            print(f"-> Lỗi kết nối: {e}")

    # Xuất file JSON có thụt lề chuẩn (indent=4)
    output_data = {
        "od_pair": "Chợ Bến Thành -> Landmark 81",
        "total_routes_found": len(all_routes_collected),
        "routes": all_routes_collected
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n=== ĐÃ HOÀN TẤT VÀ LƯU {len(all_routes_collected)} KẾT QUẢ VÀO FILE: {filename} ===")

if __name__ == "__main__":
    get_multiple_real_routes()