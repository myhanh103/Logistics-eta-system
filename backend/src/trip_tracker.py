"""trip_tracker.py - Theo dõi tiến độ chuyến giao hàng và tính lại ETA các điểm còn lại.

Trạng thái chuyến: vị trí nút hiện tại của xe (current_node), thời điểm xe sẵn sàng rời
nút đó (ready_s, đã gồm mọi độ trễ ghi nhận) và thứ tự các đơn chưa giao.

Sự kiện
  complete_stop    xe giao xong một điểm: nút hiện tại đổi sang điểm đó, ready_s = giờ giao xong,
                   ETA các điểm còn lại được tính lại từ nút này.
  apply_delay      ghi nhận thời gian mất thêm (hỏng xe, kẹt xe): cộng vào ready_s.
  report_new_eta   ETA mới cho điểm đang tới (điểm đầu tiên còn lại): ready_s được dịch
                   tương ứng, các điểm sau được tính lại.
  update_time_matrix  thay ma trận thời gian (ví dụ lấy lại từ OSRM).
  submit_gps       nhận toạ độ GPS, kiểm tra hợp lệ rồi tính độ lệch tuyến.
  check            phân loại rủi ro, xét điều kiện tính lại và gọi replan khi được phép.

Độ lệch tuyến là khoảng cách từ GPS đến đoạn thẳng nối nút hiện tại với điểm đang tới,
tính xấp xỉ phẳng (111000 m mỗi độ); đây không phải khớp bản đồ theo mạng đường.
Vị trí giữa hai nút không có ma trận thời gian riêng nên ETA luôn tính từ nút hiện tại tại
ready_s; độ trễ trên đường được phản ánh qua apply_delay hoặc report_new_eta.
GpsConfig (max_age_s, max_accuracy_m) là tham số bắt buộc, chưa có giá trị mặc định được duyệt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple

from delay_risk_detector import (AlertConfig, OrderAssessment, OrderProgress, ReoptConfig,
                                 ReoptDecision, assess, decide_reoptimization)
from multistop_optimizer import (CostConfig, DEPOT, OptimizerInputError, Plan, ReplanResult,
                                 Stop, evaluate_order, replan)

METERS_PER_DEGREE = 111000.0


class TrackerError(ValueError):
    """Sự kiện hoặc dữ liệu không hợp lệ đối với chuyến đang theo dõi."""


def _nonneg(x: Any) -> bool:
    if x is None or isinstance(x, bool) or not isinstance(x, (int, float)):
        return False
    return math.isfinite(x) and x >= 0


@dataclass(frozen=True)
class GpsConfig:
    max_age_s: float
    max_accuracy_m: float

    def __post_init__(self):
        if not _nonneg(self.max_age_s) or not _nonneg(self.max_accuracy_m):
            raise TrackerError("max_age_s và max_accuracy_m phải là số hữu hạn không âm")


@dataclass(frozen=True)
class GpsFix:
    lat: float
    lon: float
    timestamp_s: float
    accuracy_m: Optional[float] = None


def validate_fix(fix: GpsFix, now_s: float, cfg: GpsConfig) -> Tuple[bool, str]:
    for v in (fix.lat, fix.lon, fix.timestamp_s):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            return False, "toạ độ hoặc thời điểm không phải số hữu hạn"
    if not (-90.0 <= fix.lat <= 90.0) or not (-180.0 <= fix.lon <= 180.0):
        return False, "toạ độ ngoài phạm vi"
    if fix.timestamp_s > now_s + 1e-9:
        return False, "thời điểm GPS nằm ở tương lai"
    if now_s - fix.timestamp_s > cfg.max_age_s:
        return False, f"GPS cũ {now_s - fix.timestamp_s:.0f}s > {cfg.max_age_s:g}s"
    if fix.accuracy_m is not None:
        if not _nonneg(fix.accuracy_m):
            return False, "độ chính xác GPS không hợp lệ"
        if fix.accuracy_m > cfg.max_accuracy_m:
            return False, f"độ chính xác GPS {fix.accuracy_m:g}m > {cfg.max_accuracy_m:g}m"
    return True, "ok"


def distance_to_segment_m(p: Tuple[float, float], a: Tuple[float, float],
                          b: Tuple[float, float]) -> float:
    k = math.cos(math.radians((a[0] + b[0]) / 2.0))

    def xy(c):
        return (c[1] * k * METERS_PER_DEGREE, c[0] * METERS_PER_DEGREE)

    px, py = xy(p)
    ax, ay = xy(a)
    bx, by = xy(b)
    dx, dy = bx - ax, by - ay
    seg = dx * dx + dy * dy
    t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


@dataclass
class TrackerCheck:
    assessments: List[OrderAssessment]
    decision: ReoptDecision
    replan: Optional[ReplanResult]
    adopted: bool


class TripTracker:
    def __init__(self, time_matrix, stops: Sequence[Stop], cost: CostConfig,
                 alert_cfg: AlertConfig, reopt_cfg: ReoptConfig, gps_cfg: GpsConfig,
                 distance_matrix=None, node_coords: Optional[Sequence[Tuple[float, float]]] = None,
                 initial_order: Optional[Sequence[str]] = None, start_s: float = 0.0):
        stops = list(stops)
        ids = [s.order_id for s in stops]
        if len(set(ids)) != len(ids):
            raise TrackerError("order_id trùng lặp")
        order = list(initial_order) if initial_order is not None else ids
        if sorted(order) != sorted(ids):
            raise TrackerError("initial_order phải gồm đúng các order_id của stops")
        if not _nonneg(start_s):
            raise TrackerError("start_s không hợp lệ")
        if node_coords is not None and len(node_coords) != len(time_matrix):
            raise TrackerError("node_coords phải cùng kích thước với time_matrix")
        for s in stops:
            if not (isinstance(s.node, int) and 0 < s.node < len(time_matrix)):
                raise TrackerError(f"node của đơn {s.order_id} không hợp lệ")
        self.time_matrix = time_matrix
        self.distance_matrix = distance_matrix
        self.node_coords = node_coords
        self.cost, self.alert_cfg = cost, alert_cfg
        self.reopt_cfg, self.gps_cfg = reopt_cfg, gps_cfg
        self._stops = {s.order_id: s for s in stops}
        self.order: List[str] = order
        self.delivered = {}
        self.current_node = DEPOT
        self.ready_s = float(start_s)
        self.last_reopt_s: Optional[float] = None
        self.position_ok = True
        self.off_route_m: Optional[float] = None
        self.last_gps_reason = "chưa có GPS"
        self.reopt_count = 0

    def remaining_stops(self) -> List[Stop]:
        return [self._stops[i] for i in self.order]

    def plan(self) -> Optional[Plan]:
        if not self.order:
            return None
        return evaluate_order(self.remaining_stops(), self.time_matrix, self.distance_matrix,
                              False, self.ready_s, self.cost.risk_margin, self.current_node)

    def progress(self) -> List[OrderProgress]:
        plan = self.plan()
        eta = {s.order_id: s.complete_s for s in plan.stops} if plan else {}
        out = [OrderProgress(i, self._stops[i].deadline_s, eta.get(i)) for i in self.order]
        out += [OrderProgress(i, self._stops[i].deadline_s, None, True, t)
                for i, t in self.delivered.items()]
        return out

    def assess(self) -> List[OrderAssessment]:
        return assess(self.progress(), self.alert_cfg)

    def complete_stop(self, order_id: str, complete_s: float) -> None:
        if order_id in self.delivered:
            raise TrackerError(f"đơn {order_id} đã giao xong trước đó")
        if order_id not in self.order:
            raise TrackerError(f"đơn {order_id} không có trong chuyến")
        if not _nonneg(complete_s) or complete_s < self.ready_s - 1e-9:
            raise TrackerError("complete_s không hợp lệ hoặc sớm hơn thời điểm xe sẵn sàng")
        self.order.remove(order_id)
        self.delivered[order_id] = float(complete_s)
        self.current_node = self._stops[order_id].node
        self.ready_s = float(complete_s)
        self.off_route_m = None

    def apply_delay(self, delay_s: float) -> None:
        if not _nonneg(delay_s):
            raise TrackerError("delay_s phải là số hữu hạn không âm")
        self.ready_s += float(delay_s)

    def report_new_eta(self, order_id: str, eta_s: float) -> None:
        if not self.order or order_id != self.order[0]:
            raise TrackerError("ETA mới chỉ áp dụng cho điểm đang tới")
        if not _nonneg(eta_s):
            raise TrackerError("eta_s không hợp lệ")
        plan = self.plan()
        if plan is None:
            raise TrackerError("không tính được ETA hiện tại để so sánh")
        shifted = self.ready_s + (float(eta_s) - plan.stops[0].complete_s)
        if shifted < 0:
            raise TrackerError("ETA mới dẫn tới thời điểm xuất phát âm")
        self.ready_s = shifted

    def update_time_matrix(self, time_matrix, distance_matrix=None) -> None:
        if len(time_matrix) != len(self.time_matrix):
            raise TrackerError("ma trận mới phải cùng kích thước")
        self.time_matrix = time_matrix
        if distance_matrix is not None:
            self.distance_matrix = distance_matrix

    def submit_gps(self, fix: GpsFix, now_s: float) -> Tuple[bool, str]:
        ok, reason = validate_fix(fix, now_s, self.gps_cfg)
        self.position_ok, self.last_gps_reason = ok, reason
        if not ok:
            self.off_route_m = None
            return ok, reason
        if self.node_coords is None or not self.order:
            self.off_route_m = None
            return ok, "hợp lệ nhưng không có toạ độ nút hoặc không còn điểm tới"
        a = self.node_coords[self.current_node]
        b = self.node_coords[self._stops[self.order[0]].node]
        self.off_route_m = distance_to_segment_m((fix.lat, fix.lon), a, b)
        return ok, reason

    def check(self, now_s: float) -> TrackerCheck:
        assessments = self.assess()
        feasible = self.plan() is not None or not self.order
        decision = decide_reoptimization(assessments, len(self.order), self.reopt_cfg, now_s,
                                         self.last_reopt_s, self.off_route_m,
                                         self.position_ok, feasible)
        if not decision.allowed:
            return TrackerCheck(assessments, decision, None, False)
        return self._do_replan(now_s, decision, assessments)

    def force_replan(self, now_s: float) -> TrackerCheck:
        assessments = self.assess()
        decision = ReoptDecision(True, ["forced"], [], ["bỏ qua điều kiện kích hoạt"])
        if len(self.order) - (1 if self.reopt_cfg.lock_next else 0) < 2:
            decision = ReoptDecision(False, ["forced"], ["không đủ điểm để đảo"], [])
            return TrackerCheck(assessments, decision, None, False)
        return self._do_replan(now_s, decision, assessments)

    def _do_replan(self, now_s: float, decision: ReoptDecision,
                   assessments: List[OrderAssessment]) -> TrackerCheck:
        locked = self.order[0] if self.reopt_cfg.lock_next else None
        res = replan(self.time_matrix, self.remaining_stops(), self.order, self.cost,
                     self.distance_matrix, now_s=self.ready_s, delay_s=0.0,
                     max_stops=self.reopt_cfg.max_stops, start_node=self.current_node,
                     locked_first=locked)
        self.last_reopt_s = float(now_s)
        self.reopt_count += 1
        if res.adopted:
            self.order = list(res.chosen.sequence)
        return TrackerCheck(assessments, decision, res, res.adopted)
