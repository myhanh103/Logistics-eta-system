# API Contract — Logistics ETA System

## 1. Thông tin chung

- **Framework:** FastAPI (Python 3.12)
- **Base URL:** `http://127.0.0.1:8000`
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **Định dạng dữ liệu:** JSON (`application/json`)

---

## 2. Kiểm tra Backend

### `GET /health`
- **Mục đích:** Kiểm tra trạng thái hoạt động của Backend (Health Check).
- **Response 200 OK:**
```json
{
  "status": "healthy",
  "message": "Smart Logs ETA API Service is running"
}
```

## 3. Các API Định tuyến & Dự báo ETA (Routes & ETA)
- 3.1. *POST /api/v1/routes/predict* (Legacy - Tuần 2)
- **Mục đích:** Dự báo thời gian di chuyển (ETA) cho một tuyến đơn lẻ.

**Request Body mẫu:**
```json
{
  "origin": {
    "lat": 10.7769,
    "lng": 106.7009
  },
  "destination": {
    "lat": 10.8021,
    "lng": 106.6438
  },
  "departure_time": "2026-10-20T08:30:00Z"
}
```
- 3.2. *POST /api/v1/routes/update-eta* (Legacy - Tuần 2)
- **Mục đích:** Cập nhật lại ETA theo vị trí GPS gửi về.

**Request Body mẫu:**
```json
{
  "trip_id": "TRIP_101",
  "current_location": {
    "lat": 10.785,
    "lng": 106.691
  },
  "timestamp": "2026-10-20T08:42:00Z"
}
```
- 3.3. *POST /api/v1/routes/compare* (Đã tích hợp ML Random Forest - Tuần 3)
- **Mục đích:** So sánh các tuyến đường ứng viên, tích hợp mô hình Machine Learning Random Forest để dự báo ETA và đề xuất tuyến tối ưu.

**Request Body mẫu:**
```json
{
  "origin": {
    "lat": 10.773233,
    "lng": 106.697935
  },
  "destination": {
    "lat": 10.79482,
    "lng": 106.72195
  },
  "departure_time": "2026-10-30T08:00:00Z"
}
```

**Response 200 OK mẫu:**
```json
{
  "recommended_route_id": "ROUTE_A",
  "routes": [
    {
      "route_id": "ROUTE_A",
      "distance_km": 7.5,
      "predicted_eta_min": 18.2,
      "source": "ML_RANDOM_FOREST"
    },
    {
      "route_id": "ROUTE_B",
      "distance_km": 8.25,
      "predicted_eta_min": 21.5,
      "source": "ML_RANDOM_FOREST"
    }
  ],
  "selection_reason": "Chọn ROUTE_A vì thời gian di chuyển ngắn nhất (18.2 phút) từ nguồn ML_RANDOM_FOREST."
}
```
- 3.4. *POST /api/v1/routes/multistop* (Tối ưu giao hàng đa điểm - Tuần 3)
- **Mục đích:** Nhận 1 kho (depot) và nhiều điểm giao (delivery_points), gọi OSRM Table API để lập lịch trình giao hàng tối ưu chuỗi điểm dừng. Tự động kích hoạt Fallback Haversine nếu OSRM lỗi.

**Request Body mẫu:**
```json
{
  "depot": {
    "lat": 10.7691,
    "lng": 106.7064
  },
  "delivery_points": [
    {
      "order_id": "ORD_01",
      "lat": 10.7760,
      "lng": 106.7062,
      "service_s": 300
    },
    {
      "order_id": "ORD_02",
      "lat": 10.7843,
      "lng": 106.7064,
      "service_s": 300
    }
  ],
  "return_to_depot": true
}
```
**Response 200 OK mẫu:**
```json
{
  "total_distance_km": 4.25,
  "total_duration_min": 18.4,
  "optimized_sequence": ["ORD_01", "ORD_02"],
  "stops": [
    {
      "sequence": 1,
      "order_id": "ORD_01",
      "lat": 10.7760,
      "lng": 106.7062,
      "arrival_s": 210.0,
      "complete_s": 510.0,
      "late": false
    }
  ],
  "source": "OSRM_OPTIMIZED",
  "selection_reason": "Thứ tự đã tối ưu qua OSRM Table API."
}
```

