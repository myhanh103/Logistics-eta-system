from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import urllib.request
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent          # thư mục data/
PROCESSED = ROOT / "processed"
SIM = ROOT / "simulated"
SCEN_DIR = SIM / "gps_scenarios"
CACHE = SIM / "osrm_cache"
SEED = 2026

SCENARIOS = {
    "S01_normal": "Di chuyển bình thường (không có bất thường)",
    "S02_long_stop": "Dừng lâu: một điểm giao bị dừng thêm 15-30 phút",
    "S03_traffic_jam": "Kẹt xe mô phỏng: vận tốc giảm còn 20-40% trên đoạn dài 300-600 m",
    "S04_gps_loss": "Mất GPS: 1-3 khoảng mất tín hiệu 1-8 phút (thiếu dòng)",
    "S05_route_deviation": "Lệch tuyến: xe đi lệch 250-700 m rồi quay lại",
    "S06_bad_gps": "GPS sai: nhảy vị trí, trôi, tọa độ null/0, đảo lat-lon, tốc độ đột biến, trùng dòng, sai thứ tự",
}
SCENARIO_TRIPS = 5          # số chuyến áp dụng mỗi kịch bản (S01 cũng lấy 5 chuyến từ dataset chính)

LAT0, LON0 = 10.78, 106.70
M_LAT = 110574.0
M_LON = 111320.0 * math.cos(math.radians(LAT0))


def to_xy(lat, lon):
    return (lon - LON0) * M_LON, (lat - LAT0) * M_LAT


def to_ll(x, y):
    return y / M_LAT + LAT0, x / M_LON + LON0


class Polyline:

    def __init__(self, pts_ll):
        xy = [to_xy(la, lo) for la, lo in pts_ll]
        keep = [xy[0]]
        for p in xy[1:]:
            if math.hypot(p[0] - keep[-1][0], p[1] - keep[-1][1]) > 0.5:
                keep.append(p)
        if len(keep) < 2:
            keep.append((keep[0][0] + 1.0, keep[0][1]))
        self.xy = np.array(keep)
        seg = np.hypot(*np.diff(self.xy, axis=0).T)
        self.seg = seg
        self.cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.cum[-1])

    def at(self, d):
        d = min(max(d, 0.0), self.length)
        i = min(int(np.searchsorted(self.cum, d, side="right")) - 1, len(self.seg) - 1)
        t = (d - self.cum[i]) / self.seg[i]
        p = self.xy[i] + t * (self.xy[i + 1] - self.xy[i])
        u = (self.xy[i + 1] - self.xy[i]) / self.seg[i]
        return (float(p[0]), float(p[1])), (float(u[0]), float(u[1]))


def synthetic_geometry(a, b, key):
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)
    ax, ay = to_xy(*a)
    bx, by = to_xy(*b)
    f = 0.35 + ((h >> 3) % 30) / 100.0
    if h % 2 == 0:
        pts = [(ax, ay), (ax, ay + (by - ay) * f), (bx, ay + (by - ay) * f), (bx, by)]
    else:
        pts = [(ax, ay), (ax + (bx - ax) * f, ay), (ax + (bx - ax) * f, by), (bx, by)]
    return [to_ll(x, y) for x, y in pts]


