from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "processed"
SEVERE = ["Kẹt xe nặng", "Ùn tắc nghiêm trọng"]
LEVELS = {0: "thong_thoang", 1: "cham_nhe", 2: "ket_xe_nang", 3: "un_tac_nghiem_trong"}


def build_summary(obs: pd.DataFrame) -> pd.DataFrame:
    o = obs.copy()
    o["obs_time"] = pd.to_datetime(o["obs_time"])
    o["segment_id"] = o["segment_id"].fillna("")
    o["date"] = o["obs_time"].dt.date
    o["congested"] = o["status"].isin(SEVERE).astype(int)
    keys = ["observation_level", "route_id", "segment_id"]

    ff = o.groupby(keys)["speed_kmh"].quantile(0.9).rename("free_flow_kmh").reset_index()

    q = lambda p: (lambda s: s.quantile(p))
    frames = []
    weekend = o["day_of_week"] >= 5
    for day_type, sub in (("all", o), ("weekday", o[~weekend]), ("weekend", o[weekend])):
        agg = (sub.groupby(keys + ["hour", "time_slot", "is_simulated", "data_source"])
               .agg(n_obs=("speed_kmh", "size"), n_days=("date", "nunique"),
                    speed_mean=("speed_kmh", "mean"), speed_median=("speed_kmh", "median"),
                    speed_p10=("speed_kmh", q(0.1)), speed_p90=("speed_kmh", q(0.9)),
                    speed_std=("speed_kmh", "std"), congested_share=("congested", "mean"),
                    status_mode=("status", lambda x: x.mode().iat[0]))
               .reset_index())
        agg.insert(3, "day_type", day_type)
        frames.append(agg)
    s = pd.concat(frames, ignore_index=True).merge(ff, on=keys, how="left")
    s["congestion_index"] = (1 - s["speed_median"] / s["free_flow_kmh"]).clip(lower=0)
    s["low_sample"] = (s["n_obs"] < 5).astype(int)
    ci = s["congestion_index"]
    s["congestion_level_code"] = np.select([ci < 0.15, ci < 0.30, ci < 0.50], [0, 1, 2], default=3)
    s["congestion_level"] = s["congestion_level_code"].map(LEVELS)
    s = s.rename(columns={"observation_level": "scope"})
    num = ["speed_mean", "speed_median", "speed_p10", "speed_p90", "speed_std", "free_flow_kmh",
           "congestion_index", "congested_share"]
    s[num] = s[num].round(3)
    cols = ["scope", "route_id", "segment_id", "day_type", "hour", "time_slot", "n_obs", "n_days"] + num + \
           ["congestion_level_code", "congestion_level", "status_mode", "low_sample", "is_simulated", "data_source"]
    order = {"route": 0, "segment": 1}
    s["_o"] = s["scope"].map(order)
    s = s.sort_values(["_o", "route_id", "segment_id", "day_type", "hour"]).drop(columns="_o")
    return s[cols].reset_index(drop=True)