## 4. API Dữ liệu Giao thông (Traffic Data)
- 4.1. *GET /api/v1/traffic/summary* (Tổng hợp dữ liệu giao thông - Tuần 3)
- **Mục đích:** Gom nhóm và thống kê dữ liệu vận tốc giao thông theo từng đoạn đường (segment_id) và khung giờ (time_slot) từ tập tin CSV của Người 2.

- **Query Parameters:**
- **route_id (optional):** Lọc theo mã tuyến (ví dụ: R1)
- **segment_id (optional):** Lọc theo đoạn đường (ví dụ: SEG01)
- **time_slot (optional):** Lọc theo khung giờ (ví dụ: cao_diem_chieu)

**Response 200 OK mẫu:**
```json
{
  "total_records": 72,
  "data": [
    {
      "segment_id": "SEG01",
      "route_id": "R1",
      "segment_name": "Tôn Đức Thắng - đoạn Công trường Mê Linh",
      "road_type": "arterial",
      "time_slot": "cao_diem_chieu",
      "avg_speed_kmh": 19.48,
      "min_speed_kmh": 14.1,
      "max_speed_kmh": 25.5,
      "observation_count": 65
    }
  ],
  "source": "TRAFFIC_OBSERVATIONS_CSV",
  "selection_reason": "Tổng hợp thành công dữ liệu giao thông cho 72 đoạn đường."
}
```
## 5. API GPS Realtime & Quản lý Chuyến đi (Tuần 4)
- 5.1. *POST /api/v1/gps/ingest*
- **Mục đích:** Tiếp nhận tín hiệu GPS telemetry theo thời gian thực từ thiết bị/script giả lập (Người 2), lưu vết vị trí/điểm hoàn thành (Người 4), tính toán lại ETA còn lại qua ML/OSRM (Người 3) và phát cảnh báo rủi ro trễ deadline.

**Request Body mẫu:**
```json
{
  "trip_id": "TRIP_101",
  "device_id": "TRUCK_01",
  "lat": 10.7769,
  "lng": 106.7009,
  "speed_kmh": 35.5,
  "timestamp": "2026-11-10T14:30:00Z"
}
```

**Response 200 OK mẫu:**
```json
{
  "status": "SUCCESS",
  "trip_id": "TRIP_101",
  "current_location": {
    "lat": 10.7769,
    "lng": 106.7009
  },
  "next_stop_id": "ORD_02",
  "completed_stops": ["ORD_01"],
  "remaining_distance_km": 4.85,
  "updated_eta_min": 14.5,
  "delay_risk": "on_time",
  "source": "ML_RANDOM_FOREST",
  "traffic_delay_warning": false,
  "message": "Cập nhật vị trí và tính lại ETA thành công."
}
```
- 5.2. *GET /api/v1/trips/{trip_id}/status*
- **Mục đích:** Cung cấp trạng thái mới nhất của chuyến đi phục vụ cơ chế Polling từ giao diện Frontend.

- Path Parameter: trip_id (ví dụ: TRIP_101)

**Response 200 OK mẫu:**
```json
{
  "trip_id": "TRIP_101",
  "vehicle_id": "TRUCK_01",
  "status": "IN_TRANSIT",
  "last_known_location": {
    "lat": 10.7769,
    "lng": 106.7009
  },
  "last_timestamp": "2026-11-10T14:30:00Z",
  "completed_stops": ["ORD_01"],
  "remaining_stops": ["ORD_02", "ORD_03"],
  "current_next_stop": "ORD_02",
  "remaining_distance_km": 4.85,
  "updated_eta_min": 14.5,
  "delay_risk": "on_time"
}
```
## 6. Quy chuẩn Xử lý Lỗi (Error Handling & HTTP Status Codes)
- **400 Bad Request:** Dữ liệu gửi lên không đúng logic (ví dụ: trip_id bị rỗng, danh sách delivery_points bị trống).
- **404 Not Found:** Không tìm thấy chuyến đi (trip_id) hoặc tập tin dữ liệu cấu hình.
- **422 Unprocessable Entity:** Sai kiểu dữ liệu, sai định dạng tọa độ (vĩ độ ngoài khoảng [-90, 90], kinh độ ngoài khoảng [-180, 180]) hoặc tín hiệu GPS bị trùng/cũ timestamp hơn tín hiệu trước đó.
- **500 Internal Server Error:** Lỗi hệ thống phát sinh chưa lường trước (kích hoạt chế độ Fallback tự động).