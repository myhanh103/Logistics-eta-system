from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
HERE = Path(__file__).resolve().parent

ROUTES = {
    "R1": {"name": "Tôn Đức Thắng - Nguyễn Hữu Cảnh", "cols": dict(gio=1, dist=3, map=4, est=5, spd=6, stt=7)},
    "R2": {"name": "Hai Bà Trưng -> Điện Biên Phủ", "cols": dict(gio=8, dist=10, map=11, est=12, spd=13, stt=14)},
    "R3": {"name": "Hầm Thủ Thiêm", "cols": dict(gio=15, dist=17, map=18, est=19, spd=20, stt=21)},
}
WEATHER_COLS = dict(desc=22, temp=23, hum=24, rain=25)

STATUS_ORD = {"Thông thoáng": 0, "Chậm nhẹ": 1, "Kẹt xe nặng": 2, "Ùn tắc nghiêm trọng": 3}
WEATHER_CODE = {
    "Trời quang": "clear", "Nắng": "sunny", "Nắng, ít mây": "sunny",
    "Ít mây": "partly_cloudy", "Nhiều mây": "cloudy",
    "Mưa nhỏ": "light_rain", "Mưa vừa": "moderate_rain",
    "Mưa to, có dông": "heavy_rain_thunder",
}
SLOT_CODE = {"dem": 0, "sang_som": 1, "cao_diem_sang": 2, "trua": 3,
             "cao_diem_chieu": 4, "toi": 5}


def time_slot(hour: int) -> str:
    if hour < 6:
        return "dem"
    if hour < 7:
        return "sang_som"
    if hour < 10:
        return "cao_diem_sang"
    if hour < 15:
        return "trua"
    if hour < 20:
        return "cao_diem_chieu"
    return "toi"


# 12 đoạn đường khảo sát
SEGMENTS = [
    # id, route, seq, ten doan, (lat,lon) dau, (lat,lon) cuoi, loai duong, ty le chieu dai, he so van toc mo phong
    ("SEG01", "R1", 1, "Tôn Đức Thắng - đoạn Công trường Mê Linh", (10.7691, 106.7064), (10.7760, 106.7062), "arterial", 0.22, 1.05),
    ("SEG02", "R1", 2, "Tôn Đức Thắng - đoạn trước Ba Son", (10.7760, 106.7062), (10.7843, 106.7064), "arterial", 0.26, 0.92),
    ("SEG03", "R1", 3, "Tôn Đức Thắng - Nguyễn Hữu Cảnh (cầu Ba Son)", (10.7843, 106.7064), (10.7905, 106.7140), "arterial", 0.26, 0.90),
    ("SEG04", "R1", 4, "Nguyễn Hữu Cảnh - đoạn về cầu Sài Gòn", (10.7905, 106.7140), (10.7975, 106.7215), "arterial", 0.26, 1.10),
    ("SEG05", "R2", 1, "Hai Bà Trưng - đoạn Lê Lợi", (10.7730, 106.7000), (10.7790, 106.6980), "arterial", 0.22, 0.95),
    ("SEG06", "R2", 2, "Hai Bà Trưng - đoạn giữa", (10.7790, 106.6980), (10.7860, 106.6930), "arterial", 0.26, 0.85),
    ("SEG07", "R2", 3, "Hai Bà Trưng - nút Điện Biên Phủ", (10.7860, 106.6930), (10.7915, 106.7010), "arterial", 0.26, 0.90),
    ("SEG08", "R2", 4, "Điện Biên Phủ - đoạn về cầu Điện Biên Phủ", (10.7915, 106.7010), (10.7985, 106.7117), "arterial", 0.26, 1.20),
    ("SEG09", "R3", 1, "Đầu hầm Thủ Thiêm phía Quận 1", (10.7712, 106.7070), (10.7740, 106.7110), "tunnel_approach", 0.22, 0.85),
    ("SEG10", "R3", 2, "Hầm Thủ Thiêm (đoạn dưới sông)", (10.7740, 106.7110), (10.7765, 106.7150), "tunnel", 0.26, 1.15),
    ("SEG11", "R3", 3, "Cửa hầm phía Thủ Thiêm", (10.7765, 106.7150), (10.7800, 106.7185), "tunnel_approach", 0.26, 0.90),
    ("SEG12", "R3", 4, "Đại lộ Mai Chí Thọ - đoạn sau hầm", (10.7800, 106.7185), (10.7850, 106.7230), "arterial", 0.26, 1.00),
]

# Điểm giao hàng mô phỏng
DELIVERY_ZONES = [
    ("Quận 1", 10.7769, 106.7009, 1.2),
    ("Quận 3", 10.7840, 106.6800, 1.2),
    ("Phú Nhuận", 10.7990, 106.6800, 1.0),
    ("Bình Thạnh", 10.8050, 106.7100, 1.3),
    ("Thành phố Thủ Đức (Thảo Điền)", 10.8030, 106.7350, 1.2),
    ("Thành phố Thủ Đức (Thủ Thiêm)", 10.7880, 106.7250, 1.0),
]
DEPOT = ("DEPOT01", "Kho trung tâm (mô phỏng, Quận 1)", 10.7740, 106.7040)

# Hàm tính khoảng cách và hướng giữa hai tọa độ
def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")



