"""reopt_experiment.py - Thử nghiệm quy mô nhỏ về quy tắc tính lại thứ tự (re-optimization).

DỮ LIỆU TỔNG HỢP: toạ độ, hạn giao, hệ số tắc đường và sự cố đều do bộ sinh ngẫu nhiên
(random.Random với seed) tạo ra, không phải dữ liệu giao hàng thực tế. Kết quả chỉ so sánh
các chính sách trong cùng kịch bản mô phỏng, không khẳng định hiệu quả ngoài đời.

Mỗi kịch bản: 1 kho, 5 điểm giao, ma trận thời gian Manhattan (10 m/s, 111000 m mỗi độ).
Kế hoạch ban đầu có từ tối ưu hoá soft_cost. Khi thực thi, thời gian đi thực = thời gian
kế hoạch x hệ số ngẫu nhiên của từng cặp nút; tại mỗi điểm quyết định, có xác suất xảy
ra sự cố làm mất thêm thời gian (được báo ngay cho bộ theo dõi qua apply_delay).

Ba chính sách chạy trên CÙNG kịch bản:
  static   giữ thứ tự ban đầu, không tính lại.
  always   tính lại ở mọi điểm quyết định (bỏ qua điều kiện kích hoạt).
  gated    chỉ tính lại khi detector cho phép (TripTracker.check).

Mọi tham số (trọng số chi phí, ngưỡng cảnh báo, ngưỡng tính lại, xác suất sự cố, ...) là giá trị
MINH HOẠ, CHƯA ĐƯỢC DUYỆT, và đều nhận qua tham số dòng lệnh hoặc hằng số ExperimentConfig.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass
from typing import Dict, List

from delay_risk_detector import AlertConfig, ReoptConfig
from multistop_optimizer import CostConfig, Stop, evaluate_order, optimize
from trip_tracker import GpsConfig, TripTracker

POLICIES = ("static", "always", "gated")
SPEED_MPS = 10.0
METERS_PER_DEGREE = 111000.0


@dataclass(frozen=True)
class ExperimentConfig:
    trials: int
    seed: int
    n_stops: int
    deadline_slack_low: float
    deadline_slack_high: float
    factor_low: float
    factor_high: float
    incident_prob: float
    incident_low_s: float
    incident_high_s: float
    late_weight: float
    time_weight: float
    min_improvement: float
    at_risk_buffer_s: float
    min_interval_s: float
    lock_next: bool


ILLUSTRATIVE = ExperimentConfig(
    trials=200, seed=20261110, n_stops=5, deadline_slack_low=1.0, deadline_slack_high=1.4,
    factor_low=0.8, factor_high=1.6, incident_prob=0.3, incident_low_s=300.0,
    incident_high_s=900.0, late_weight=3.0, time_weight=1.0, min_improvement=30.0,
    at_risk_buffer_s=120.0, min_interval_s=0.0, lock_next=True)


def _scenario(cfg: ExperimentConfig, rng: random.Random) -> Dict:
    n = cfg.n_stops
    pts = [(10.0 + rng.uniform(0, 0.05), 106.0 + rng.uniform(0, 0.05)) for _ in range(n + 1)]
    size = n + 1
    base = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i != j:
                meters = (abs(pts[i][0] - pts[j][0]) + abs(pts[i][1] - pts[j][1])) \
                    * METERS_PER_DEGREE
                base[i][j] = meters / SPEED_MPS
    service = [rng.uniform(60.0, 180.0) for _ in range(n)]
    factors = [[rng.uniform(cfg.factor_low, cfg.factor_high) for _ in range(size)]
               for _ in range(size)]
    incidents = [rng.uniform(cfg.incident_low_s, cfg.incident_high_s)
                 if rng.random() < cfg.incident_prob else 0.0 for _ in range(n)]
    slack = [rng.uniform(cfg.deadline_slack_low, cfg.deadline_slack_high) for _ in range(n)]
    return dict(pts=pts, base=base, service=service, factors=factors,
                incidents=incidents, slack=slack)


def _build_stops(cfg: ExperimentConfig, sc: Dict) -> List[Stop]:
    probe = [Stop(f"O{i + 1}", i + 1, sc["service"][i], None) for i in range(cfg.n_stops)]
    plan = evaluate_order(probe, sc["base"])
    eta = {s.order_id: s.complete_s for s in plan.stops}
    return [Stop(s.order_id, s.node, s.service_s, eta[s.order_id] * sc["slack"][k])
            for k, s in enumerate(probe)]


def run_policy(policy: str, cfg: ExperimentConfig, sc: Dict, stops: List[Stop]) -> Dict:
    cost = CostConfig(cfg.late_weight, cfg.time_weight, 0.0, cfg.min_improvement)
    first = optimize(sc["base"], stops, cost=cost)
    reopt = ReoptConfig(trigger_on_at_risk=True, off_route_m=1e12,
                        min_interval_s=cfg.min_interval_s, lock_next=cfg.lock_next)
    tracker = TripTracker(sc["base"], stops, cost, AlertConfig(cfg.at_risk_buffer_s), reopt,
                          GpsConfig(30.0, 50.0), initial_order=first.optimal.sequence)
    by_id = {s.order_id: s for s in stops}
    now = 0.0
    step = 0
    while tracker.order:
        incident = sc["incidents"][step]
        if incident > 0:
            tracker.apply_delay(incident)
            now += incident
        if policy == "always":
            tracker.force_replan(now)
        elif policy == "gated":
            tracker.check(now)
        nxt = by_id[tracker.order[0]]
        travel = sc["base"][tracker.current_node][nxt.node] \
            * sc["factors"][tracker.current_node][nxt.node]
        now += travel + nxt.service_s
        tracker.complete_stop(nxt.order_id, max(now, tracker.ready_s))
        step += 1
    late = 0
    lateness = 0.0
    for oid, t in tracker.delivered.items():
        d = by_id[oid].deadline_s
        if t > d + 1e-9:
            late += 1
            lateness += t - d
    return dict(late=late, lateness_s=lateness, finish_s=max(tracker.delivered.values()),
                replans=tracker.reopt_count)


def run_experiment(cfg: ExperimentConfig) -> Dict:
    rng = random.Random(cfg.seed)
    totals = {p: dict(late=0, lateness_s=0.0, finish_s=0.0, replans=0, trips_with_late=0)
              for p in POLICIES}
    per_trial = []
    for _ in range(cfg.trials):
        sc = _scenario(cfg, rng)
        stops = _build_stops(cfg, sc)
        row = {}
        for p in POLICIES:
            r = run_policy(p, cfg, sc, stops)
            row[p] = r
            for k in ("late", "lateness_s", "finish_s", "replans"):
                totals[p][k] += r[k]
            totals[p]["trips_with_late"] += 1 if r["late"] else 0
        per_trial.append(row)
    summary = {}
    for p in POLICIES:
        t = totals[p]
        summary[p] = dict(
            late_orders=t["late"], total_lateness_s=round(t["lateness_s"], 1),
            mean_finish_s=round(t["finish_s"] / cfg.trials, 1), replans=t["replans"],
            trips_with_late=t["trips_with_late"])
    better = sum(1 for r in per_trial if r["gated"]["lateness_s"] < r["static"]["lateness_s"] - 1e-9)
    worse = sum(1 for r in per_trial if r["gated"]["lateness_s"] > r["static"]["lateness_s"] + 1e-9)
    return dict(data="TỔNG HỢP (mô phỏng), không phải dữ liệu giao hàng thực tế",
                parameters="MINH HOẠ, CHƯA ĐƯỢC DUYỆT", config=asdict(cfg), summary=summary,
                gated_vs_static=dict(better=better, worse=worse,
                                     equal=cfg.trials - better - worse))


def format_summary(res: Dict) -> str:
    lines = [f"Dữ liệu: {res['data']}", f"Tham số: {res['parameters']}",
             f"Số kịch bản: {res['config']['trials']}, seed: {res['config']['seed']}", ""]
    lines.append(f"{'policy':8} {'đơn trễ':>8} {'tổng trễ (s)':>13} {'chuyến có trễ':>14} "
                 f"{'hoàn tất TB (s)':>16} {'số lần tính lại':>16}")
    for p in POLICIES:
        s = res["summary"][p]
        lines.append(f"{p:8} {s['late_orders']:>8} {s['total_lateness_s']:>13} "
                     f"{s['trips_with_late']:>14} {s['mean_finish_s']:>16} {s['replans']:>16}")
    g = res["gated_vs_static"]
    lines.append("")
    lines.append(f"gated so với static theo tổng thời gian trễ từng chuyến: "
                 f"tốt hơn {g['better']}, kém hơn {g['worse']}, bằng nhau {g['equal']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Thử nghiệm re-optimization (dữ liệu tổng hợp)")
    ap.add_argument("--trials", type=int, default=ILLUSTRATIVE.trials)
    ap.add_argument("--seed", type=int, default=ILLUSTRATIVE.seed)
    ap.add_argument("--out", help="ghi kết quả JSON")
    args = ap.parse_args(argv)
    cfg = ExperimentConfig(**{**asdict(ILLUSTRATIVE), "trials": args.trials, "seed": args.seed})
    res = run_experiment(cfg)
    print(format_summary(res))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
