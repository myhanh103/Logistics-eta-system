"""delay_risk_detector.py - Phát hiện rủi ro trễ hạn và điều kiện cho phép tính lại thứ tự.

Phân loại từng đơn bằng cách so ETA cập nhật với hạn giao gốc (giờ tuyệt đối, cùng gốc
thời gian với ETA). ETA ở đây là thời điểm giao xong (đến nơi + thời gian dừng).

Trạng thái
  delivered   đã giao xong, không còn cảnh báo.
  no_deadline không có hạn giao: không thể trễ, chỉ ghi nhận (cảnh báo mức info).
  eta_unknown thiếu hoặc không hợp lệ ETA: không kết luận được (cảnh báo mức warning).
  late        ETA > hạn giao (cảnh báo critical).
  at_risk     chưa trễ nhưng còn dư địa slack = hạn - ETA < at_risk_buffer_s (warning).
  on_time     còn dư địa >= at_risk_buffer_s.
  ETA đúng bằng hạn giao không phải trễ; nó là at_risk khi at_risk_buffer_s > 0.

Điều kiện cho phép tính lại thứ tự (decide_reoptimization)
  Kích hoạt (cần ít nhất một):
    late        có đơn chưa giao ở trạng thái late.
    at_risk     có đơn at_risk và trigger_on_at_risk = True.
    off_route   độ lệch tuyến > off_route_m (chỉ khi vị trí GPS tin cậy).
    blocked     thứ tự hiện tại có đoạn đường không đi được.
  Chặn (có một là không cho phép):
    số đơn còn lại vượt max_stops của bộ tối ưu;
    số điểm được phép đảo (sau khi trừ điểm đầu nếu lock_next) nhỏ hơn 2;
    chưa đủ min_interval_s kể từ lần tính lại trước (trừ trường hợp blocked).
  Cổng thứ hai nằm ở multistop_optimizer.replan: chỉ đổi thứ tự khi chi phí giảm hơn
  min_improvement.

at_risk_buffer_s, off_route_m, min_interval_s, trigger_on_at_risk và lock_next đều là
tham số bắt buộc; chưa có giá trị mặc định được duyệt.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence

from multistop_optimizer import MAX_STOPS

STATUS_DELIVERED = "delivered"
STATUS_NO_DEADLINE = "no_deadline"
STATUS_ETA_UNKNOWN = "eta_unknown"
STATUS_LATE = "late"
STATUS_AT_RISK = "at_risk"
STATUS_ON_TIME = "on_time"

ALERT_CRITICAL = "critical"
ALERT_WARNING = "warning"
ALERT_INFO = "info"
ALERT_NONE = "none"

TRIGGER_LATE = "late"
TRIGGER_AT_RISK = "at_risk"
TRIGGER_OFF_ROUTE = "off_route"
TRIGGER_BLOCKED = "blocked"

_EPS = 1e-9
_ALERT_RANK = {ALERT_CRITICAL: 3, ALERT_WARNING: 2, ALERT_INFO: 1, ALERT_NONE: 0}
_STATUS_ORDER = {STATUS_LATE: 0, STATUS_AT_RISK: 1, STATUS_ETA_UNKNOWN: 2,
                 STATUS_ON_TIME: 3, STATUS_NO_DEADLINE: 4, STATUS_DELIVERED: 5}


class DelayRiskInputError(ValueError):
    """Dữ liệu hoặc cấu hình đầu vào không hợp lệ."""


def _finite_nonneg(x: Any) -> bool:
    if x is None or isinstance(x, bool) or not isinstance(x, (int, float)):
        return False
    return math.isfinite(x) and x >= 0


@dataclass(frozen=True)
class AlertConfig:
    at_risk_buffer_s: float

    def __post_init__(self):
        if not _finite_nonneg(self.at_risk_buffer_s):
            raise DelayRiskInputError("at_risk_buffer_s phải là số hữu hạn không âm")


@dataclass(frozen=True)
class ReoptConfig:
    trigger_on_at_risk: bool
    off_route_m: float
    min_interval_s: float
    lock_next: bool
    max_stops: int = MAX_STOPS

    def __post_init__(self):
        if not isinstance(self.trigger_on_at_risk, bool) or not isinstance(self.lock_next, bool):
            raise DelayRiskInputError("trigger_on_at_risk và lock_next phải là bool")
        for name in ("off_route_m", "min_interval_s"):
            if not _finite_nonneg(getattr(self, name)):
                raise DelayRiskInputError(f"{name} phải là số hữu hạn không âm")
        if isinstance(self.max_stops, bool) or not isinstance(self.max_stops, int) \
                or self.max_stops < 1:
            raise DelayRiskInputError("max_stops phải là số nguyên >= 1")


@dataclass(frozen=True)
class OrderProgress:
    order_id: str
    deadline_s: Optional[float] = None
    eta_s: Optional[float] = None
    delivered: bool = False
    delivered_s: Optional[float] = None


@dataclass
class OrderAssessment:
    order_id: str
    status: str
    alert: str
    deadline_s: Optional[float]
    eta_s: Optional[float]
    slack_s: Optional[float]
    lateness_s: float
    message: str


@dataclass
class ReoptDecision:
    allowed: bool
    triggers: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        if self.allowed:
            return "Cho phép tính lại: " + ", ".join(self.triggers)
        if self.blockers:
            return "Không tính lại: " + "; ".join(self.blockers)
        return "Không tính lại: chưa có điều kiện kích hoạt"


def classify(p: OrderProgress, cfg: AlertConfig) -> OrderAssessment:
    if not isinstance(cfg, AlertConfig):
        raise DelayRiskInputError("cfg phải là AlertConfig")
    oid = p.order_id
    if p.deadline_s is not None and not _finite_nonneg(p.deadline_s):
        raise DelayRiskInputError(f"Hạn giao không hợp lệ của đơn {oid}: {p.deadline_s!r}")
    deadline = None if p.deadline_s is None else float(p.deadline_s)

    if p.delivered:
        done = p.delivered_s
        lateness = 0.0
        note = "đã giao xong"
        if deadline is not None and _finite_nonneg(done) and done > deadline + _EPS:
            lateness = float(done) - deadline
            note = f"đã giao xong, trễ {lateness:.0f}s"
        return OrderAssessment(oid, STATUS_DELIVERED, ALERT_NONE, deadline, None, None,
                               lateness, note)

    if deadline is None:
        return OrderAssessment(oid, STATUS_NO_DEADLINE, ALERT_INFO, None,
                               float(p.eta_s) if _finite_nonneg(p.eta_s) else None, None, 0.0,
                               "không có hạn giao, không đánh giá trễ")

    if not _finite_nonneg(p.eta_s):
        return OrderAssessment(oid, STATUS_ETA_UNKNOWN, ALERT_WARNING, deadline, None, None,
                               0.0, "thiếu hoặc ETA không hợp lệ")

    eta = float(p.eta_s)
    slack = deadline - eta
    if eta > deadline + _EPS:
        return OrderAssessment(oid, STATUS_LATE, ALERT_CRITICAL, deadline, eta, slack,
                               eta - deadline, f"dự kiến trễ {eta - deadline:.0f}s")
    if slack < cfg.at_risk_buffer_s - _EPS:
        return OrderAssessment(oid, STATUS_AT_RISK, ALERT_WARNING, deadline, eta, slack, 0.0,
                               f"còn dư {slack:.0f}s < ngưỡng {cfg.at_risk_buffer_s:g}s")
    return OrderAssessment(oid, STATUS_ON_TIME, ALERT_NONE, deadline, eta, slack, 0.0,
                           f"còn dư {slack:.0f}s")


def assess(orders: Sequence[OrderProgress], cfg: AlertConfig) -> List[OrderAssessment]:
    """Phân loại mọi đơn; kết quả xếp theo mức khẩn cấp, hoà thì theo hạn rồi order_id."""
    seen = set()
    for o in orders:
        if o.order_id in seen:
            raise DelayRiskInputError(f"order_id trùng lặp: {o.order_id}")
        seen.add(o.order_id)
    results = [classify(o, cfg) for o in orders]
    results.sort(key=lambda a: (
        _STATUS_ORDER[a.status],
        -a.lateness_s if a.status == STATUS_LATE else 0.0,
        a.slack_s if a.slack_s is not None else math.inf,
        a.deadline_s if a.deadline_s is not None else math.inf,
        a.order_id))
    return results


def worst_alert(assessments: Sequence[OrderAssessment]) -> str:
    return max((a.alert for a in assessments), key=lambda x: _ALERT_RANK[x], default=ALERT_NONE)


def count_by_status(assessments: Sequence[OrderAssessment]) -> dict:
    out: dict = {}
    for a in assessments:
        out[a.status] = out.get(a.status, 0) + 1
    return out


def decide_reoptimization(assessments: Sequence[OrderAssessment], remaining: int,
                          cfg: ReoptConfig, now_s: float,
                          last_reopt_s: Optional[float] = None,
                          off_route_m: Optional[float] = None,
                          position_ok: bool = True,
                          plan_feasible: bool = True) -> ReoptDecision:
    if not isinstance(cfg, ReoptConfig):
        raise DelayRiskInputError("cfg phải là ReoptConfig")
    if not _finite_nonneg(now_s):
        raise DelayRiskInputError("now_s phải là số hữu hạn không âm")
    if last_reopt_s is not None and not _finite_nonneg(last_reopt_s):
        raise DelayRiskInputError("last_reopt_s không hợp lệ")
    if isinstance(remaining, bool) or not isinstance(remaining, int) or remaining < 0:
        raise DelayRiskInputError("remaining phải là số nguyên không âm")

    d = ReoptDecision(allowed=False)
    live = [a for a in assessments if a.status != STATUS_DELIVERED]
    if any(a.status == STATUS_LATE for a in live):
        d.triggers.append(TRIGGER_LATE)
    if cfg.trigger_on_at_risk and any(a.status == STATUS_AT_RISK for a in live):
        d.triggers.append(TRIGGER_AT_RISK)
    if off_route_m is not None:
        if not position_ok:
            d.notes.append("vị trí GPS không tin cậy, bỏ qua điều kiện lệch tuyến")
        elif not _finite_nonneg(off_route_m):
            raise DelayRiskInputError("off_route_m không hợp lệ")
        elif off_route_m > cfg.off_route_m + _EPS:
            d.triggers.append(TRIGGER_OFF_ROUTE)
    if not plan_feasible:
        d.triggers.append(TRIGGER_BLOCKED)

    if not d.triggers:
        return d

    if remaining > cfg.max_stops:
        d.blockers.append(f"còn {remaining} đơn, vượt giới hạn {cfg.max_stops}")
    free = remaining - (1 if cfg.lock_next else 0)
    if free < 2:
        d.blockers.append(f"chỉ còn {max(free, 0)} điểm có thể đảo, cần ít nhất 2")
    if TRIGGER_BLOCKED not in d.triggers and last_reopt_s is not None \
            and now_s - last_reopt_s < cfg.min_interval_s - _EPS:
        d.blockers.append(
            f"mới tính lại {now_s - last_reopt_s:.0f}s trước, cần >= {cfg.min_interval_s:g}s")
    d.allowed = not d.blockers
    return d
