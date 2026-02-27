from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

SIGNAL_EPS = 1e-9


class CalibrationPointLike(Protocol):
    known_weight_lbs: float
    signal: float


@dataclass(frozen=True)
class CalibrationModel:
    method: str
    slope_lbs_per_mv: Optional[float]
    intercept_lbs: Optional[float]
    active_points_count: int
    total_points_count: int
    last_calibration_utc: Optional[str]


def _point_id(point: CalibrationPointLike) -> int:
    try:
        return int(getattr(point, "id", 0) or 0)
    except Exception:
        return 0


def _point_ts(point: CalibrationPointLike) -> Optional[str]:
    ts = getattr(point, "ts", None)
    if ts is None:
        return None
    ts_s = str(ts).strip()
    return ts_s or None


def _last_calibration_ts(points: list[CalibrationPointLike]) -> Optional[str]:
    best_ts: Optional[str] = None
    best_id = -1
    for point in points:
        ts = _point_ts(point)
        pid = _point_id(point)
        if ts is not None:
            if best_ts is None or ts > best_ts or (ts == best_ts and pid > best_id):
                best_ts = ts
                best_id = pid
        elif best_ts is None and pid > best_id:
            best_id = pid
    return best_ts


def _usable_segments(
    active_points: list[CalibrationPointLike],
) -> list[tuple[int, float, float, float, float, float]]:
    """Return adjacent segments as (idx, sig0, sig1, wt0, wt1, slope)."""
    segments: list[tuple[int, float, float, float, float, float]] = []
    for idx in range(len(active_points) - 1):
        p0 = active_points[idx]
        p1 = active_points[idx + 1]
        sig0 = float(p0.signal)
        sig1 = float(p1.signal)
        wt0 = float(p0.known_weight_lbs)
        wt1 = float(p1.known_weight_lbs)
        sig_delta = sig1 - sig0
        if abs(sig_delta) <= SIGNAL_EPS:
            continue
        slope = (wt1 - wt0) / sig_delta
        segments.append((idx, sig0, sig1, wt0, wt1, slope))
    return segments


def _select_segment_for_signal(
    signal_mv: float,
    active_points: list[CalibrationPointLike],
) -> tuple[float, float, float, float, float] | None:
    """Pick the nearest adjacent calibration segment for a signal value."""
    candidates: list[tuple[int, float, int, float, float, float, float, float]] = []
    for idx, sig0, sig1, wt0, wt1, slope in _usable_segments(active_points):
        lo = min(sig0, sig1)
        hi = max(sig0, sig1)
        in_range = (lo - SIGNAL_EPS) <= signal_mv <= (hi + SIGNAL_EPS)
        distance = 0.0 if in_range else min(abs(signal_mv - lo), abs(signal_mv - hi))
        candidates.append((0 if in_range else 1, float(distance), idx, sig0, sig1, wt0, wt1, slope))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    _, _, _, sig0, sig1, wt0, wt1, slope = candidates[0]
    return float(sig0), float(sig1), float(wt0), float(wt1), float(slope)


def _select_segment_for_weight(
    target_weight_lbs: float,
    active_points: list[CalibrationPointLike],
) -> tuple[float, float, float, float, float] | None:
    """Pick nearest adjacent calibration segment for a target weight."""
    candidates: list[tuple[int, float, int, float, float, float, float, float]] = []
    for idx, sig0, sig1, wt0, wt1, slope in _usable_segments(active_points):
        wt_delta = wt1 - wt0
        if abs(wt_delta) <= 1e-9:
            continue
        lo = min(wt0, wt1)
        hi = max(wt0, wt1)
        in_range = lo <= target_weight_lbs <= hi
        distance = 0.0 if in_range else min(abs(target_weight_lbs - lo), abs(target_weight_lbs - hi))
        candidates.append((0 if in_range else 1, float(distance), idx, sig0, sig1, wt0, wt1, slope))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    _, _, _, sig0, sig1, wt0, wt1, slope = candidates[0]
    return float(sig0), float(sig1), float(wt0), float(wt1), float(slope)