def read_report(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, header=None, skiprows=2, dtype=str, encoding="utf-8-sig")
    if raw.shape[1] < 26:
        raise SystemExit(f"[LOI] {path.name} chi co {raw.shape[1]} cot, can >= 26")
    hdr = pd.read_csv(path, header=None, skiprows=1, nrows=1, dtype=str, encoding="utf-8-sig").iloc[0]
    if str(hdr[0]).strip() != "Ngày" or str(hdr[1]).strip() != "Giờ đi":
        raise SystemExit("[LOI] Khong dung dinh dang bao cao tuan 2 (hang 2 phai bat dau 'Ngày','Giờ đi')")
    return raw.reset_index(drop=True)


def build_trips(raw: pd.DataFrame, issues: list[dict]) -> pd.DataFrame:
    date = pd.to_datetime(raw[0].str.strip(), format="%d/%m/%Y", errors="coerce")
    if date.isna().any():
        raise SystemExit(f"[LOI] {int(date.isna().sum())} dong co ngay sai dinh dang")

    w_desc = raw[WEATHER_COLS["desc"]].str.strip()
    w_temp = num(raw[WEATHER_COLS["temp"]])
    w_hum = num(raw[WEATHER_COLS["hum"]])
    w_rain = num(raw[WEATHER_COLS["rain"]])
    unknown_w = sorted(set(w_desc.dropna()) - set(WEATHER_CODE))
    if unknown_w:
        issues.append(dict(muc="thoi_tiet", mo_ta=f"Mo ta thoi tiet chua co trong bang ma: {unknown_w}", xu_ly="gan 'unknown'"))

    frames = []
    for rid, cfg in ROUTES.items():
        c = cfg["cols"]
        t = pd.DataFrame({
            "date": date,
            "dep_str": raw[c["gio"]].str.strip(),
            "route_id": rid,
            "route_name": cfg["name"],
            "distance_km": num(raw[c["dist"]]),
            "map_time_raw": raw[c["map"]].str.strip(),
            "est_time_min": num(raw[c["est"]]),
            "avg_speed_raw": raw[c["spd"]],
            "avg_speed_num": num(raw[c["spd"]]),
            "status": raw[c["stt"]].str.strip(),
            "weather_desc": w_desc,
            "temp_c": w_temp,
            "humidity_pct": w_hum,
            "rain_mm_h": w_rain,
            "src_row": raw.index + 3,  
        })
        frames.append(t)
    df = pd.concat(frames, ignore_index=True)

    hm = df["dep_str"].str.extract(r"^(\d{1,2}):(\d{2})$").astype(float)
    if hm.isna().any().any():
        raise SystemExit("[LOI] co gio xuat phat sai dinh dang")
    df["hour"] = hm[0].astype(int)
    df["minute"] = hm[1].astype(int)
    df["departure_time"] = df["hour"].map("{:02d}".format) + ":" + df["minute"].map("{:02d}".format)
    df["departure_time_full"] = (
        df["date"] + pd.to_timedelta(df["hour"], unit="h") + pd.to_timedelta(df["minute"], unit="m")
    )

    rng = df["map_time_raw"].str.extract(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)").astype(float)
    df["map_time_low_min"], df["map_time_high_min"] = rng[0], rng[1]
    df["map_time_mid_min"] = (rng[0] + rng[1]) / 2
    df["map_time_min"] = df["map_time_low_min"].astype("Int64").astype(str) + " - " + df["map_time_high_min"].astype("Int64").astype(str)
    if rng.isna().any().any():
        issues.append(dict(muc="map_time", mo_ta=f"{int(rng[0].isna().sum())} dong khong tach duoc khoang thoi gian map", xu_ly="de trong"))

    calc_speed = (df["distance_km"] / df["est_time_min"] * 60).round(1)
    bad = df["avg_speed_num"].isna() | ((df["avg_speed_num"] - calc_speed).abs() > 0.3)
    df["speed_recomputed"] = bad.astype(int)
    for (d, rid), g in df[bad].groupby([df[bad]["date"].dt.strftime("%d/%m/%Y"), "route_id"]):
        sample = g["avg_speed_raw"].iloc[0]
        issues.append(dict(
            muc="van_toc",
            mo_ta=f"{len(g)} dong {rid} ngay {d} co van toc hong (vd: '{sample}'; gio {', '.join(g['dep_str'])})",
            xu_ly="tinh lai = quang duong / thoi gian du doan x 60",
        ))
    df["avg_speed_kmh"] = np.where(bad, calc_speed, df["avg_speed_num"]).round(1)

    df["actual_travel_time"] = df["est_time_min"]

    unknown_s = sorted(set(df["status"].dropna()) - set(STATUS_ORD))
    if unknown_s:
        issues.append(dict(muc="tinh_trang", mo_ta=f"Tinh trang la: {unknown_s}", xu_ly="status_ord de trong"))
    df["status_ord"] = df["status"].map(STATUS_ORD)

    df["day_of_week"] = df["date"].dt.dayofweek  
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["time_slot"] = df["hour"].map(time_slot)
    df["time_slot_code"] = df["time_slot"].map(SLOT_CODE)
    df["is_peak"] = df["time_slot"].isin(["cao_diem_sang", "cao_diem_chieu"]).astype(int)
    df["weather_code"] = df["weather_desc"].map(WEATHER_CODE).fillna("unknown")
    df["is_raining"] = (df["rain_mm_h"] > 0).astype(int)

    seg = pd.DataFrame(SEGMENTS, columns=["segment_id", "route_id", "seq", "name", "s", "e", "rt", "share", "f"])
    ends = {}
    for rid, g in seg.groupby("route_id"):
        g = g.sort_values("seq")
        ends[rid] = (g.iloc[0]["s"], g.iloc[-1]["e"])
    df["origin_lat"] = df["route_id"].map(lambda r: ends[r][0][0])
    df["origin_lon"] = df["route_id"].map(lambda r: ends[r][0][1])
    df["dest_lat"] = df["route_id"].map(lambda r: ends[r][1][0])
    df["dest_lon"] = df["route_id"].map(lambda r: ends[r][1][1])

    df["is_simulated"] = 0
    df["data_source"] = "manual"          
    df["label_type"] = "map_estimate"    
    df["osrm_time_min"] = np.nan          

    df = df.sort_values(["date", "hour", "route_id"]).reset_index(drop=True)
    df["trip_id"] = (
        df["route_id"] + "_" + df["departure_time_full"].dt.strftime("%Y%m%d_%H%M")
    )
    return df


