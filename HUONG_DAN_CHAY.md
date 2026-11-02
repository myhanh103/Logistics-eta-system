# Hướng dẫn chạy - Dữ liệu Tuần 3 

## 1. Chuẩn bị
- cài thư viện: `pip install pandas numpy` (thêm `requests` nếu muốn thử OSRM).
- Đặt cùng một thư mục: `prepare_week3_data.py`, `validate_trips_csv.py`, `trip_data.csv` (CSV tuần 2).

## 2. Chạy lại toàn bộ pipeline
```bash
python prepare_week3_data.py
```
Kết quả nằm trong thư mục `week3_output/`. Chạy lại luôn cho cùng kết quả (seed = 42, không cần mạng).

Tùy chọn:
```bash
python prepare_week3_data.py --input duong_dan/trip_data.csv --out thu_muc_ra/
python prepare_week3_data.py --verify    # so khớp SHA-256 trong dataset_manifest.json
python prepare_week3_data.py --osrm      # thử gọi OSRM public để điền osrm_time_min (cần internet)
```

## 3. Các file đầu ra
| File | Nội dung | Loại |
|---|---|---|
| trips_history.csv | 741 lượt (13 ngày x 19 mốc giờ x 3 tuyến), đúng schema `validate_trips_csv.py` | Thật |
| ml_features.csv | Feature thống nhất + nhãn `target_travel_time_min` để huấn luyện | Thật |
| data_dictionary.csv | Mô tả từng cột của từng file | - |
| data_quality_report.md | Báo cáo chất lượng, lỗi đã sửa, lưu ý khi huấn luyện | - |
| road_segments.csv | 12 đoạn đường (SEG01-SEG12), tọa độ đầu/cuối | Xấp xỉ |
| traffic_observations.csv | Vận tốc theo giờ: mức tuyến (thật) + mức đoạn (mô phỏng) | Hỗn hợp |
| delivery_orders.csv | 80 đơn, 20 chuyến, mỗi chuyến 3-5 điểm giao | Mô phỏng |
| gps_simulated.csv | GPS mô phỏng mỗi 30 giây cho 20 chuyến (dùng tuần 4) | Mô phỏng |
| dataset_manifest.json | Checksum khóa CSV tuần 2 và các file đầu ra | - |

## 4. Quy ước thật / mô phỏng
- Mọi file có cột `is_simulated` (0 = thật, 1 = mô phỏng) và `data_source`
  (`manual`, `simulated`, `osrm_api`, `openstreetmap`).
- Khi đánh giá mô hình chỉ dùng dòng `is_simulated = 0`.

## 5. Feature thống nhất với Người 3
`hour`, `day_of_week`, `is_weekend`, `is_peak`, `time_slot_code`, `distance_km`,
`map_time_mid_min` (thời gian bản đồ), `osrm_time_min` (để trống nếu chưa gọi OSRM),
`temp_c`, `humidity_pct`, `rain_mm_h`, `route_code`. Nhãn: `target_travel_time_min`.
Khung giờ: đêm 0-5h, sáng sớm 6h, cao điểm sáng 7-9h, trưa 10-14h, cao điểm chiều 15-19h, tối 20-23h.

## 6. Việc cần làm tay
1. Đối chiếu tọa độ `road_segments.csv` (cột `needs_verification = 1`) bằng OSRM hoặc Google Maps.
2. Thu thập thêm vận tốc theo khung giờ từ nguồn thật (mục 3.2.4); khi có, thêm dòng vào `traffic_observations.csv`
   với `is_simulated = 0`.

