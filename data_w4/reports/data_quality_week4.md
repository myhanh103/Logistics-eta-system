# Báo cáo chất lượng dữ liệu - Tuần 4 

Sinh tự động bởi `prepare_week4_data.py` (seed=2026, tần suất GPS 5 giây). Chạy lại cho cùng kết quả.

## 1. Tình trạng theo yêu cầu

| Mã | Yêu cầu | Tình trạng |
|---|---|---|
| 4.2.1 | Dataset GPS mô phỏng dựa trên geometry OSRM, có thời gian, tọa độ, tốc độ, mã chuyến | **Một phần**: đủ cột và đủ 20 chuyến, nhưng geometry hiện là tổng hợp, chưa phải OSRM (xem mục 4) |
| 4.2.2 | Script phát GPS theo thời gian, cấu hình tốc độ phát và tần suất 5-10 giây | Đạt (`gps_simulator.py play`) |
| 4.2.3 | Kịch bản: bình thường, dừng lâu, kẹt xe, mất GPS, lệch tuyến, GPS sai | Đạt (6 kịch bản, có nhật ký bất thường) |
| 4.2.4 | Rà soát traffic tuần 3, tổng hợp đoạn đường theo giờ và mức độ ùn tắc | Đạt (`traffic_summary.csv` có `congestion_level`), kèm các vấn đề cần lưu ý (mục 7) |
| 4.2.5 | Chuẩn hóa đơn hàng: hạn giao, thời gian phục vụ, thời gian hoàn thành giả lập | Đạt (mục 8). Giờ hoàn thành lấy từ GPS mô phỏng nên cũng phụ thuộc geometry tổng hợp |
| 4.2.6 | Báo cáo phân biệt dữ liệu thật, OSRM, mô phỏng; kiểm tra chất lượng | Đạt (mục 3 và 9). Kết quả: **chưa có dữ liệu OSRM nào** |

## 2. Các file đầu ra

| File | Nội dung |
|---|---|
| data/simulated/gps_simulated.csv | 19645 điểm GPS, 20 chuyến, mỗi 5 giây (kịch bản bình thường) |
| data/simulated/gps_scenarios/S01..S06_*.csv | 6 kịch bản, mỗi kịch bản 5 chuyến |
| data/simulated/gps_scenarios/anomaly_log.csv | Nhật ký bất thường đã chèn (loại, thời điểm, tham số) để làm đáp án |
| data/simulated/gps_scenarios/scenario_index.csv | Danh mục kịch bản |
| data/simulated/stop_events.csv | Giờ đến/đi từng điểm giao, so với khung giờ giao |
| data/scripts/gps_simulator.py | Dựng dataset (`build`) và phát GPS (`play`) |
| data/scripts/traffic_summary.py | Rà soát và tổng hợp traffic |
| data/scripts/prepare_week4_data.py | Chạy toàn bộ pipeline + sinh báo cáo này |
| data/processed/traffic_summary.csv | Tổng hợp vận tốc theo tuyến/đoạn x loại ngày x giờ |
| data/reports/data_provenance.csv | Số dòng thật / OSRM / mô phỏng / ước lượng thủ công của từng file |
| data/processed/delivery_orders.csv | 80 đơn / 20 chuyến (từ tuần 3, đã chuẩn hóa, mục 8) |

## 3. Phân loại dữ liệu: thật, OSRM, mô phỏng 

Quy ước: **Thật** = đọc tay từ Google Maps (`is_simulated = 0`, `data_source = manual`). **OSRM** = giá trị lấy trực tiếp từ OSRM (`data_source = osrm_api`). **Mô phỏng** = sinh bằng code (`is_simulated = 1`, `data_source = simulated`). **Ước lượng thủ công** = nhập tay xấp xỉ, không đo và không mô phỏng.