def select_active_calibration_points(cal_points: Iterable[CalibrationPointLike]) -> list[CalibrationPointLike]:
    """Return deterministic active points: latest capture per known weight."""
    latest_by_weight: dict[float, CalibrationPointLike] = {}
    for point in cal_points:
        weight = float(point.known_weight_lbs)
        existing = latest_by_weight.get(weight)
        if existing is None:
            latest_by_weight[weight] = point
            continue
        point_id = _point_id(point)
        existing_id = _point_id(existing)
        if point_id > existing_id:
            latest_by_weight[weight] = point
            continue
        if point_id == existing_id:
            ts = _point_ts(point)
            existing_ts = _point_ts(existing)
            if ts is not None and existing_ts is not None and ts > existing_ts:
                latest_by_weight[weight] = point
    return sorted(latest_by_weight.values(), key=lambda p: float(p.known_weight_lbs))


def calibration_model_from_points(cal_points: Iterable[CalibrationPointLike]) -> CalibrationModel:
    points = list(cal_points)
    active_points = select_active_calibration_points(points)
    total_count = len(points)
    active_count = len(active_points)
    last_ts = _last_calibration_ts(points)

    if active_count == 2:
        p0 = active_points[0]
        p1 = active_points[-1]
        sig0 = float(p0.signal)
        sig1 = float(p1.signal)
        wt0 = float(p0.known_weight_lbs)
        wt1 = float(p1.known_weight_lbs)
        sig_delta = sig1 - sig0
        if abs(sig_delta) > SIGNAL_EPS:
            slope = (wt1 - wt0) / sig_delta
            intercept = wt0 - slope * sig0
            return CalibrationModel(
                method="two_point_linear",
                slope_lbs_per_mv=float(slope),
                intercept_lbs=float(intercept),
                active_points_count=active_count,
                total_points_count=total_count,
                last_calibration_utc=last_ts,
            )
        return CalibrationModel(
            method="two_point_degenerate",
            slope_lbs_per_mv=None,
            intercept_lbs=None,
            active_points_count=active_count,
            total_points_count=total_count,
            last_calibration_utc=last_ts,
        )

    if active_count > 2:
        seg = _select_segment_for_weight(0.0, active_points)
        if seg is not None:
            _, _, _, _, slope = seg
            return CalibrationModel(
                method="piecewise_linear",
                slope_lbs_per_mv=float(slope),
                intercept_lbs=None,
                active_points_count=active_count,
                total_points_count=total_count,
                last_calibration_utc=last_ts,
            )
        return CalibrationModel(
            method="piecewise_degenerate",
            slope_lbs_per_mv=None,
            intercept_lbs=None,
            active_points_count=active_count,
            total_points_count=total_count,
            last_calibration_utc=last_ts,
        )

    if active_count == 1:
        p = active_points[0]
        sig = float(p.signal)
        wt = float(p.known_weight_lbs)
        if abs(sig) > SIGNAL_EPS:
            return CalibrationModel(
                method="single_point_linear",
                slope_lbs_per_mv=float(wt / sig),
                intercept_lbs=0.0,
                active_points_count=active_count,
                total_points_count=total_count,
                last_calibration_utc=last_ts,
            )
        return CalibrationModel(
            method="single_point_degenerate",
            slope_lbs_per_mv=None,
            intercept_lbs=None,
            active_points_count=active_count,
            total_points_count=total_count,
            last_calibration_utc=last_ts,
        )

    return CalibrationModel(
        method="uncalibrated",
        slope_lbs_per_mv=None,
        intercept_lbs=None,
        active_points_count=0,
        total_points_count=total_count,
        last_calibration_utc=last_ts,
    )


