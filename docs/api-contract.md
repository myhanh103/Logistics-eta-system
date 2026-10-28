
# API Contract — Logistics ETA System

## 1. Thông tin chung

- Framework: FastAPI
- Base URL: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- Định dạng dữ liệu: JSON

## 2. Kiểm tra Backend

GET /health

Mục đích: Kiểm tra trạng thái hoạt động của Backend.

## 3. API dự báo ETA (Mock)

POST /api/v1/routes/predict

Request mẫu:

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

Response: Danh sách tuyến ứng viên, thời gian ETA,
mã tuyến được đề xuất và lý do lựa chọn.

Lưu ý: Endpoint này thuộc API mock của tuần 2.

## 4. API cập nhật ETA (Mock)

POST /api/v1/routes/update-eta

Request mẫu:

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

Response: ETA cập nhật và thời gian đến dự kiến.

Lưu ý: Chưa kết nối luồng GPS realtime.

## 5. API so sánh tuyến đường (Tích hợp)

POST /api/v1/routes/compare

Request mẫu:

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
  "departure_time": "2026-10-30T08:00:00"
}
```

Các trường chính trong Response:

- recommended_route_id: ID tuyến được đề xuất
- candidate_routes: Danh sách tuyến OSRM
- ranking: Thứ hạng các tuyến
- selection_reason: Lý do chọn tuyến
- prediction_source: Nguồn ước tính ETA

Mỗi tuyến có các trường chính:

- route_id
- distance_km
- osrm_duration_min
- geometry
- predicted_duration_min
- prediction_source

geometry sử dụng GeoJSON LineString với tọa độ
theo thứ tự [longitude, latitude].

## 6. Giới hạn của phiên bản tuần 2

- Đã tích hợp OSRM và thuật toán lựa chọn tuyến.
- ETA hiện sử dụng ước tính OSRM.
- Chưa tích hợp model Random Forest vào API.
- Chưa triển khai GPS realtime hoàn chỉnh.
