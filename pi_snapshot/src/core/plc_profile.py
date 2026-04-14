"""PLC output profile curve utilities.

Maps weight (lb) to analog output (V or mA) using piecewise linear interpolation.
When input weight is outside the defined points, the curve extrapolates using the
nearest segment.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


_WEIGHT_EPS = 1e-9


@dataclass(frozen=True)
class PlcProfilePoint:
    weight_lb: float
    analog_value: float


def _interp_segment(
    x: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> float:
    dx = float(x1) - float(x0)
    if abs(dx) <= _WEIGHT_EPS:
        return float(y1)
    t = (float(x) - float(x0)) / dx
    return float(y0) + t * (float(y1) - float(y0))


class PlcProfileCurve:
    """Piecewise-linear weight -> analog mapping curve."""

    def __init__(self, output_mode: str, points: Iterable[Tuple[float, float]]) -> None:
        raw_points = [PlcProfilePoint(float(w), float(a)) for w, a in points]
        if len(raw_points) < 2:
            raise ValueError("PLC profile requires at least 2 points")
        self.output_mode = str(output_mode)
        self._points: List[PlcProfilePoint] = self._normalize_points(raw_points)
        if len(self._points) < 2:
            raise ValueError("PLC profile requires at least 2 unique weight points")
        self._weights = [p.weight_lb for p in self._points]

    @staticmethod
    def _normalize_points(points: Sequence[PlcProfilePoint]) -> List[PlcProfilePoint]:
        # Sort by weight so interpolation is well-defined.
        ordered = sorted(points, key=lambda p: (p.weight_lb, p.analog_value))
        collapsed: List[PlcProfilePoint] = []

        i = 0
        while i < len(ordered):
            w = ordered[i].weight_lb
            total = ordered[i].analog_value
            count = 1
            j = i + 1
            while j < len(ordered) and abs(ordered[j].weight_lb - w) <= _WEIGHT_EPS:
                total += ordered[j].analog_value
                count += 1
                j += 1
            collapsed.append(PlcProfilePoint(weight_lb=w, analog_value=(total / count)))
            i = j

        return collapsed

    @property
    def point_count(self) -> int:
        return len(self._points)

    def analog_from_weight(self, weight_lb: float) -> float:
        """Return interpolated/extrapolated analog output for a weight."""
        x = float(weight_lb)
        p = self._points

        if x <= p[0].weight_lb:
            return _interp_segment(x, p[0].weight_lb, p[0].analog_value, p[1].weight_lb, p[1].analog_value)
        if x >= p[-1].weight_lb:
            return _interp_segment(
                x,
                p[-2].weight_lb,
                p[-2].analog_value,
                p[-1].weight_lb,
                p[-1].analog_value,
            )

        hi = bisect_right(self._weights, x)
        lo = max(0, hi - 1)
        hi = min(len(p) - 1, hi)
        return _interp_segment(
            x,
            p[lo].weight_lb,
            p[lo].analog_value,
            p[hi].weight_lb,
            p[hi].analog_value,
        )