def calibration_zero_signal(cal_points: Iterable[CalibrationPointLike]) -> float:
    """Return the signal value that best represents 0 lb in active calibration."""
    active_points = select_active_calibration_points(cal_points)
    if not active_points:
        return 0.0
    for point in active_points:
        if abs(float(point.known_weight_lbs)) <= 1e-9:
            return float(point.signal)
    if len(active_points) == 1:
        return float(active_points[0].signal)

    seg = _select_segment_for_weight(0.0, active_points)
    if seg is not None:
        sig0, sig1, wt0, wt1, _ = seg
        wt_delta = wt1 - wt0
        if abs(wt_delta) > 1e-9:
            t = (0.0 - wt0) / wt_delta
            return float(sig0 + t * (sig1 - sig0))

    zero_point = min(active_points, key=lambda p: abs(float(p.known_weight_lbs)))
    return float(zero_point.signal)


def calibration_signal_at_weight(
    target_weight_lbs: float,
    cal_points: Iterable[CalibrationPointLike],
) -> float:
    """Return the signal value that represents a given weight in the calibration curve."""
    target = float(target_weight_lbs)
    active_points = select_active_calibration_points(cal_points)
    if not active_points:
        return 0.0
    if len(active_points) == 1:
        p = active_points[0]
        sig = float(p.signal)
        wt = float(p.known_weight_lbs)
        if abs(wt) <= 1e-9:
            return sig
        return sig * (target / wt) if abs(wt) > 1e-9 else sig

    seg = _select_segment_for_weight(target, active_points)
    if seg is not None:
        sig0, sig1, wt0, wt1, _ = seg
        wt_delta = wt1 - wt0
        if abs(wt_delta) > 1e-9:
            t = (target - wt0) / wt_delta
            return float(sig0 + t * (sig1 - sig0))

    nearest = min(active_points, key=lambda p: abs(float(p.known_weight_lbs) - target))
    return float(nearest.signal)


def compute_zero_offset(
    current_signal: float,
    cal_points: Iterable[CalibrationPointLike],
    zero_target_lb: float = 0.0,
) -> tuple[float, float]:
    """Compute manual ZERO offset so the scale reads zero_target_lb.

    When zero_target_lb is 0.0 (default), this behaves like a traditional
    zero: the current signal is mapped to 0 lbs.  When set to a positive
    value (e.g. 3.0), ZERO targets that weight instead, preserving a
    configurable floor above the PLC dead-zone.
    """
    current_signal = float(current_signal)
    zero_target_lb = float(zero_target_lb)
    if abs(zero_target_lb) < 1e-9:
        cal_target_sig = calibration_zero_signal(cal_points)
    else:
        cal_target_sig = calibration_signal_at_weight(zero_target_lb, cal_points)
    drift = current_signal - cal_target_sig
    return float(drift), float(cal_target_sig)


def map_signal_to_weight(
    signal_mv: float,
    cal_points: Iterable[CalibrationPointLike],
) -> tuple[float | None, float | None]:
    """Map signal to weight using deterministic active-point behavior."""
    signal_mv = float(signal_mv)
    active_points = select_active_calibration_points(cal_points)
    active_count = len(active_points)

    if active_count >= 2:
        seg = _select_segment_for_signal(signal_mv, active_points)
        if seg is None:
            return 0.0, None
        sig0, _sig1, wt0, _wt1, slope = seg
        weight_lbs = wt0 + (signal_mv - sig0) * slope
        return float(weight_lbs), float(slope)

    if active_count == 1:
        p = active_points[0]
        sig = float(p.signal)
        wt = float(p.known_weight_lbs)
        if abs(sig) <= SIGNAL_EPS:
            return 0.0, None
        slope = wt / sig
        return float(slope * signal_mv), float(slope)

    return None, None


def estimate_lbs_per_mv(cal_points: Iterable[CalibrationPointLike]) -> float | None:
    """Estimate lbs/mV near 0 lb for zeroing and auto-zero logic."""
    active_points = select_active_calibration_points(cal_points)
    if len(active_points) >= 2:
        seg = _select_segment_for_weight(0.0, active_points)
        if seg is not None:
            return float(seg[4])
        return None
    if len(active_points) == 1:
        sig = float(active_points[0].signal)
        if abs(sig) <= SIGNAL_EPS:
            return None
        return float(active_points[0].known_weight_lbs) / sig
    return None
