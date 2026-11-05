# test_remaining_system.py
import json
from osm.routing.remaining_route_service import get_remaining_route

def run_test():
    print("=== BAT DAU KIEM THU MODULE TUAN 4 (REMAINING ROUTE) ===")
    
    # Tọa độ giả định: Vị trí hiện tại của xe và điểm giao tiếp theo ở HCMC
    current_gps = (10.7769, 106.7009)  # Khu vực Quận 1
    next_stop_gps = (10.7829, 106.6982)
    
    result = get_remaining_route(
        current_gps=current_gps,
        next_stop_gps=next_stop_gps,
        trip_id="T001",
        next_stop_id="O002"
    )
    
    if result["success"]:
        payload = result["data"]
        print("\nKet qua tra ve chuan format JSON:")
        print(json.dumps(payload, ensure_ascii=False, indent=4))
        
        # Lưu file JSON mẫu theo yêu cầu bàn giao
        output_path = "data/remaining_route_sample.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=4)
        print(f"\n-> Da luu file JSON mau tai: {output_path}")
    else:
        print(f"Loi: {result['error']}")

if __name__ == "__main__":
    run_test()