TRIP_COLS = [
    "trip_id", "route_id", "route_name", "date", "departure_time", "departure_time_full",
    "hour", "day_of_week", "is_weekend", "time_slot", "is_peak",
    "distance_km", "map_time_min", "map_time_low_min", "map_time_high_min", "map_time_mid_min",
    "est_time_min", "actual_travel_time", "avg_speed_kmh", "speed_recomputed",
    "status", "status_ord",
    "weather_desc", "weather_code", "temp_c", "humidity_pct", "rain_mm_h", "is_raining",
    "origin_lat", "origin_lon", "dest_lat", "dest_lon", "osrm_time_min",
    "is_simulated", "data_source", "label_type", "src_row",
]


def build_segments(trips: pd.DataFrame) -> pd.DataFrame:
    med = trips.groupby("route_id")["distance_km"].median()
    rows = []
    for sid, rid, seq, name, s, e, rt, share, _f in SEGMENTS:
        rows.append(dict(
            segment_id=sid, route_id=rid, seq=seq, segment_name=name,
            start_lat=s[0], start_lon=s[1], end_lat=e[0], end_lon=e[1],
            road_type=rt,
            straight_km=round(haversine_km(*s, *e), 3),
            length_km_est=round(med[rid] * share, 2),
            osrm_distance_km=np.nan, osrm_time_min=np.nan,
            coord_source="manual_approx", needs_verification=1,
        ))
    return pd.DataFrame(rows)