def review(obs, segs, trips, summary) -> dict:
    o = obs.copy()
    o["obs_time"] = pd.to_datetime(o["obs_time"])
    real = o[(o["is_simulated"] == 0) & (o["observation_level"] == "route")]
    sim = o[o["observation_level"] == "segment"]
    m = {}
    m["rows"], m["rows_real"], m["rows_sim"] = len(o), len(real), len(sim)
    m["dup_obs_id"] = int(o["obs_id"].duplicated().sum())
    m["null_speed"] = int(o["speed_kmh"].isna().sum())
    m["recomputed_rows"] = int(real["note"].fillna("").str.contains("recomputed").sum())
    dates = sorted(o["obs_time"].dt.date.unique())
    m["date_min"], m["date_max"], m["n_days"] = str(dates[0]), str(dates[-1]), len(dates)
    m["weekend_days"] = [str(d) for d in dates if pd.Timestamp(d).dayofweek >= 5]
    hours = sorted(o["hour"].unique())
    m["hours_present"] = [int(h) for h in hours]
    m["hours_missing"] = [h for h in range(24) if h not in hours]
    per_day = real.groupby(["route_id", real["obs_time"].dt.date])["hour"].nunique()
    m["hours_per_route_day"] = sorted(int(x) for x in per_day.unique())

    rs = summary[(summary["scope"] == "route") & (summary["day_type"] != "all")]
    m["cells_weekday"] = int((rs["day_type"] == "weekday").sum())
    m["cells_weekend"] = int((rs["day_type"] == "weekend").sum())
    m["n_obs_weekday_per_cell"] = int(rs[rs["day_type"] == "weekday"]["n_obs"].median())
    m["n_obs_weekend_per_cell"] = int(rs[rs["day_type"] == "weekend"]["n_obs"].median())
    m["low_sample_cells_weekend"] = int(rs[(rs["day_type"] == "weekend")]["low_sample"].sum())

    sp = real["speed_kmh"]
    q1, q3 = sp.quantile([0.25, 0.75])
    out = (sp < q1 - 1.5 * (q3 - q1)) | (sp > q3 + 1.5 * (q3 - q1))
    m["speed_min"], m["speed_max"] = float(sp.min()), float(sp.max())
    m["speed_iqr_outliers"] = int(out.sum())
    m["speed_sim_min"], m["speed_sim_max"] = float(sim["speed_kmh"].min()), float(sim["speed_kmh"].max())

    #tình trạng tắc nghẽn theo tuyến
    st = real.groupby(["route_id", "status"])["speed_kmh"].agg(["count", "median"]).round(1).reset_index()
    m["status_table"] = st.to_dict("records")
    weak = []
    for rid, g in real.groupby("route_id"):
        med = g.groupby("status")["speed_kmh"].median()
        sev = [s for s in SEVERE if s in med.index and (g["status"] == s).sum() >= 20]
        if "Chậm nhẹ" in med.index and sev:
            gap = (med["Chậm nhẹ"] - med[sev[0]]) / med["Chậm nhẹ"]
            if gap < 0.1:
                weak.append(dict(route_id=rid, status=sev[0], median_kmh=float(med[sev[0]]),
                                 slow_median_kmh=float(med["Chậm nhẹ"]), gap_pct=round(gap * 100, 1)))
    m["status_weak"] = weak
    m["status_labels_by_route"] = {r: sorted(g["status"].unique()) for r, g in real.groupby("route_id")}

    #đoạn đường có khớp tốc độ tuyến không
    mer = sim.merge(real[["route_id", "obs_time", "speed_kmh"]], on=["route_id", "obs_time"], suffixes=("", "_route"))
    corr = mer.groupby("segment_id").apply(lambda g: g["speed_kmh"].corr(g["speed_kmh_route"]))
    m["seg_route_corr_min"], m["seg_route_corr_max"] = round(float(corr.min()), 3), round(float(corr.max()), 3)

    #tọa độ tuyến có khớp với tọa độ đoạn đường không
    med_km = trips.groupby("route_id")["distance_km"].median()
    st_km = segs.groupby("route_id")["straight_km"].sum()
    m["geometry_check"] = [dict(route_id=r, route_km=float(med_km[r]), straight_km=round(float(st_km[r]), 2),
                                ratio=round(float(st_km[r] / med_km[r]), 2)) for r in med_km.index]
    m["geometry_suspect"] = [g["route_id"] for g in m["geometry_check"] if g["ratio"] < 0.55]
    return m


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    obs = pd.read_csv(PROCESSED / "traffic_observations.csv")
    summary = build_summary(obs)
    summary.to_csv(PROCESSED / "traffic_summary.csv", index=False, encoding="utf-8-sig")
    print(f"[OK] traffic_summary.csv: {len(summary)} dòng "
          f"({(summary.scope == 'route').sum()} mức tuyến, {(summary.scope == 'segment').sum()} mức đoạn)")


if __name__ == "__main__":
    main()