def get_geometry(a, b, use_osrm, stats):
    key = f"{a[0]:.6f},{a[1]:.6f};{b[0]:.6f},{b[1]:.6f}"
    f = CACHE / (hashlib.md5(key.encode()).hexdigest() + ".json")
    if f.exists():
        data = json.loads(f.read_text(encoding="utf-8"))
        stats["osrm"] += 1
        return [(la, lo) for lo, la in data["coordinates"]], "osrm"
    if use_osrm:
        url = (f"https://router.project-osrm.org/route/v1/driving/{a[1]:.6f},{a[0]:.6f};"
               f"{b[1]:.6f},{b[0]:.6f}?overview=full&geometries=geojson")
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                rt = json.loads(r.read().decode())["routes"][0]
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({
                "key": key, "distance_m": rt["distance"], "duration_s": rt["duration"],
                "coordinates": rt["geometry"]["coordinates"]}), encoding="utf-8")
            stats["osrm"] += 1
            time.sleep(1.0)  # tránh vượt hạn mức của máy chủ OSRM công cộng
            return [(la, lo) for lo, la in rt["geometry"]["coordinates"]], "osrm"
        except Exception as ex:
            stats["osrm_errors"] += 1
            if stats["osrm_errors"] == 1:
                print(f"[CẢNH BÁO] Không gọi được OSRM ({type(ex).__name__}: {ex}); dùng geometry tổng hợp")
    stats["synthetic"] += 1
    return synthetic_geometry(a, b, key), "synthetic"

#Mô phỏng một chuyến
def make_hour_speed(obs: pd.DataFrame):
    real = obs[(obs["is_simulated"] == 0) & (obs["observation_level"] == "route")]
    med = real.groupby("hour")["speed_kmh"].median()
    overall = float(real["speed_kmh"].median())
    return lambda h: float(med.get(h, overall))


def plan_kinematic(name, leg_lengths, n_stops, rng):
    p = np.array(leg_lengths) / sum(leg_lengths)
    sp = {}
    if name == "S02_long_stop":
        sp["long_stop"] = {"stop_idx": int(rng.integers(0, n_stops)), "extra_s": int(rng.integers(900, 1801))}
    elif name == "S03_traffic_jam":
        leg = int(rng.choice(len(p), p=p))
        L = leg_lengths[leg]
        jlen = min(float(rng.uniform(300, 600)), 0.8 * L)          # đoạn kẹt dài 300-600 m
        f0 = float(rng.uniform(0.05, max(0.06, 1 - jlen / L - 0.05)))
        sp["jam"] = {"leg": leg, "f0": f0, "f1": min(1.0, f0 + jlen / L), "factor": float(rng.uniform(0.2, 0.4))}
    elif name == "S05_route_deviation":
        f0 = float(rng.uniform(0.2, 0.45))
        sp["dev"] = {"leg": int(rng.choice(len(p), p=p)), "f0": f0, "f1": f0 + float(rng.uniform(0.25, 0.4)),
                     "peak": float(rng.uniform(250, 700)), "side": float(rng.choice([-1.0, 1.0]))}
    return sp


