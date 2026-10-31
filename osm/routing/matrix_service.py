import csv
import json
import requests

def calculate_travel_time_matrix(locations):
    """
    locations: Danh sách các điểm gồm Kho và các điểm giao, ví dụ:
    [
        {"id": "Kho_1", "lon": 106.697935, "lat": 10.773233},
        {"id": "Diem_Giao_1", "lon": 106.705100, "lat": 10.781200}
    ]
    """
    if len(locations) < 2:
        return {"success": False, "error": "Cần ít nhất 2 điểm (1 kho và 1 điểm giao trở lên)."}

    coords_str = ";".join([f"{loc['lon']},{loc['lat']}" for loc in locations])
    url = f"http://router.project-osrm.org/table/v1/driving/{coords_str}"
    
    params = {
        "annotations": "duration,distance"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return {"success": False, "error": f"Lỗi API Table: {response.status_code}"}
            
        data = response.json()
        if data.get("code") != "Ok":
            return {"success": False, "error": f"Không tạo được ma trận. Mã lỗi: {data.get('code')}"}

        durations_matrix = data.get("durations", []) # Ma trận thời gian (giây), xét chiều A->B và B->A
        distances_matrix = data.get("distances", []) # Ma trận khoảng cách (mét)

        # Chuyển đổi đơn vị: giây -> phút, mét -> km
        durations_min_matrix = [[round(sec / 60.0, 2) if sec is not None else None for sec in row] for row in durations_matrix]
        distances_km_matrix = [[round(m / 1000.0, 2) if m is not None else None for m in row] for row in distances_matrix]

        matrix_result = {
            "locations": [loc["id"] for loc in locations],
            "durations_minutes": durations_min_matrix,
            "distances_km": distances_km_matrix
        }

        return {"success": True, "matrix": matrix_result}

    except Exception as e:
        return {"success": False, "error": str(e)}

def export_matrix_to_files(matrix_data, json_path="data/travel_time_matrix.json", csv_path="data/travel_time_matrix.csv"):
    """
    Xuất kết quả ma trận ra file JSON và CSV phục vụ báo cáo.
    """
    # 1. Lưu file JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(matrix_data, f, ensure_ascii=False, indent=4)

    # 2. Lưu file CSV 
    locations = matrix_data["locations"]
    durations = matrix_data["durations_minutes"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["From \\ To"] + locations)
        for i, loc_name in enumerate(locations):
            writer.writerow([loc_name] + durations[i])
            
    print(f"-> Đã xuất ma trận thành công ra: {json_path} và {csv_path}")