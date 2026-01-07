from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from src.core.pwl import PiecewiseLinearCurve


CalibrationPoint = Tuple[float, float]  # (signal, known_weight_lbs)


@dataclass
class CalibrationCurve:
    """Piecewise-linear calibration: signal -> weight (lb)."""

    points: List[CalibrationPoint]
    ratiometric: bool = True

    def __post_init__(self) -> None:
        self._curve = PiecewiseLinearCurve([(s, w) for (s, w) in self.points])

    def add_point(self, signal: float, known_weight_lbs: float) -> None:
        self.points.append((float(signal), float(known_weight_lbs)))
        self._curve.add_point(float(signal), float(known_weight_lbs))

    def weight_from_signal(self, signal: float) -> float:
        return float(self._curve.eval(float(signal)))

    def as_dict(self) -> dict:
        return {"ratiometric": bool(self.ratiometric), "points": [(s, w) for (s, w) in self.points]}

    @staticmethod
    def from_dict(d: dict) -> "CalibrationCurve":
        pts = d.get("points") or []
        return CalibrationCurve(points=[(float(s), float(w)) for (s, w) in pts], ratiometric=bool(d.get("ratiometric", True)))


