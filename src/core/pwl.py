from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


Point = Tuple[float, float]


def _sorted_points(points: Iterable[Point]) -> List[Point]:
    pts = [(float(x), float(y)) for (x, y) in points]
    pts.sort(key=lambda p: p[0])
    return pts


def pwl_eval(x: float, points: Sequence[Point], extrapolate: bool = True) -> float:
    """Piecewise-linear interpolation with optional extrapolation.

    If points are not sorted, they will be treated as sorted by x.
    
    Args:
        x: The input value to evaluate.
        points: List of (x, y) calibration points.
        extrapolate: If True, extrapolate linearly beyond the calibration range.
                     If False, clamp to the nearest endpoint value.
    """

    if not points:
        return 0.0
    pts = _sorted_points(points)
    x = float(x)

    # Handle values below the first calibration point
    if x <= pts[0][0]:
        if extrapolate and len(pts) >= 2:
            # Extrapolate using the slope from the first two points
            x0, y0 = pts[0]
            x1, y1 = pts[1]
            if x1 != x0:
                slope = (y1 - y0) / (x1 - x0)
                return y0 + slope * (x - x0)
        return pts[0][1]

    # Handle values above the last calibration point
    if x >= pts[-1][0]:
        if extrapolate and len(pts) >= 2:
            # Extrapolate using the slope from the last two points
            x0, y0 = pts[-2]
            x1, y1 = pts[-1]
            if x1 != x0:
                slope = (y1 - y0) / (x1 - x0)
                return y1 + slope * (x - x1)
        return pts[-1][1]

    # Find segment for interpolation
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)

    # Should not happen, but keep safe.
    return pts[-1][1]


@dataclass
class PiecewiseLinearCurve:
    points: List[Point]

    def __post_init__(self) -> None:
        self.points = _sorted_points(self.points)

    def add_point(self, x: float, y: float) -> None:
        self.points.append((float(x), float(y)))
        self.points = _sorted_points(self.points)

    def eval(self, x: float) -> float:
        return pwl_eval(x, self.points)


