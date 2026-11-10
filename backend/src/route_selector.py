"""route_selector.py - Chọn tuyến tối ưu từ danh sách tuyến ứng viên.

Quy tắc đã thống nhất:
  1. Mỗi tuyến có ETA do mô hình ML dự đoán (eta_ml). Nếu ETA ML thiếu hoặc
     không hợp lệ (None, NaN, âm, vô cực) thì dùng ETA của OSRM (eta_osrm).
  2. Chọn tuyến có ETA thấp nhất.
  3. ETA bằng nhau -> ưu tiên tuyến ngắn hơn (distance_m), sau đó theo route_id
     (để kết quả luôn xác định, không phụ thuộc thứ tự đầu vào).
  4. Tuyến không đi được (drivable=False) hoặc không có ETA nào dùng được bị loại.
  5. Không còn tuyến hợp lệ -> ném NoValidRouteError.

Fallback OSRM thật (select_route_with_fallback)
  - Chỉ gọi OSRM Route API cho tuyến thiếu cả eta_ml lẫn eta_osrm và có đủ
    origin, destination (lat, lon); tuyến đã có ETA không bao giờ bị gọi API.
  - Lỗi OSRM không bị che giấu: tuyến đó bị loại kèm lý do "OSRM lỗi: ..." và có
    cảnh báo trong kết quả.

Đơn vị: ETA tính bằng giây, khoảng cách tính bằng mét.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Tuple

from osrm_client import OsrmError

SOURCE_ML = "ml"
SOURCE_OSRM = "osrm"
_TIE_TOL = 1e-6

Coord = Tuple[float, float]


class NoValidRouteError(ValueError):
    """Không có tuyến nào hợp lệ để chọn."""


def _as_coord(value: Any) -> Optional[Coord]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (float(value[0]), float(value[1]))
    raise ValueError(f"Toạ độ phải là (lat, lon): {value!r}")


@dataclass(frozen=True)
class RouteCandidate:
    route_id: str
    eta_ml: Optional[float] = None
    eta_osrm: Optional[float] = None
    distance_m: Optional[float] = None
    drivable: bool = True
    origin: Optional[Coord] = None
    destination: Optional[Coord] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RouteCandidate":
        return cls(
            route_id=str(d["route_id"]),
            eta_ml=d.get("eta_ml"),
            eta_osrm=d.get("eta_osrm"),
            distance_m=d.get("distance_m"),
            drivable=bool(d.get("drivable", True)),
            origin=_as_coord(d.get("origin")),
            destination=_as_coord(d.get("destination")),
        )


@dataclass(frozen=True)
class RankedRoute:
    route_id: str
    eta_s: float
    source: str
    distance_m: Optional[float]


@dataclass
class SelectionResult:
    best: RankedRoute
    ranking: List[RankedRoute]
    excluded: List[Tuple[str, str]] = field(default_factory=list)
    tie_broken: bool = False
    warnings: List[str] = field(default_factory=list)


def _valid_number(x: Any) -> bool:
    if x is None or isinstance(x, bool):
        return False
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v) and v >= 0


def resolve_eta(c: RouteCandidate) -> Tuple[Optional[float], Optional[str]]:
    """Trả về (eta, nguồn). Ưu tiên ML, fallback OSRM, không có thì (None, None)."""
    if _valid_number(c.eta_ml):
        return float(c.eta_ml), SOURCE_ML
    if _valid_number(c.eta_osrm):
        return float(c.eta_osrm), SOURCE_OSRM
    return None, None


def needs_osrm_fallback(c: RouteCandidate) -> bool:
    return c.drivable and resolve_eta(c)[0] is None


def select_route(candidates: Iterable[RouteCandidate],
                 failure_reasons: Optional[Dict[str, str]] = None) -> SelectionResult:
    cands = list(candidates)
    if not cands:
        raise NoValidRouteError("Danh sách tuyến ứng viên rỗng")
    failure_reasons = failure_reasons or {}

    ranked: List[RankedRoute] = []
    excluded: List[Tuple[str, str]] = []
    seen = set()
    for c in cands:
        if c.route_id in seen:
            excluded.append((c.route_id, "route_id trùng lặp"))
            continue
        seen.add(c.route_id)
        if not c.drivable:
            excluded.append((c.route_id, "đường không đi được"))
            continue
        eta, src = resolve_eta(c)
        if eta is None:
            reason = "thiếu ETA (cả ML lẫn OSRM)"
            if c.route_id in failure_reasons:
                reason += f"; {failure_reasons[c.route_id]}"
            excluded.append((c.route_id, reason))
            continue
        dist = float(c.distance_m) if _valid_number(c.distance_m) else None
        ranked.append(RankedRoute(c.route_id, eta, src, dist))

    if not ranked:
        reasons = "; ".join(f"{rid}: {why}" for rid, why in excluded)
        raise NoValidRouteError(f"Không có tuyến hợp lệ ({reasons})")

    ranked.sort(key=lambda r: (r.eta_s,
                               r.distance_m if r.distance_m is not None else math.inf,
                               r.route_id))
    best = ranked[0]
    tie = any(abs(r.eta_s - best.eta_s) <= _TIE_TOL for r in ranked[1:])

    warnings: List[str] = []
    if len({r.source for r in ranked}) > 1:
        warnings.append("Các tuyến dùng ETA từ nguồn khác nhau (ML và OSRM); "
                        "ETA OSRM không tính tắc đường nên có thể thấp hơn thực tế.")
    if best.source == SOURCE_OSRM:
        warnings.append(f"Tuyến {best.route_id} được chọn bằng ETA fallback OSRM.")
    if tie:
        warnings.append("ETA bằng nhau, đã phân định theo khoảng cách ngắn hơn rồi route_id.")

    return SelectionResult(best=best, ranking=ranked, excluded=excluded,
                           tie_broken=tie, warnings=warnings)


def fill_osrm_fallback(candidates: Iterable[RouteCandidate],
                       osrm: Any) -> Tuple[List[RouteCandidate], Dict[str, str]]:
    """Gọi osrm.route(origin, destination) cho đúng các tuyến thiếu ETA.

    Trả về (danh sách tuyến đã điền eta_osrm, {route_id: lý do lỗi OSRM}).
    """
    filled: List[RouteCandidate] = []
    failures: Dict[str, str] = {}
    called = set()
    for c in candidates:
        if (not needs_osrm_fallback(c) or c.origin is None or c.destination is None
                or c.route_id in called):
            filled.append(c)
            continue
        called.add(c.route_id)
        try:
            result = osrm.route(c.origin, c.destination)
        except OsrmError as exc:
            failures[c.route_id] = f"OSRM lỗi: {exc}"
            filled.append(c)
            continue
        distance = c.distance_m if _valid_number(c.distance_m) else result.distance_m
        filled.append(replace(c, eta_osrm=result.duration_s, distance_m=distance))
    return filled, failures


def select_route_with_fallback(candidates: Iterable[RouteCandidate],
                               osrm: Any = None) -> SelectionResult:
    cands = list(candidates)
    if osrm is None:
        return select_route(cands)
    filled, failures = fill_osrm_fallback(cands, osrm)
    result = select_route(filled, failure_reasons=failures)
    if failures:
        result.warnings.append("Gọi OSRM thất bại cho: " + ", ".join(sorted(failures))
                               + "; các tuyến này bị loại.")
    return result


if __name__ == "__main__":
    demo = [
        RouteCandidate("R1", eta_ml=1500, eta_osrm=1200, distance_m=9000),
        RouteCandidate("R2", eta_ml=None, eta_osrm=1400, distance_m=8000),
        RouteCandidate("R3", eta_ml=1300, distance_m=11000),
        RouteCandidate("R4", eta_ml=900, drivable=False),
    ]
    res = select_route(demo)
    print("Tuyến được chọn:", res.best)
    for r in res.ranking:
        print("  ", r)
    print("Bị loại:", res.excluded)
    print("Cảnh báo:", res.warnings)