| File | Số dòng | Thật | OSRM | Mô phỏng | Ước lượng thủ công | Ghi chú |
|---|---|---|---|---|---|---|
| processed/trips_history.csv | 741 | 741 | 0 | 0 | 0 | Thật: đọc tay từ Google Maps. Nhãn thời gian là ước tính của bản đồ. Cột osrm_time_min còn trống |
| processed/ml_features.csv | 741 | 741 | 0 | 0 | 0 | Cùng nguồn trips_history |
| processed/road_segments.csv | 12 | 0 | 0 | 0 | 12 | Tọa độ đặt tay xấp xỉ, chưa kiểm chứng; cột OSRM còn trống |
| processed/traffic_observations.csv | 3705 | 741 | 0 | 2964 | 0 | Thật ở mức tuyến (Google Maps); mô phỏng ở mức đoạn |
| processed/traffic_summary.csv | 855 | 171 | 0 | 684 | 0 | Tổng hợp từ traffic_observations |
| processed/delivery_orders.csv | 80 | 0 | 0 | 80 | 0 | Toàn bộ mô phỏng, kể cả hạn giao và giờ hoàn thành |
| simulated/gps_simulated.csv | 19645 | 0 | 0 | 19645 | 0 | Mô phỏng. Cột osrm = số dòng có geometry từ OSRM; hiện có 0 đoạn OSRM trong cache |
| simulated/gps_scenarios/*.csv | 30529 | 0 | 0 | 30529 | 0 | Mô phỏng, có đáp án trong anomaly_log.csv |

**Hiện chưa có dữ liệu nào từ OSRM** (tổng cột OSRM = 0). Dữ liệu thật chỉ gồm 741 lượt đi và 741 quan sát vận tốc mức tuyến, cùng nguồn Google Maps; mọi thứ liên quan đến đoạn đường, đơn hàng và GPS là mô phỏng hoặc ước lượng. Không dùng dữ liệu mô phỏng để báo cáo độ chính xác của mô hình.

## 4. Dataset GPS mô phỏng 

Cột chính: `delivery_trip_id` (mã chuyến), `timestamp`, `lat`, `lon`, `speed_kmh`, `heading_deg`, `next_stop_seq`, `phase` (drive/light/delivery/long_stop), `is_stopped`, cùng cột đáp án `true_lat`, `true_lon`, `route_offset_m`, `is_anomaly`, `anomaly_type`. Mọi dòng có `is_simulated = 1`, `data_source = simulated`.

- 19645 điểm, 20 chuyến, thời lượng trung vị mỗi chuyến 84.4 phút.
- Khoảng cách giữa hai điểm liên tiếp đúng 5 giây ở 100.0% cặp điểm; thời gian tăng dần: có.
- 100.0% điểm nằm trong khung TP.HCM; vận tốc từ 0.0 đến 26.0 km/h (TB khi di chuyển 20.1 km/h); vận tốc suy ra từ tọa độ lớn nhất 39.5 km/h.
- `gps_id` duy nhất: có.
- Vận tốc nền theo giờ lấy từ trung vị vận tốc **thật** theo tuyến của tuần 3; nhiễu GPS ~4 m.

> **Geometry hiện là tổng hợp, chưa phải OSRM.** Máy chủ OSRM công cộng không truy cập được từ môi trường tạo dữ liệu này, nên 80/80 đoạn đi được dựng bằng đường gấp khúc 3 đoạn giữa hai điểm (cột `geometry_source = synthetic`). Vị trí trên đường thật chưa đúng. Để đạt yêu cầu 4.2.1, chạy trên máy có internet: `python prepare_week4_data.py --osrm`. Lệnh này lưu geometry OSRM vào `data/simulated/osrm_cache/` rồi dựng lại toàn bộ dữ liệu; các lần chạy sau tự dùng cache.

## 5. Script phát GPS 

```bash
python gps_simulator.py play --trip DT01 --speed 10 --interval 5     # phát nhanh gấp 10 lần, lấy mẫu 5 giây
python gps_simulator.py play --speed 1                               # thời gian thực, mọi chuyến
python gps_simulator.py play --input ../simulated/gps_scenarios/S04_gps_loss.csv --speed 0   # nhanh nhất
python gps_simulator.py play --sink file:out.jsonl                   # ghi file; hoặc --sink http:URL để POST
python gps_simulator.py play --config play_config.json               # cấu hình trong file JSON
```
- `--speed`: 1 = thời gian thực, N = nhanh gấp N lần, 0 = không chờ. `--interval`: 5-10 giây (lấy mẫu lại từ file). `--max-gap-s` rút ngắn khoảng nghỉ giữa các chuyến. `--limit`, `--loop` giới hạn hoặc lặp lại.
- Đã kiểm tra thủ công: phát 30 bản ghi ở speed 20 mất ~8 giây (đúng 145 giây dữ liệu / 20); `--interval` ngoài 5-10 bị từ chối; nạp cấu hình từ JSON hoạt động.

## 6. Kịch bản di chuyển 

| Kịch bản | Mô tả | Số chuyến | Số dòng | Dòng gán nhãn bất thường |
|---|---|---|---|---|
| S01_normal | Di chuyển bình thường (không có bất thường) | 5 | 4407 | 0 |
| S02_long_stop | Dừng lâu: một điểm giao bị dừng thêm 15-30 phút | 5 | 6726 | 1298 |
| S03_traffic_jam | Kẹt xe mô phỏng: vận tốc giảm còn 20-40% trên đoạn dài 300-600 m | 5 | 5443 | 253 |
| S04_gps_loss | Mất GPS: 1-3 khoảng mất tín hiệu 1-8 phút (thiếu dòng) | 5 | 5502 | 0 |
| S05_route_deviation | Lệch tuyến: xe đi lệch 250-700 m rồi quay lại | 5 | 4799 | 354 |
| S06_bad_gps | GPS sai: nhảy vị trí, trôi, tọa độ null/0, đảo lat-lon, tốc độ đột biến, trùng dòng, sai thứ tự | 5 | 3652 | 494 |

Mỗi kịch bản có nhật ký đáp án trong `anomaly_log.csv`. Kết quả thử phát hiện bằng bộ lọc đơn giản:

| Kịch bản | Kết quả |
|---|---|
| S02 dừng lâu | Thời gian đứng yên liên tục dài nhất mỗi chuyến: bình thường 5.0-8.0 phút, kịch bản 13.7-34.0 phút. Ngưỡng 12 phút tách được 2 nhóm |
| S03 kẹt xe | Vận tốc TB trong đoạn kẹt 6.2 km/h so với 20.6 km/h khi chạy bình thường (253 dòng) |
| S04 mất GPS | Phát hiện 9/9 khoảng mất tín hiệu bằng ngưỡng khoảng cách thời gian > 2x tần suất; khoảng mất dài nhất 480 giây; thiếu 470 dòng |
| S05 lệch tuyến | Khoảng cách tới đường đã lập kế hoạch > 60 m: phát hiện 325/354 dòng lệch (tối đa 420 m), phần chưa phát hiện là các dòng lệch 30-60 m ở hai đầu đoạn lệch; 0 báo nhầm trong 4445 dòng bình thường (p99 11.6 m) |

S06 GPS sai (độ phủ của bộ phát hiện đơn giản):

| Loại | Số dòng gán nhãn | Phát hiện được |
|---|---|---|
| outlier_jump | 49 | 49 |
| speed_spike | 21 | 21 |
| null_coord | 15 | 15 |
| zero_coord | 10 | 10 |
| swapped_latlon | 9 | 9 |
| duplicate_row | 35 | 35 |
| out_of_order | 22 | 22 |
| drift | 333 | 0 |

Loại `drift` (trôi chậm 80-200 m) không bị bộ phát hiện đơn giản bắt được, cần lọc theo quỹ đạo (ví dụ Kalman/map-matching) ở bước sau.

## 7. Rà soát traffic tuần 3 và tổng hợp theo giờ 

`traffic_summary.csv`: 855 dòng (171 mức tuyến thật, 684 mức đoạn mô phỏng), chia theo `day_type` = all/weekday/weekend, 19 giờ có dữ liệu.

Quy mô đầu vào: 3705 quan sát (741 thật + 2964 mô phỏng), 2026-10-19 đến 2026-10-31 (13 ngày). Trùng `obs_id`: 0; thiếu vận tốc: 0; 4 dòng vận tốc đã được tính lại ở tuần 3.

**Các vấn đề phát hiện**

1. **Thiếu dữ liệu các giờ 1h, 2h, 3h, 4h, 5h.** Chỉ có 0h và 6h-23h (19 giờ). Mô hình và bảng tổng hợp không có thông tin ban đêm từ 1h đến 5h. Nên bổ sung hoặc chỉ dùng mô hình cho khoảng 6h-24h.
2. **Cuối tuần quá ít.** Chỉ 3 ngày cuối tuần (2026-10-24, 2026-10-25, 2026-10-31), mỗi ô giờ x tuyến có 3 quan sát (ngày thường 10). Toàn bộ 57 ô cuối tuần mức tuyến bị gắn `low_sample = 1`; không kết luận theo cuối tuần.
3. **Tình trạng giao thông không khớp vận tốc ở R2.** "Ùn tắc nghiêm trọng" có vận tốc trung vị 22.0 km/h, chỉ thấp hơn "Chậm nhẹ" (22.5 km/h) 2.2%. Nhãn tình trạng ở tuyến này gần như không phân biệt được với vận tốc; không nên dùng `status` làm nhãn.
4. **Vận tốc bị lượng tử hóa.** Vận tốc suy ra từ thời gian dự đoán làm tròn phút nên mỗi tuyến chỉ có 24-34 giá trị khác nhau trên 247 mốc (R1/R2/R3: R1=24, R2=28, R3=34). Độ phân giải thấp, phân vị p10/p90 trong bảng tổng hợp thường trùng nhau.
5. **Dữ liệu theo đoạn đường không độc lập.** 2964 quan sát đoạn là vận tốc tuyến nhân hệ số cố định và nhiễu, nên tương quan với vận tốc tuyến 0.862-0.941. Bảng tổng hợp mức đoạn (scope = segment) không chứa thông tin mới, dùng để dựng pipeline, không dùng để kết luận về từng đoạn.
6. **Tọa độ đoạn đường không khớp quãng đường tuyến.** R1: tổng đường chim bay các đoạn 3.9 km so với quãng đường tuyến 5.3 km (tỉ lệ 0.74); R2: tổng đường chim bay các đoạn 4.12 km so với quãng đường tuyến 6.6 km (tỉ lệ 0.62); R3: tổng đường chim bay các đoạn 2.34 km so với quãng đường tuyến 5.3 km (tỉ lệ 0.44). Tỉ lệ dưới 0,55 ở R3 cho thấy tọa độ đoạn của tuyến này sai hoặc quãng đường tuyến tính cả phần ngoài hai điểm đầu/cuối. Cần đối chiếu lại tọa độ (cột `needs_verification = 1`) trước khi dùng cho OSRM.

**Mức độ ùn tắc** (cột `congestion_level`, tính từ vận tốc): `congestion_index = 1 - vận tốc trung vị / vận tốc thông thoáng (p90)`; chia 4 mức: 0 thong_thoang (< 0,15), 1 cham_nhe (< 0,30), 2 ket_xe_nang (< 0,50), 3 un_tac_nghiem_trong (>= 0,50). Ngưỡng do người làm đặt, chưa hiệu chỉnh với dữ liệu thật khác.

Giờ bị xếp `ket_xe_nang` (ngày thường):

- R1: 17h, 18h, 19h
- R2: 17h, 18h, 19h, 20h, 21h, 23h
- R3: 15h, 16h, 17h

Lưu ý: ở R2 mức ùn tắc theo vận tốc mâu thuẫn với nhãn tình trạng gốc (vấn đề 3), nên mức độ của R2 kém tin cậy. Mức theo từng giờ ngày thường dựa trên 10 quan sát nên dao động.


Vận tốc thật theo tuyến (trung vị, km/h) theo khung giờ, ngày thường:

| Khung giờ | R1 | R2 | R3 |
|---|---|---|---|
| dem | 26.3 | 24.0 | 22.3 |
| sang_som | 26.5 | 26.4 | 19.9 |
| cao_diem_sang | 20.7 | 24.6 | 15.9 |
| trua | 22.0 | 24.1 | 15.9 |
| cao_diem_chieu | 18.0 | 20.7 | 13.4 |
| toi | 22.7 | 20.8 | 19.2 |

## 8. Chuẩn hóa dữ liệu đơn hàng (

`delivery_orders.csv` giữ nguyên các cột tuần 3 và thêm các cột sau:

| Cột | Ý nghĩa |
|---|---|
| `window_start` | Giờ bắt đầu khung giao, dạng YYYY-MM-DD HH:MM:SS |
| `delivery_deadline` | **Hạn giao** = giờ kết thúc khung giao (`time_window_end`) |
| `has_deadline` | 1 nếu có hạn giao; 0 thì `deadline_status = no_deadline` (hiện cả 80 đơn đều có hạn) |
| `service_time_s` | **Thời gian phục vụ** tại điểm giao, giây (= `service_time_min` x 60, từ 3 đến 8 phút) |
| `simulated_arrival_time` | Giờ xe đến điểm giao, lấy từ GPS mô phỏng kịch bản bình thường |
| `simulated_completion_time` | **Thời gian hoàn thành giả lập** = giờ đến + thời gian phục vụ |
| `slack_min` | Hạn giao trừ giờ hoàn thành, phút (âm nghĩa là trễ) |
| `deadline_status` | `on_time` (dư từ 10 phút), `at_risk` (dư dưới 10 phút), `late` (trễ), `no_deadline` |
| `completion_basis` | Nguồn của giờ hoàn thành, ví dụ `simulated_gps_synthetic_geometry` |

Kết quả trên 80 đơn: on_time = 61, at_risk = 8, late = 11, no_deadline = 0. `slack_min` trung vị 30.1 phút (nhỏ nhất -27.4, lớn nhất 71.7).

Giả định cần biết:
- Hạn giao lấy từ khung giờ giao đã sinh ngẫu nhiên ở tuần 3, không tính theo thời gian di chuyển thực. Tỉ lệ đúng hạn / trễ chỉ để thử logic, không phản ánh thực tế.
- Ngưỡng `at_risk` = 10 phút là giá trị tạm do người làm đặt; nên thống nhất lại với Người làm cảnh báo trễ (mục 4.4.2).
- Xe đến sớm hơn giờ bắt đầu khung thì vẫn giao ngay, không chờ. Giờ đến phụ thuộc geometry tổng hợp nên sẽ đổi khi chạy lại với `--osrm`.

## 9. Kiểm tra chất lượng dữ liệu 

Đạt 26/28 phép kiểm tra tự động.

| File | Phép kiểm tra | Kết quả | Chi tiết |
|---|---|---|---|
| trips_history.csv | trip_id duy nhất | Đạt |  |
| trips_history.csv | không thiếu giá trị ở cột số chính | Đạt | 0 ô thiếu |
| trips_history.csv | vận tốc trong 5-60 km/h | Đạt | 9.6-33.0 |
| trips_history.csv | vận tốc khớp quãng đường / thời gian (sai lệch <= 0,3 km/h) | Đạt | lớn nhất 0.05 |
| trips_history.csv | is_simulated = 0 và data_source = manual | Đạt |  |
| ml_features.csv | nhãn target_travel_time_min không thiếu | Đạt |  |
| ml_features.csv | không chứa cột tình trạng (tránh rò rỉ nhãn) | Đạt |  |
| road_segments.csv | 12 đoạn, tọa độ nằm trong khung TP.HCM | Đạt |  |
| road_segments.csv | tọa độ đã đối chiếu OSRM / Google Maps | **Không đạt** | còn 12/12 đoạn needs_verification = 1 |
| traffic_observations.csv | obs_id duy nhất, vận tốc không thiếu | Đạt |  |
| traffic_observations.csv | is_simulated khớp data_source (0 = manual, 1 = simulated) | Đạt |  |
| traffic_summary.csv | khóa (scope, route, segment, day_type, hour) duy nhất | Đạt |  |
| traffic_summary.csv | vận tốc trung vị trong 3-60 km/h; congestion_index trong [0, 1] | Đạt |  |
| traffic_summary.csv | có mức độ ùn tắc ở mọi dòng | Đạt |  |
| delivery_orders.csv | 80 đơn, mã đơn duy nhất, mỗi chuyến 3-5 điểm | Đạt |  |
| delivery_orders.csv | tọa độ điểm giao trong khung TP.HCM | Đạt |  |
| delivery_orders.csv | không thiếu hạn giao, giờ đến, giờ hoàn thành | Đạt |  |
| delivery_orders.csv | hạn giao sau giờ bắt đầu khung | Đạt |  |
| delivery_orders.csv | giờ hoàn thành - giờ đến = thời gian phục vụ | Đạt |  |
| delivery_orders.csv | giờ đến tăng dần theo thứ tự điểm giao | Đạt |  |
| delivery_orders.csv | is_simulated = 1 | Đạt |  |
| gps_simulated.csv | gps_id duy nhất, thời gian tăng dần | Đạt |  |
| gps_simulated.csv | khoảng cách giữa hai điểm đúng tần suất cấu hình | Đạt | 100.0% |
| gps_simulated.csv | mọi điểm trong khung TP.HCM, vận tốc suy ra <= 80 km/h | Đạt | vận tốc suy ra lớn nhất 39.5 km/h |
| gps_simulated.csv | geometry lấy từ OSRM | **Không đạt** | 0/19645 dòng dùng OSRM |
| gps_scenarios/ | gps_id duy nhất trong từng file | Đạt |  |
| gps_scenarios/ | is_simulated = 1 ở mọi dòng | Đạt |  |
| gps_scenarios/ | nhật ký bất thường có đủ 5 kịch bản S02-S06 | Đạt |  |

Các phép kiểm tra không đạt phản ánh hạn chế đã biết (tọa độ đoạn chưa kiểm chứng, geometry chưa phải OSRM), không phải lỗi pipeline.

## 10. Hạn chế và việc cần làm

1. Chạy `python prepare_week4_data.py --osrm` trên máy có internet để thay geometry tổng hợp bằng OSRM (yêu cầu 4.2.1), rồi chép lại `osrm_cache/` và các CSV mới.
2. Tọa độ đoạn đường vẫn là xấp xỉ; cần kiểm tra lại, đặc biệt các tuyến ở mục 7.
3. GPS mô phỏng không phản ánh hành vi tài xế thật (đèn đỏ, rẽ, đường một chiều). Chỉ dùng để thử pipeline, không dùng để báo cáo độ chính xác mô hình.
4. Nhiễu GPS và tỉ lệ bất thường (1,5% nhảy vị trí, v.v.) là giả định của người làm, chưa lấy từ thiết bị thật.
5. Dữ liệu vận tốc thật vẫn chỉ ở mức tuyến và từ một nguồn (Google Maps).