def simulate_trip(trip_id, orders, legs, geo_src, hour_speed, interval, rng, scen, sp, vehicle):
    t0 = pd.Timestamp(orders["planned_departure"].iloc[0])
    sec0 = t0.hour * 3600 + t0.minute * 60 + t0.second
    n = len(legs)
    service = [int(s) * 60 for s in orders["service_time_min"]]
    day = t0.strftime("%Y-%m-%d")
    win = [(pd.Timestamp(f"{day} {a}"), pd.Timestamp(f"{day} {b}"))
           for a, b in zip(orders["time_window_start"], orders["time_window_end"])]
    ls, jam, dev = sp.get("long_stop"), sp.get("jam"), sp.get("dev")

    rows, events, logs = [], [], []
    sec, leg, d, v = 0, 0, 0.0, 0.0
    phase, dwell, extra, light = "drive", 0, 0, 0
    hdg = 0.0
    track = {}   #theo dõi các dòng bất thường để ghi vào log

    def mark(kind, cur):
        track.setdefault(kind, [cur, cur])[1] = cur

    while sec < 6 * 3600:
        cur = t0 + pd.Timedelta(seconds=sec)
        L = legs[leg]
        in_jam = bool(jam and jam["leg"] == leg and jam["f0"] * L.length <= d <= jam["f1"] * L.length)
        in_dev = bool(dev and dev["leg"] == leg and dev["f0"] * L.length <= d <= dev["f1"] * L.length)

        #ghi dữ liệu GPS mỗi interval giây
        if sec % interval == 0:
            (px, py), (ux, uy) = L.at(d)
            off = 0.0
            if in_dev:
                fr = (d - dev["f0"] * L.length) / ((dev["f1"] - dev["f0"]) * L.length)
                off = dev["peak"] * math.sin(math.pi * min(max(fr, 0), 1)) * dev["side"]
            tx, ty = px + uy * off, py - ux * off                  # vị trí thật của xe
            if phase == "drive" and v > 0.5:
                hdg = (math.degrees(math.atan2(ux, uy)) + 360) % 360
            ox, oy = tx + rng.normal(0, 4.0), ty + rng.normal(0, 4.0)   
            lat, lon = to_ll(ox, oy)
            tlat, tlon = to_ll(tx, ty)
            stopped = phase in ("delivery", "long_stop")
            spd = abs(rng.normal(0, 0.3)) if v < 0.5 else max(0.0, v + rng.normal(0, 0.4))
            rows.append(dict(
                scenario_id=scen, delivery_trip_id=trip_id, vehicle_id=vehicle,
                timestamp=cur, seq=len(rows), lat=round(lat, 6), lon=round(lon, 6),
                speed_kmh=round(spd, 1), heading_deg=round((hdg + rng.normal(0, 3)) % 360, 1),
                next_stop_seq=leg + 1, phase=phase, is_stopped=int(stopped),
                route_offset_m=round(abs(off), 1),
                true_lat=round(tlat, 6), true_lon=round(tlon, 6), geometry_source=geo_src[leg],
                is_anomaly=0, anomaly_type="",
            ))
            lab = "off_route" if abs(off) > 30 else "long_stop" if phase == "long_stop" else "traffic_jam" if in_jam else ""
            if lab:
                rows[-1]["is_anomaly"], rows[-1]["anomaly_type"] = 1, lab
            if abs(off) > 30:
                mark("off_route", cur)
        if in_jam:
            mark("traffic_jam", cur)

        #cập nhật vận tốc, vị trí, trạng thái
        if phase == "drive":
            h = ((sec0 + sec) // 3600) % 24
            factor = jam["factor"] if in_jam else 1.0
            v += 0.15 * (hour_speed(h) * factor - v) + rng.normal(0, 0.5)
            v = max(v, 0.0)
            if not in_jam and rng.random() < 1 / 300:  #đèn đỏ
                phase, light, v = "light", int(rng.integers(15, 45)), 0.0
            d += v / 3.6
            if d >= L.length:
                d, v = L.length, 0.0
                phase, dwell = "delivery", service[leg]
                extra = ls["extra_s"] if (ls and ls["stop_idx"] == leg) else 0
                events.append(dict(delivery_trip_id=trip_id, stop_seq=leg + 1, arrival_time=cur,
                                   window_start=win[leg][0], window_end=win[leg][1], service_s=service[leg],
                                   extra_stop_s=extra, _leg=leg))
        elif phase == "light":
            light -= 1
            if light <= 0:
                phase = "drive"
        else:  
            dwell -= 1
            if phase == "long_stop":
                mark("long_stop", cur)
            if dwell <= 0:
                if phase == "delivery" and extra > 0:
                    phase, dwell = "long_stop", extra
                    mark("long_stop", cur)
                else:
                    events[-1]["departure_time"] = cur
                    leg += 1
                    if leg >= n:
                        break
                    d, v, phase = 0.0, 0.0, "drive"
        sec += 1

    kinds = {"traffic_jam": ("Kẹt xe", sp.get("jam")), "long_stop": ("Dừng lâu", sp.get("long_stop")),
             "off_route": ("Lệch tuyến", sp.get("dev"))}
    for k, (s, e) in track.items():
        logs.append(dict(scenario_id=scen, delivery_trip_id=trip_id, anomaly_type=k, start_time=s, end_time=e,
                         duration_s=int((e - s).total_seconds()),
                         detail=json.dumps(kinds[k][1], ensure_ascii=False)))
    return rows, events, logs



def apply_gps_loss(df, trip_id, rng, logs, scen):
    ts = df["timestamp"]
    t_start, t_end = ts.min(), ts.max()
    dur = (t_end - t_start).total_seconds()
    k = int(rng.integers(1, 4))
    keep = np.ones(len(df), dtype=bool)
    for i in range(k):
        length = int(rng.integers(300, 481)) if (i == 0 and k >= 2) else int(rng.integers(60, 301))
        kind = "gps_loss_long" if length >= 300 else "gps_loss"
        s = t_start + pd.Timedelta(seconds=float(rng.uniform(0.05, 0.9) * dur))
        e = s + pd.Timedelta(seconds=length)
        m = (ts >= s) & (ts < e)
        n_drop = int(m.sum())
        if n_drop == 0:
            continue
        keep &= ~m.to_numpy()
        logs.append(dict(scenario_id=scen, delivery_trip_id=trip_id, anomaly_type=kind, start_time=s,
                         end_time=e, duration_s=length, detail=json.dumps({"rows_dropped": n_drop})))
    return df[keep].reset_index(drop=True)


def apply_bad_gps(df, trip_id, rng, logs, scen):
    df = df.copy()
    n = len(df)
    free = list(range(n))
    rng.shuffle(free)

    def take(frac):
        k = max(1, int(round(frac * n)))
        got = [free.pop() for _ in range(min(k, len(free)))]
        return sorted(got)

    def tag(idx, kind):
        for i in idx:
            df.loc[i, ["is_anomaly", "anomaly_type"]] = [1, kind]
            logs.append(dict(scenario_id=scen, delivery_trip_id=trip_id, anomaly_type=kind,
                             start_time=df.loc[i, "timestamp"], end_time=df.loc[i, "timestamp"], duration_s=0, detail=""))

    for i in take(0.015):                                            
        r, a = rng.uniform(800, 5000), rng.uniform(0, 2 * math.pi)
        x, y = to_xy(df.loc[i, "lat"], df.loc[i, "lon"])
        df.loc[i, ["lat", "lon"]] = [round(v, 6) for v in to_ll(x + r * math.cos(a), y + r * math.sin(a))]
        tag([i], "outlier_jump")
    idx = take(0.007)                       #tốc độ đột biến
    for i in idx:
        df.loc[i, "speed_kmh"] = round(float(rng.uniform(90, 220)), 1)
    tag(idx, "speed_spike")
    idx = take(0.005)                                                
    df.loc[idx, ["lat", "lon"]] = np.nan
    tag(idx, "null_coord")
    idx = take(0.003)                                               
    df.loc[idx, ["lat", "lon"]] = 0.0
    tag(idx, "zero_coord")
    for i in take(0.003):                                           
        la, lo = df.loc[i, "lat"], df.loc[i, "lon"]
        df.loc[i, ["lat", "lon"]] = [lo, la]
        tag([i], "swapped_latlon")
    for i in take(0.003):                                           
        if i + 1 < n:
            a, b = df.loc[i, "timestamp"], df.loc[i + 1, "timestamp"]
            df.loc[i, "timestamp"], df.loc[i + 1, "timestamp"] = b, a
            tag([i, i + 1], "out_of_order")
    if n > 80:                                                       
        w = int(rng.integers(60, 85))
        s = int(rng.integers(0, max(1, n - w)))
        bias, ang = float(rng.uniform(80, 200)), float(rng.uniform(0, 2 * math.pi))
        for j in range(w):
            i = s + j
            if i in free:
                free.remove(i)
            x, y = to_xy(df.loc[i, "lat"], df.loc[i, "lon"])
            m = bias * (j + 1) / w
            df.loc[i, ["lat", "lon"]] = [round(v, 6) for v in to_ll(x + m * math.cos(ang), y + m * math.sin(ang))]
            df.loc[i, ["is_anomaly", "anomaly_type"]] = [1, "drift"]
        logs.append(dict(scenario_id=scen, delivery_trip_id=trip_id, anomaly_type="drift",
                         start_time=df.loc[s, "timestamp"], end_time=df.loc[s + w - 1, "timestamp"],
                         duration_s=w * int((df["timestamp"].iloc[1] - df["timestamp"].iloc[0]).total_seconds() or 5),
                         detail=json.dumps({"max_bias_m": round(bias, 1)})))
    dup_idx = take(0.01)                                             
    dups = df.loc[dup_idx].copy()
    dups["is_anomaly"], dups["anomaly_type"] = 1, "duplicate_row"
    for i in dup_idx:
        logs.append(dict(scenario_id=scen, delivery_trip_id=trip_id, anomaly_type="duplicate_row",
                         start_time=df.loc[i, "timestamp"], end_time=df.loc[i, "timestamp"], duration_s=0, detail=""))
    df = pd.concat([df, dups]).sort_values("seq", kind="stable").reset_index(drop=True)
    return df


#dựng dataset GPS và các kịch bản
def build(interval=5, use_osrm=False, verbose=True):
    if not 5 <= interval <= 10:
        raise SystemExit("[LỖI] --interval phải nằm trong khoảng 5-10 giây")
    orders = pd.read_csv(PROCESSED / "delivery_orders.csv")
    obs = pd.read_csv(PROCESSED / "traffic_observations.csv")
    hs = make_hour_speed(obs)
    trips = sorted(orders["delivery_trip_id"].unique())

    stats = {"osrm": 0, "synthetic": 0, "osrm_errors": 0}
    geo = {}
    for tid in trips:
        g = orders[orders["delivery_trip_id"] == tid].sort_values("stop_seq")
        pts = [(float(g["depot_lat"].iloc[0]), float(g["depot_lon"].iloc[0]))] + \
              [(float(a), float(b)) for a, b in zip(g["dest_lat"], g["dest_lon"])]
        legs, src = [], []
        for a, b in zip(pts[:-1], pts[1:]):
            pl, s = get_geometry(a, b, use_osrm, stats)
            legs.append(Polyline(pl))
            src.append(s)
        geo[tid] = (g, legs, src)

    def vehicle(i):
        return f"VH{i % 5 + 1:02d}"

    main_rows, all_events, main_by_trip = [], [], {}
    for i, tid in enumerate(trips):
        g, legs, src = geo[tid]
        rng = np.random.default_rng([SEED, i])
        rows, ev, _ = simulate_trip(tid, g, legs, src, hs, interval, rng, "S01_normal", {}, vehicle(i))
        main_by_trip[tid] = pd.DataFrame(rows)
        all_events += ev
    main = pd.concat(main_by_trip.values(), ignore_index=True)
    main["scenario_id"] = "S00_main"
    ev = pd.DataFrame(all_events).drop(columns="_leg")

    out = {"main": main, "events": ev, "scenarios": {}, "log": [], "stats": stats, "interval": interval,
           "legs": {t: [float(l.length) for l in geo[t][1]] for t in trips}}

    for si, name in enumerate(SCENARIOS):
        pick_rng = np.random.default_rng([SEED, 100 + si])
        chosen = sorted(pick_rng.choice(trips, size=SCENARIO_TRIPS, replace=False))
        frames, logs = [], []
        for tid in chosen:
            i = trips.index(tid)
            g, legs, src = geo[tid]
            if name == "S01_normal":
                df = main_by_trip[tid].copy()
                df["scenario_id"] = name
            else:
                sp_rng = np.random.default_rng([SEED, 200 + si, i])
                sp = plan_kinematic(name, [l.length for l in legs], len(g), sp_rng)
                rng = np.random.default_rng([SEED, i])         
                rows, _, lg = simulate_trip(tid, g, legs, src, hs, interval, rng, name, sp, vehicle(i))
                df, logs = pd.DataFrame(rows), logs + lg
                an_rng = np.random.default_rng([SEED, 300 + si, i])
                if name == "S04_gps_loss":
                    df = apply_gps_loss(df, tid, an_rng, logs, name)
                elif name == "S06_bad_gps":
                    df = apply_bad_gps(df, tid, an_rng, logs, name)
            frames.append(df)
        out["scenarios"][name] = pd.concat(frames, ignore_index=True)
        out["log"] += logs
        if verbose:
            print(f"  {name}: {len(out['scenarios'][name])} dòng, {len(chosen)} chuyến ({', '.join(chosen)})")
    return out


COLS = ["gps_id", "scenario_id", "delivery_trip_id", "vehicle_id", "timestamp", "seq", "lat", "lon", "speed_kmh",
        "heading_deg", "next_stop_seq", "phase", "is_stopped", "route_offset_m", "true_lat", "true_lon",
        "geometry_source", "is_anomaly", "anomaly_type", "is_simulated", "data_source"]


def finalize(df):
    df = df.copy()
    #gps_id = kịch bản + mã chuyến + số thứ tự trong chuyến 
    df["gps_id"] = df["scenario_id"] + "_" + df["delivery_trip_id"] + "_" + \
        (df.groupby(["scenario_id", "delivery_trip_id"]).cumcount() + 1).astype(str).str.zfill(5)
    df["is_simulated"], df["data_source"] = 1, "simulated"
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return df[COLS]


def write_outputs(out):
    SCEN_DIR.mkdir(parents=True, exist_ok=True)
    finalize(out["main"]).to_csv(SIM / "gps_simulated.csv", index=False, encoding="utf-8-sig")
    idx = []
    for name, df in out["scenarios"].items():
        f = finalize(df)
        f.to_csv(SCEN_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
        idx.append(dict(scenario_id=name, file=f"{name}.csv", description=SCENARIOS[name],
                        n_trips=df["delivery_trip_id"].nunique(), n_rows=len(df),
                        n_anomaly_rows=int(df["is_anomaly"].sum())))
    pd.DataFrame(idx).to_csv(SCEN_DIR / "scenario_index.csv", index=False, encoding="utf-8-sig")
    log = pd.DataFrame(out["log"])
    if not log.empty:
        for c in ("start_time", "end_time"):
            log[c] = pd.to_datetime(log[c]).dt.strftime("%Y-%m-%d %H:%M:%S")
    log.to_csv(SCEN_DIR / "anomaly_log.csv", index=False, encoding="utf-8-sig")

    ev = out["events"].copy()
    ev["delay_vs_window_end_min"] = ((ev["arrival_time"] - ev["window_end"]).dt.total_seconds() / 60).round(1)
    ev["on_time"] = (ev["arrival_time"] <= ev["window_end"]).astype(int)
    ev["arrived_early"] = (ev["arrival_time"] < ev["window_start"]).astype(int)
    for c in ("arrival_time", "departure_time", "window_start", "window_end"):
        ev[c] = pd.to_datetime(ev[c]).dt.strftime("%Y-%m-%d %H:%M:%S")
    ev["is_simulated"], ev["data_source"] = 1, "simulated"
    ev.to_csv(SIM / "stop_events.csv", index=False, encoding="utf-8-sig")


#phát gps theo thời gian thực hoặc nhanh hơn
def make_sink(spec):
    """stdout | file:đường_dẫn.jsonl | file:đường_dẫn.csv | http:URL"""
    if spec == "stdout":
        return lambda recs: [print(json.dumps(r, ensure_ascii=False), flush=True) for r in recs], lambda: None
    kind, _, target = spec.partition(":")
    if kind == "file":
        fh = open(target, "w", encoding="utf-8", newline="")
        state = {"header": False}
        if target.endswith(".csv"):
            def w(recs):
                if not recs:
                    return
                if not state["header"]:
                    fh.write(",".join(recs[0].keys()) + "\n")
                    state["header"] = True
                for r in recs:
                    fh.write(",".join("" if v is None else str(v) for v in r.values()) + "\n")
                fh.flush()
        else:
            def w(recs):
                for r in recs:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
        return w, fh.close
    if kind == "http":
        def w(recs):
            req = urllib.request.Request(target, data=json.dumps(recs, ensure_ascii=False).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=10).read()
        return w, lambda: None
    raise SystemExit(f"[LỖI] sink không hợp lệ: {spec}")


def play(a):
    cfg = {}
    if a.config:
        cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    g = lambda k, default: cfg.get(k, default) if getattr(a, k, None) is None else getattr(a, k)
    path = Path(g("input", str(SIM / "gps_simulated.csv")))
    speed = float(g("speed", 1.0))            # 1 = thời gian thực, 10 = nhanh gấp 10 lần, 0 = không chờ
    interval = g("interval", None)             # None = giữ nguyên tần suất của file
    trip, sink_spec = g("trip", None), g("sink", "stdout")
    limit, loops = g("limit", None), int(g("loop", 1))
    max_gap = float(g("max_gap_s", 30))        # bỏ qua khoảng nghỉ dài giữa các chuyến (giây dữ liệu)

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if trip:
        df = df[df["delivery_trip_id"] == trip]
    if df.empty:
        raise SystemExit("[LỖI] không có dòng nào để phát (kiểm tra --trip / --input)")
    if interval:
        interval = int(interval)
        if not 5 <= interval <= 10:
            raise SystemExit("[LỖI] --interval phải trong khoảng 5-10 giây")
        t0 = df.groupby("delivery_trip_id")["timestamp"].transform("min")
        off = (df["timestamp"] - t0).dt.total_seconds()
        df = df[off % interval == 0]
    df = df.sort_values(["timestamp", "delivery_trip_id", "seq"], kind="stable")
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    ts = pd.to_datetime(df["timestamp"])
    send, close = make_sink(sink_spec)
    sent = 0
    try:
        for _ in range(loops):
            prev = None
            for t, grp in df.groupby(ts, sort=True):
                if prev is not None and speed > 0:
                    time.sleep(min((t - prev).total_seconds(), max_gap) / speed)
                recs = json.loads(grp.to_json(orient="records", force_ascii=False))
                send(recs)
                sent += len(recs)
                prev = t
                if limit and sent >= int(limit):
                    return
    finally:
        close()
        print(f"[OK] đã phát {sent} bản ghi (speed={speed}, sink={sink_spec})", file=sys.stderr)



def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="tạo dataset GPS và các kịch bản")
    b.add_argument("--interval", type=int, default=5, help="tần suất ghi (giây), 5-10")
    b.add_argument("--osrm", action="store_true", help="gọi OSRM public để lấy geometry (cần internet)")
    p = sub.add_parser("play", help="phát GPS theo thời gian")
    p.add_argument("--input", help="file GPS CSV (mặc định gps_simulated.csv)")
    p.add_argument("--trip", help="chỉ phát một chuyến, ví dụ DT01")
    p.add_argument("--speed", type=float, help="hệ số tốc độ phát: 1 = thời gian thực, 0 = nhanh nhất")
    p.add_argument("--interval", type=int, help="lấy mẫu lại theo tần suất 5-10 giây")
    p.add_argument("--sink", help="stdout | file:out.jsonl | file:out.csv | http:URL")
    p.add_argument("--limit", type=int, help="dừng sau N bản ghi")
    p.add_argument("--loop", type=int, help="số lần lặp lại")
    p.add_argument("--max-gap-s", dest="max_gap_s", type=float, help="khoảng nghỉ tối đa giữa hai lần phát (giây dữ liệu)")
    p.add_argument("--config", help="file JSON cấu hình (tham số dòng lệnh ưu tiên hơn)")
    a = ap.parse_args()

    if a.cmd == "build":
        out = build(a.interval, a.osrm)
        write_outputs(out)
        s = out["stats"]
        print(f"[OK] geometry: osrm={s['osrm']} legs, synthetic={s['synthetic']} legs | "
              f"gps_simulated.csv: {len(out['main'])} dòng, 20 chuyến, mỗi {a.interval} giây")
    else:
        play(a)


if __name__ == "__main__":
    main()
