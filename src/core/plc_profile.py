from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from src.core.pwl import PiecewiseLinearCurve


PlcProfilePoint = Tuple[float, float]  # (plc_displayed_lbs, commanded_analog_value)


@dataclass
class PlcProfileCurve:
    """Piecewise-linear correction curve: desired_lbs -> analog_value.

    Points are collected by commanding a known analog value and reading PLC displayed lbs.
    The stored curve maps:
      x = PLC displayed lbs
      y = commanded analog value
    Then when we want the PLC to display 'true' lbs, we evaluate analog_value = f(true_lbs).
    """

    output_mode: str  # "0_10V" or "4_20mA"
    points: List[PlcProfilePoint]

    def __post_init__(self) -> None:
        self._curve = PiecewiseLinearCurve([(lbs, a) for (lbs, a) in self.points])

    def add_point(self, plc_displayed_lbs: float, commanded_analog_value: float) -> None:
        self.points.append((float(plc_displayed_lbs), float(commanded_analog_value)))
        self._curve.add_point(float(plc_displayed_lbs), float(commanded_analog_value))

    def analog_for_weight(self, desired_true_lbs: float) -> float:
        return float(self._curve.eval(float(desired_true_lbs)))

    def as_dict(self) -> dict:
        return {"output_mode": self.output_mode, "points": [(lbs, a) for (lbs, a) in self.points]}

    @staticmethod
    def from_dict(d: dict) -> "PlcProfileCurve":
        pts = d.get("points") or []
        return PlcProfileCurve(
            output_mode=str(d.get("output_mode", "0_10V")),
            points=[(float(lbs), float(a)) for (lbs, a) in pts],
        )


