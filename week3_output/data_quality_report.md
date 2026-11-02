# Báo cáo chất lượng dữ liệu - Tuần 3

Nguồn: `trip_data.csv` (báo cáo tuần 2). Sinh tự động bởi `prepare_week3_data.py` (seed=42).

## 1. Tổng quan

| Tập dữ liệu | Số dòng | Loại | Nguồn |
|---|---|---|---|
| trips_history.csv | 741 | THẬT (quan sát tay từ bản đồ) | manual |
| ml_features.csv | 741 | THẬT | manual |
| road_segments.csv | 12 | Tọa độ xấp xỉ | manual_approx |
| traffic_observations.csv | 3705 (741 thật mức tuyến + 2964 mô phỏng mức đoạn) | Hỗn hợp, có cột is_simulated | manual / simulated |
| delivery_orders.csv | 80 đơn, 20 chuyến | MÔ PHỎNG | simulated |
| gps_simulated.csv | 3090 điểm | MÔ PHỎNG | simulated |

## 2. Dữ liệu thật (trips_history)

- Khoảng thời gian: 2026-10-19 -> 2026-10-31 (13 ngày), 247 mốc giờ x 3 tuyến = 741 lượt.
- Ngày cuối tuần: ['24/10', '25/10', '31/10'].
- Trùng lặp (ngày, giờ, tuyến): 0.
- Giá trị thiếu ở cột nhãn / feature chính: 0.

Thống kê theo tuyến:

| Tuyến | Số lượt | Km (min-max) | Thời gian phút (TB) | Vận tốc km/h (TB) |
|---|---|---|---|---|
| R1 | 247 | 5.1-6.5 | 15.5 | 21.5 |
| R2 | 247 | 5.3-6.7 | 16.8 | 23.2 |
| R3 | 247 | 4.9-7.6 | 22.5 | 16.0 |

## 3. Lỗi phát hiện & cách xử lý

| Mục | Mô tả | Xử lý |
|---|---|---|
| van_toc | 4 dong R2 ngay 29/10/2026 co van toc hong (vd: '126,024.5'; gio 18:00, 17:00, 16:00, 15:00) | tinh lai = quang duong / thoi gian du doan x 60 |

## 4. Lưu ý quan trọng khi huấn luyện

1. **Nhãn không phải đo thực**: `actual_travel_time` = cột "Khoảng thời gian dự đoán" của tuần 2 (ước tính từ bản đồ), nên mô hình học lại ước tính bản đồ chứ chưa phải thời gian GPS thực. Ghi nhận ở cột `label_type = map_estimate`.
2. **Thời gian dự đoán nằm ngoài khoảng bản đồ**: số lượt lệch theo tuyến = {'R1': 0, 'R2': 28, 'R3': 40}. Nên kiểm tra lại cách lấy số khi tuần 3 làm việc với Người 3.
3. **Thang tình trạng không đồng nhất**: Tuyến 2 dùng "Ùn tắc nghiêm trọng" còn Tuyến 1, 3 dùng "Kẹt xe nặng"; đã quy về `status_ord` 0-3. Không đưa `status` vào feature vì suy ra trực tiếp từ vận tốc (rò rỉ nhãn).
4. **Dữ liệu ngắn**: chỉ 13 ngày (≈ 2 tuần), mới có 3 ngày cuối tuần; nên chia train/test theo ngày, không xáo trộn ngẫu nhiên.
5. **Tọa độ đoạn đường là xấp xỉ** (`needs_verification = 1`). Cần đối chiếu bằng OSRM/Google Maps trước khi dùng trong báo cáo.
6. **OSRM**: Không gọi OSRM (chạy với --osrm để thử); cột osrm_time_min để trống.
7. **Dữ liệu mô phỏng** (đoạn đường, đơn hàng, GPS) luôn có `is_simulated = 1`; chỉ dùng để dựng/kiểm thử pipeline tuần 4, không dùng để báo cáo độ chính xác.
8. GPS mô phỏng nội suy đường thẳng x hệ số 1.3, chưa bám theo đường thật (chưa map-matching).

## 5. Kiểm tra tự động

- `validate_trips_csv.py` chạy trên `trips_history.csv` (xem kết quả ở cuối `prepare_week3_data.py`).
- Lưu ý: `validate_trips_csv.py` với file báo cáo gốc báo OK nhưng **không kiểm tra cột vận tốc**, nên không phát hiện 4 giá trị hỏng ở mục 3.
