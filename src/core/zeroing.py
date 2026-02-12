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

    if active_count >= 2:
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
    zero_point = min(active_points, key=lambda p: abs(float(p.known_weight_lbs)))
    return float(zero_point.signal)


def compute_zero_offset(current_signal: float, cal_points: Iterable[CalibrationPointLike]) -> tuple[float, float]:
    """Compute manual ZERO offset and referenced calibration-zero signal."""
    current_signal = float(current_signal)
    cal_zero = calibration_zero_signal(cal_points)
    drift = current_signal - cal_zero
    return float(drift), float(cal_zero)


def map_signal_to_weight(
    signal_mv: float,
    cal_points: Iterable[CalibrationPointLike],
) -> tuple[float | None, float | None]:
    """Map signal to weight using deterministic single/two-point linear behavior."""
    signal_mv = float(signal_mv)
    model = calibration_model_from_points(cal_points)
    slope = model.slope_lbs_per_mv

    if model.method == "two_point_linear" and slope is not None and model.intercept_lbs is not None:
        return float(slope * signal_mv + model.intercept_lbs), float(slope)
    if model.method == "single_point_linear" and slope is not None:
        return float(slope * signal_mv), float(slope)
    if model.method in ("two_point_degenerate", "single_point_degenerate"):
        return 0.0, None
    return None, None


def estimate_lbs_per_mv(cal_points: Iterable[CalibrationPointLike]) -> float | None:
    """Estimate lbs/mV slope for zeroing and auto-zero logic."""
    return calibration_model_from_points(cal_points).slope_lbs_per_mv