def build_observations(trips: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    real = pd.DataFrame({
        "obs_id": ["OBS_R_" + t for t in trips["trip_id"]],
        "observation_level": "route",
        "route_id": trips["route_id"],
        "segment_id": "",
        "obs_time": trips["departure_time_full"],
        "hour": trips["hour"],
        "day_of_week": trips["day_of_week"],
        "time_slot": trips["time_slot"],
        "speed_kmh": trips["avg_speed_kmh"],
        "status": trips["status"],
        "is_simulated": 0,
        "data_source": "manual",
        "note": np.where(trips["speed_recomputed"] == 1, "speed recomputed from distance/time", ""),
    })

    f = {s[0]: s[8] for s in SEGMENTS}
    seg_route = {s[0]: s[1] for s in SEGMENTS}
    base = trips.set_index(["route_id", "departure_time_full"])
    sim_rows = []
    for sid in f:
        rid = seg_route[sid]
        t = trips[trips["route_id"] == rid]
        noise = rng.lognormal(mean=0.0, sigma=0.08, size=len(t))
        sp = np.clip(t["avg_speed_kmh"].to_numpy() * f[sid] * noise, 4.0, 60.0).round(1)
        sim_rows.append(pd.DataFrame({
            "obs_id": [f"OBS_S_{sid}_{x}" for x in t["departure_time_full"].dt.strftime("%Y%m%d_%H%M")],
            "observation_level": "segment",
            "route_id": rid,
            "segment_id": sid,
            "obs_time": t["departure_time_full"].to_numpy(),
            "hour": t["hour"].to_numpy(),
            "day_of_week": t["day_of_week"].to_numpy(),
            "time_slot": t["time_slot"].to_numpy(),
            "speed_kmh": sp,
            "status": t["status"].to_numpy(),
            "is_simulated": 1,
            "data_source": "simulated",
            "note": "derived from route-level real speed x segment factor x noise",
        }))
    out = pd.concat([real] + sim_rows, ignore_index=True)
    return out.sort_values(["obs_time", "observation_level", "route_id", "segment_id"]).reset_index(drop=True)


#Mô phỏng
def build_orders(rng: np.random.Generator, n_orders: int = 80) -> pd.DataFrame:
    sizes = []
    while sum(sizes) < n_orders:
        sizes.append(int(rng.integers(3, 6)))
    over = sum(sizes) - n_orders
    sizes[-1] -= over
    if sizes[-1] < 3:  
        extra = sizes.pop()
        i = 0
        while extra > 0:
            if sizes[i % len(sizes)] < 5:
                sizes[i % len(sizes)] += 1
                extra -= 1
            i += 1

    days = pd.date_range("2026-11-02", periods=5, freq="D")  # Thu Hai - Thu Sau
    rows, oid = [], 1
    for k, size in enumerate(sizes, start=1):
        trip_id = f"DT{k:02d}"
        day = days[(k - 1) % len(days)]
        dep_hour = int(rng.choice([7, 8, 9, 10, 13, 14, 15, 16]))
        depart = day + pd.Timedelta(hours=dep_hour)
        zone_ids = rng.choice(len(DELIVERY_ZONES), size=size, replace=True)
        eta_offset = 0
        for seq, zi in enumerate(zone_ids, start=1):
            zname, zlat, zlon, rad = DELIVERY_ZONES[zi]
            ang = rng.uniform(0, 2 * math.pi)
            r = rad * math.sqrt(rng.uniform(0, 1))
            lat = zlat + (r * math.sin(ang)) / 110.574
            lon = zlon + (r * math.cos(ang)) / (111.320 * math.cos(math.radians(zlat)))
            eta_offset += int(rng.integers(12, 25))
            win_start = depart + pd.Timedelta(minutes=eta_offset - 10)
            win_end = win_start + pd.Timedelta(minutes=int(rng.choice([30, 45, 60])))
            rows.append(dict(
                order_id=f"ORD{oid:03d}", delivery_trip_id=trip_id, stop_seq=seq,
                order_date=day.strftime("%Y-%m-%d"),
                planned_departure=depart,
                depot_id=DEPOT[0], depot_lat=DEPOT[2], depot_lon=DEPOT[3],
                dest_zone=zname, dest_lat=round(lat, 6), dest_lon=round(lon, 6),
                address_label=f"Điểm giao mô phỏng {oid:03d} - {zname}",
                weight_kg=round(float(rng.uniform(0.5, 15.0)), 1),
                service_time_min=int(rng.integers(3, 9)),
                time_window_start=win_start.strftime("%H:%M"),
                time_window_end=win_end.strftime("%H:%M"),
                is_simulated=1, data_source="simulated",
            ))
            oid += 1
    return pd.DataFrame(rows)


def build_gps(orders: pd.DataFrame, trips: pd.DataFrame, rng: np.random.Generator,
              step_s: int = 30, detour: float = 1.3) -> pd.DataFrame:
    speed_by_hour = trips.groupby("hour")["avg_speed_kmh"].median()
    overall = float(trips["avg_speed_kmh"].median())
    rows, gid = [], 1
    for trip_id, g in orders.groupby("delivery_trip_id", sort=True):
        g = g.sort_values("stop_seq")
        t = pd.Timestamp(g["planned_departure"].iloc[0])
        cur = (float(g["depot_lat"].iloc[0]), float(g["depot_lon"].iloc[0]))
        pts = []

        def emit(ts, lat, lon, spd, hdg, nxt, stopped):
            nonlocal gid
            
            nlat = lat + rng.normal(0, 5) / 110574.0
            nlon = lon + rng.normal(0, 5) / (111320.0 * math.cos(math.radians(lat)))
            pts.append(dict(
                gps_id=f"GPS{gid:05d}", delivery_trip_id=trip_id, timestamp=ts,
                lat=round(nlat, 6), lon=round(nlon, 6), speed_kmh=round(max(spd, 0.0), 1),
                heading_deg=round(hdg, 1), next_stop_seq=nxt, is_stopped=int(stopped),
                is_simulated=1, data_source="simulated",
            ))
            gid += 1

        for _, stop in g.iterrows():
            dest = (float(stop["dest_lat"]), float(stop["dest_lon"]))
            hdg = bearing_deg(*cur, *dest)
            dist = haversine_km(*cur, *dest) * detour
            base = float(speed_by_hour.get(t.hour, overall))
            moved, total_s = 0.0, dist / max(base, 5.0) * 3600
            elapsed = 0.0
            while elapsed < total_s:
                frac = min(elapsed / total_s, 1.0)
                spd = max(base * rng.lognormal(0, 0.15), 3.0)
                emit(t + pd.Timedelta(seconds=elapsed),
                     cur[0] + (dest[0] - cur[0]) * frac, cur[1] + (dest[1] - cur[1]) * frac,
                     spd, hdg, int(stop["stop_seq"]), False)
                elapsed += step_s
            t = t + pd.Timedelta(seconds=total_s)
         
            dwell = int(stop["service_time_min"]) * 60
            e = 0
            while e < dwell:
                emit(t + pd.Timedelta(seconds=e), dest[0], dest[1], 0.0, hdg, int(stop["stop_seq"]), True)
                e += step_s
            t = t + pd.Timedelta(seconds=dwell)
            cur = dest
        rows.extend(pts)
    return pd.DataFrame(rows)



def try_osrm(segments: pd.DataFrame, trips: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    try:
        import requests
    except ImportError:
        return segments, trips, "Khong co thu vien requests - bo qua OSRM"
    ok = 0
    for i, s in segments.iterrows():
        url = (f"https://router.project-osrm.org/route/v1/driving/"
               f"{s.start_lon},{s.start_lat};{s.end_lon},{s.end_lat}?overview=false")
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            rt = r.json()["routes"][0]
            segments.loc[i, "osrm_distance_km"] = round(rt["distance"] / 1000, 3)
            segments.loc[i, "osrm_time_min"] = round(rt["duration"] / 60, 2)
            ok += 1
        except Exception as ex:  # mang bi chan / het han muc
            return segments, trips, f"OSRM khong truy cap duoc ({type(ex).__name__}) - de trong osrm_time_min"
    per_route = segments.groupby("route_id")["osrm_time_min"].sum()
    trips["osrm_time_min"] = trips["route_id"].map(per_route).round(2)
    return segments, trips, f"OSRM OK: {ok}/{len(segments)} doan"


# data dictionary
DICT = {
    "trips_history.csv": [
        ("trip_id", "str", "Ma luot di = tuyen_ngay_gio (duy nhat)", "R1_20261019_0600", "real"),
        ("route_id", "str", "R1 Ton Duc Thang-Nguyen Huu Canh, R2 Hai Ba Trung->Dien Bien Phu, R3 Ham Thu Thiem", "R1", "real"),
        ("route_name", "str", "Ten tuyen", "Hầm Thủ Thiêm", "real"),
        ("date", "date", "Ngay (YYYY-MM-DD)", "2026-10-19", "real"),
        ("departure_time", "str", "Gio xuat phat HH:MM", "06:00", "real"),
        ("departure_time_full", "datetime", "Ngay + gio xuat phat", "2026-10-19 06:00:00", "real"),
        ("hour", "int", "Gio xuat phat (0-23)", "6", "feature"),
        ("day_of_week", "int", "Thu trong tuan, 0=Thu Hai ... 6=Chu Nhat", "0", "feature"),
        ("is_weekend", "int", "1 neu Thu Bay/Chu Nhat", "0", "feature"),
        ("time_slot", "str", "Khung gio: dem(0-5h), sang_som(6h), cao_diem_sang(7-9h), trua(10-14h), cao_diem_chieu(15-19h), toi(20-23h)", "cao_diem_chieu", "feature"),
        ("is_peak", "int", "1 neu khung cao diem sang/chieu", "1", "feature"),
        ("distance_km", "float", "Quang duong do tren ban do (km)", "5.3", "feature"),
        ("map_time_min", "str", "Khoang thoi gian ban do hien thi, 'thap - cao' (phut)", "9 - 18", "real"),
        ("map_time_low_min", "float", "Can duoi khoang thoi gian map", "9", "feature"),
        ("map_time_high_min", "float", "Can tren khoang thoi gian map", "18", "feature"),
        ("map_time_mid_min", "float", "Trung diem khoang thoi gian map", "13.5", "feature"),
        ("est_time_min", "float", "Thoi gian du doan trong bao cao tuan 2 (phut)", "14", "real"),
        ("actual_travel_time", "float", "NHAN huan luyen = est_time_min (phut). Chu y: la uoc tinh tu ban do, khong phai do GPS thuc", "14", "label"),
        ("avg_speed_kmh", "float", "Van toc TB = distance_km / est_time_min x 60", "22.7", "real"),
        ("speed_recomputed", "int", "1 neu van toc goc bi hong va da tinh lai", "0", "qc"),
        ("status", "str", "Tinh trang giao thong goc tu ban do", "Chậm nhẹ", "real"),
        ("status_ord", "int", "0 Thong thoang, 1 Cham nhe, 2 Ket xe nang, 3 Un tac nghiem trong (khong dua vao feature de tranh ro ri nhan)", "1", "real"),
        ("weather_desc", "str", "Mo ta thoi tiet TP.HCM", "Nhiều mây", "real"),
        ("weather_code", "str", "Ma thoi tiet chuan hoa", "cloudy", "feature"),
        ("temp_c", "float", "Nhiet do (do C)", "26.3", "feature"),
        ("humidity_pct", "float", "Do am (%)", "81", "feature"),
        ("rain_mm_h", "float", "Luong mua (mm/gio)", "0.0", "feature"),
        ("is_raining", "int", "1 neu rain_mm_h > 0", "0", "feature"),
        ("origin_lat", "float", "Vi do diem dau tuyen (XAP XI)", "10.7691", "approx"),
        ("origin_lon", "float", "Kinh do diem dau tuyen (XAP XI)", "106.7064", "approx"),
        ("dest_lat", "float", "Vi do diem cuoi tuyen (XAP XI)", "10.7975", "approx"),
        ("dest_lon", "float", "Kinh do diem cuoi tuyen (XAP XI)", "106.7215", "approx"),
        ("osrm_time_min", "float", "Thoi gian OSRM tong cac doan (de trong neu chua goi duoc OSRM)", "", "osrm"),
        ("is_simulated", "int", "0 = du lieu that (quan sat tay), 1 = mo phong", "0", "meta"),
        ("data_source", "str", "osrm_api | openstreetmap | simulated | manual", "manual", "meta"),
        ("label_type", "str", "map_estimate = nhan lay tu uoc tinh ban do", "map_estimate", "meta"),
        ("src_row", "int", "So dong trong trip_data.csv goc (truy vet)", "3", "meta"),
    ],
    "ml_features.csv": [
        ("trip_id", "str", "Khoa noi voi trips_history.csv", "R1_20261019_0600", "key"),
        ("route_code", "int", "R1=1, R2=2, R3=3", "1", "feature"),
        ("hour", "int", "Gio xuat phat", "6", "feature"),
        ("day_of_week", "int", "0=Thu Hai", "0", "feature"),
        ("is_weekend", "int", "Cuoi tuan", "0", "feature"),
        ("is_peak", "int", "Cao diem", "1", "feature"),
        ("time_slot_code", "int", "dem0 sang_som1 cao_diem_sang2 trua3 cao_diem_chieu4 toi5", "1", "feature"),
        ("distance_km", "float", "Khoang cach (km)", "5.3", "feature"),
        ("map_time_mid_min", "float", "Trung diem thoi gian ban do (thay the/di kem OSRM)", "13.5", "feature"),
        ("osrm_time_min", "float", "Thoi gian OSRM (co the NaN)", "", "feature"),
        ("temp_c", "float", "Nhiet do", "26.3", "feature"),
        ("humidity_pct", "float", "Do am", "81", "feature"),
        ("rain_mm_h", "float", "Luong mua", "0.0", "feature"),
        ("is_simulated", "int", "0 that / 1 mo phong - dung de loc khi danh gia", "0", "meta"),
        ("target_travel_time_min", "float", "NHAN: thoi gian di (phut)", "14", "label"),
    ],
    "road_segments.csv": [
        ("segment_id", "str", "Ma doan SEG01..SEG12", "SEG01", "key"),
        ("route_id", "str", "Tuyen chua doan", "R1", "key"),
        ("seq", "int", "Thu tu doan trong tuyen", "1", ""),
        ("segment_name", "str", "Ten doan", "", ""),
        ("start_lat", "float", "Vi do diem dau (xap xi)", "10.7691", ""),
        ("start_lon", "float", "Kinh do diem dau (xap xi)", "106.7064", ""),
        ("end_lat", "float", "Vi do diem cuoi (xap xi)", "10.7760", ""),
        ("end_lon", "float", "Kinh do diem cuoi (xap xi)", "106.7062", ""),
        ("road_type", "str", "arterial / tunnel / tunnel_approach", "arterial", ""),
        ("straight_km", "float", "Khoang cach duong chim bay", "0.77", ""),
        ("length_km_est", "float", "Chieu dai uoc tinh = ty le x quang duong tuyen", "1.17", ""),
        ("osrm_distance_km", "float", "Quang duong OSRM (neu co)", "", ""),
        ("osrm_time_min", "float", "Thoi gian OSRM (neu co)", "", ""),
        ("coord_source", "str", "manual_approx = dat tay xap xi", "manual_approx", ""),
        ("needs_verification", "int", "1 = can doi chieu lai toa do", "1", ""),
    ],
    "traffic_observations.csv": [
        ("obs_id", "str", "Ma quan sat", "", "key"),
        ("observation_level", "str", "route (that) | segment (mo phong)", "route", ""),
        ("route_id", "str", "Tuyen", "R1", ""),
        ("segment_id", "str", "Doan (rong neu muc tuyen)", "", ""),
        ("obs_time", "datetime", "Thoi diem quan sat", "2026-10-19 06:00:00", ""),
        ("hour", "int", "Gio", "6", ""),
        ("day_of_week", "int", "0=Thu Hai", "0", ""),
        ("time_slot", "str", "Khung gio", "sang_som", ""),
        ("speed_kmh", "float", "Van toc (km/h)", "26.5", ""),
        ("status", "str", "Tinh trang giao thong goc", "Thông thoáng", ""),
        ("is_simulated", "int", "0 that / 1 mo phong", "0", ""),
        ("data_source", "str", "manual (that) | simulated", "manual", ""),
        ("note", "str", "Ghi chu xu ly", "", ""),
    ],
    "delivery_orders.csv": [
        ("order_id", "str", "Ma don ORD001..", "ORD001", "key"),
        ("delivery_trip_id", "str", "Ma chuyen giao DT01.. (3-5 diem/chuyen)", "DT01", ""),
        ("stop_seq", "int", "Thu tu diem giao", "1", ""),
        ("order_date", "date", "Ngay giao", "2026-11-02", ""),
        ("planned_departure", "datetime", "Gio xuat phat du kien tu kho", "2026-11-02 08:00:00", ""),
        ("depot_id/lat/lon", "", "Kho xuat phat (mo phong)", "DEPOT01", ""),
        ("dest_zone", "str", "Khu vuc giao", "Quận 1", ""),
        ("dest_lat/lon", "float", "Toa do diem giao (ngau nhien trong khu vuc)", "", ""),
        ("address_label", "str", "Nhan dia chi gia lap, khong co dia chi that", "", ""),
        ("weight_kg", "float", "Khoi luong (kg)", "4.2", ""),
        ("service_time_min", "int", "Thoi gian giao tai diem (phut)", "5", ""),
        ("time_window_start/end", "str", "Khung gio giao HH:MM", "08:20", ""),
        ("is_simulated", "int", "Luon 1", "1", ""),
        ("data_source", "str", "simulated", "simulated", ""),
    ],
    "gps_simulated.csv": [
        ("gps_id", "str", "Ma diem GPS", "GPS00001", "key"),
        ("delivery_trip_id", "str", "Chuyen giao hang (noi voi delivery_orders)", "DT01", ""),
        ("timestamp", "datetime", "Thoi diem (moi 30 giay)", "2026-11-02 08:00:00", ""),
        ("lat/lon", "float", "Toa do co nhieu GPS ~5 m; noi suy duong thang x he so 1.3, CHUA map-matching", "", ""),
        ("speed_kmh", "float", "Van toc tuc thoi (0 khi dung giao hang)", "21.4", ""),
        ("heading_deg", "float", "Huong di (do, 0=Bac)", "45.0", ""),
        ("next_stop_seq", "int", "Diem giao ke tiep", "1", ""),
        ("is_stopped", "int", "1 khi dang giao tai diem", "0", ""),
        ("is_simulated", "int", "Luon 1", "1", ""),
        ("data_source", "str", "simulated", "simulated", ""),
    ],
}


def write_dictionary(out: Path) -> None:
    rows = []
    for f, cols in DICT.items():
        for c in cols:
            rows.append(dict(file=f, column=c[0], dtype=c[1], description=c[2], example=c[3], role=c[4]))
    pd.DataFrame(rows).to_csv(out / "data_dictionary.csv", index=False, encoding="utf-8-sig")


def write_report(out: Path, raw_rows: int, trips: pd.DataFrame, segments, obs, orders, gps,
                 issues: list[dict], osrm_msg: str) -> None:
    L = []
    a = L.append
    a("# Báo cáo chất lượng dữ liệu - Tuần 3\n")
    a(f"Nguồn: `trip_data.csv` (báo cáo tuần 2). Sinh tự động bởi `prepare_week3_data.py` (seed={SEED}).\n")
    a("## 1. Tổng quan\n")
    a("| Tập dữ liệu | Số dòng | Loại | Nguồn |")
    a("|---|---|---|---|")
    a(f"| trips_history.csv | {len(trips)} | THẬT (quan sát tay từ bản đồ) | manual |")
    a(f"| ml_features.csv | {len(trips)} | THẬT | manual |")
    a(f"| road_segments.csv | {len(segments)} | Tọa độ xấp xỉ | manual_approx |")
    real_o = int((obs.is_simulated == 0).sum())
    sim_o = int((obs.is_simulated == 1).sum())
    a(f"| traffic_observations.csv | {len(obs)} ({real_o} thật mức tuyến + {sim_o} mô phỏng mức đoạn) | Hỗn hợp, có cột is_simulated | manual / simulated |")
    a(f"| delivery_orders.csv | {len(orders)} đơn, {orders.delivery_trip_id.nunique()} chuyến | MÔ PHỎNG | simulated |")
    a(f"| gps_simulated.csv | {len(gps)} điểm | MÔ PHỎNG | simulated |")
    a("")
    d0, d1 = trips["date"].min().date(), trips["date"].max().date()
    a("## 2. Dữ liệu thật (trips_history)\n")
    a(f"- Khoảng thời gian: {d0} -> {d1} ({trips['date'].nunique()} ngày), {raw_rows} mốc giờ x 3 tuyến = {len(trips)} lượt.")
    a(f"- Ngày cuối tuần: {sorted(trips[trips.is_weekend==1]['date'].dt.strftime('%d/%m').unique())}.")
    a(f"- Trùng lặp (ngày, giờ, tuyến): {int(trips.duplicated(['route_id','departure_time_full']).sum())}.")
    a(f"- Giá trị thiếu ở cột nhãn / feature chính: "
      f"{int(trips[['distance_km','actual_travel_time','avg_speed_kmh','temp_c','humidity_pct','rain_mm_h']].isna().sum().sum())}.")
    a("")
    a("Thống kê theo tuyến:\n")
    a("| Tuyến | Số lượt | Km (min-max) | Thời gian phút (TB) | Vận tốc km/h (TB) |")
    a("|---|---|---|---|---|")
    for rid, g in trips.groupby("route_id"):
        a(f"| {rid} | {len(g)} | {g.distance_km.min()}-{g.distance_km.max()} | {g.actual_travel_time.mean():.1f} | {g.avg_speed_kmh.mean():.1f} |")
    a("")
    a("## 3. Lỗi phát hiện & cách xử lý\n")
    if issues:
        a("| Mục | Mô tả | Xử lý |")
        a("|---|---|---|")
        for i in issues:
            a(f"| {i['muc']} | {i['mo_ta']} | {i['xu_ly']} |")
    else:
        a("Không có lỗi.")
    a("")
    a("## 4. Lưu ý quan trọng khi huấn luyện\n")
    a("1. **Nhãn không phải đo thực**: `actual_travel_time` = cột \"Khoảng thời gian dự đoán\" của tuần 2 (ước tính từ bản đồ), "
      "nên mô hình học lại ước tính bản đồ chứ chưa phải thời gian GPS thực. Ghi nhận ở cột `label_type = map_estimate`.")
    n_out = {}
    for rid, g in trips.groupby("route_id"):
        n_out[rid] = int(((g.est_time_min < g.map_time_low_min) | (g.est_time_min > g.map_time_high_min)).sum())
    a(f"2. **Thời gian dự đoán nằm ngoài khoảng bản đồ**: số lượt lệch theo tuyến = {n_out}. Nên kiểm tra lại cách lấy số khi tuần 3 làm việc với Người 3.")
    a("3. **Thang tình trạng không đồng nhất**: Tuyến 2 dùng \"Ùn tắc nghiêm trọng\" còn Tuyến 1, 3 dùng \"Kẹt xe nặng\"; đã quy về `status_ord` 0-3. "
      "Không đưa `status` vào feature vì suy ra trực tiếp từ vận tốc (rò rỉ nhãn).")
    a(f"4. **Dữ liệu ngắn**: chỉ {trips['date'].nunique()} ngày (≈ 2 tuần), mới có {trips[trips.is_weekend==1]['date'].nunique()} ngày cuối tuần; "
      "nên chia train/test theo ngày, không xáo trộn ngẫu nhiên.")
    a("5. **Tọa độ đoạn đường là xấp xỉ** (`needs_verification = 1`). Cần đối chiếu bằng OSRM/Google Maps trước khi dùng trong báo cáo.")
    a(f"6. **OSRM**: {osrm_msg}.")
    a("7. **Dữ liệu mô phỏng** (đoạn đường, đơn hàng, GPS) luôn có `is_simulated = 1`; chỉ dùng để dựng/kiểm thử pipeline tuần 4, "
      "không dùng để báo cáo độ chính xác.")
    a("8. GPS mô phỏng nội suy đường thẳng x hệ số 1.3, chưa bám theo đường thật (chưa map-matching).\n")
    a("## 5. Kiểm tra tự động\n")
    a("- `validate_trips_csv.py` chạy trên `trips_history.csv` (xem kết quả ở cuối `prepare_week3_data.py`).")
    a("- Lưu ý: `validate_trips_csv.py` với file báo cáo gốc báo OK nhưng **không kiểm tra cột vận tốc**, nên không phát hiện 4 giá trị hỏng ở mục 3.")
    (out / "data_quality_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def write_manifest(out: Path, input_path: Path, files: list[str]) -> None:
    manifest = {
        "seed": SEED,
        "input": {"file": input_path.name, "sha256": sha256(input_path), "locked": True},
        "outputs": {f: sha256(out / f) for f in files},
    }
    (out / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def verify(out: Path, input_path: Path) -> int:
    mp = out / "dataset_manifest.json"
    if not mp.exists():
        print("[LOI] Chua co dataset_manifest.json - hay chay pipeline truoc")
        return 1
    m = json.loads(mp.read_text(encoding="utf-8"))
    bad = 0
    cur = sha256(input_path)
    ok = cur == m["input"]["sha256"]
    print(f"[{'OK' if ok else 'LOI'}] input {input_path.name}")
    bad += not ok
    for f, h in m["outputs"].items():
        p = out / f
        ok = p.exists() and sha256(p) == h
        print(f"[{'OK' if ok else 'LOI'}] {f}")
        bad += not ok
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Pipeline du lieu tuan 3")
    ap.add_argument("--input", type=Path, default=HERE / "trip_data.csv")
    ap.add_argument("--out", type=Path, default=HERE / "week3_output")
    ap.add_argument("--osrm", action="store_true", help="thu goi OSRM public (can internet)")
    ap.add_argument("--verify", action="store_true", help="chi kiem tra checksum")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args.out.mkdir(parents=True, exist_ok=True)

    if args.verify:
        return verify(args.out, args.input)

    rng = np.random.default_rng(SEED)
    issues: list[dict] = []

    raw = read_report(args.input)
    trips = build_trips(raw, issues)
    segments = build_segments(trips)

    osrm_msg = "Không gọi OSRM (chạy với --osrm để thử); cột osrm_time_min để trống"
    if args.osrm:
        segments, trips, osrm_msg = try_osrm(segments, trips)
        print("[OSRM]", osrm_msg)

    obs = build_observations(trips, rng)
    orders = build_orders(rng)
    gps = build_gps(orders, trips, rng)

    # ghi file
    t_out = trips[TRIP_COLS].copy()
    t_out["date"] = t_out["date"].dt.strftime("%Y-%m-%d")
    t_out["departure_time_full"] = t_out["departure_time_full"].dt.strftime("%Y-%m-%d %H:%M:%S")
    t_out.to_csv(args.out / "trips_history.csv", index=False, encoding="utf-8-sig")

    ml = pd.DataFrame({
        "trip_id": trips["trip_id"],
        "route_code": trips["route_id"].str[1:].astype(int),
        "hour": trips["hour"], "day_of_week": trips["day_of_week"],
        "is_weekend": trips["is_weekend"], "is_peak": trips["is_peak"],
        "time_slot_code": trips["time_slot_code"],
        "distance_km": trips["distance_km"], "map_time_mid_min": trips["map_time_mid_min"],
        "osrm_time_min": trips["osrm_time_min"],
        "temp_c": trips["temp_c"], "humidity_pct": trips["humidity_pct"], "rain_mm_h": trips["rain_mm_h"],
        "is_simulated": trips["is_simulated"],
        "target_travel_time_min": trips["actual_travel_time"],
    })
    ml.to_csv(args.out / "ml_features.csv", index=False, encoding="utf-8-sig")

    segments.to_csv(args.out / "road_segments.csv", index=False, encoding="utf-8-sig")
    o_out = obs.copy()
    o_out["obs_time"] = pd.to_datetime(o_out["obs_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    o_out.to_csv(args.out / "traffic_observations.csv", index=False, encoding="utf-8-sig")

    od = orders.copy()
    od["planned_departure"] = od["planned_departure"].dt.strftime("%Y-%m-%d %H:%M:%S")
    od.to_csv(args.out / "delivery_orders.csv", index=False, encoding="utf-8-sig")
    g_out = gps.copy()
    g_out["timestamp"] = g_out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    g_out.to_csv(args.out / "gps_simulated.csv", index=False, encoding="utf-8-sig")

    write_dictionary(args.out)
    write_report(args.out, len(raw), trips, segments, obs, orders, gps, issues, osrm_msg)

    files = ["trips_history.csv", "ml_features.csv", "road_segments.csv", "traffic_observations.csv",
             "delivery_orders.csv", "gps_simulated.csv", "data_dictionary.csv", "data_quality_report.md"]
    write_manifest(args.out, args.input, files)

    # --- kiem tra tu dong ---
    print(f"[OK] trips_history: {len(trips)} luot | segments: {len(segments)} | "
          f"observations: {len(obs)} | orders: {len(orders)} ({orders.delivery_trip_id.nunique()} chuyen) | gps: {len(gps)}")
    sizes = orders.groupby("delivery_trip_id").size()
    assert sizes.between(3, 5).all(), "chuyen giao hang phai co 3-5 diem"
    assert 50 <= len(orders) <= 100, "so don phai tu 50-100"
    assert 10 <= len(segments) <= 15, "so doan phai tu 10-15"
    assert trips["trip_id"].is_unique, "trip_id trung"

    validator = HERE / "validate_trips_csv.py"
    if validator.exists():
        r = subprocess.run([sys.executable, str(validator), str(args.out / "trips_history.csv")],
                           capture_output=True, text=True, encoding="utf-8")
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            return 1
    else:
        print("[CANH BAO] khong tim thay validate_trips_csv.py canh script, bo qua buoc kiem tra")
    print(f"Da ghi file vao: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
