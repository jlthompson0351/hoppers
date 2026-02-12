from __future__ import annotations

import unittest
from dataclasses import dataclass

from src.app.routes import _fit_linear_range_from_profile


@dataclass(frozen=True)
class _Point:
    analog_value: float
    plc_displayed_lbs: float


class OutputRangeFitTests(unittest.TestCase):
    def test_fit_linear_range_from_profile_in_voltage_mode(self) -> None:
        points = [
            _Point(analog_value=0.0, plc_displayed_lbs=0.0),
            _Point(analog_value=1.0, plc_displayed_lbs=25.0),
            _Point(analog_value=2.0, plc_displayed_lbs=50.0),
        ]
        min_lb, max_lb = _fit_linear_range_from_profile(points, "0_10V")
        self.assertAlmostEqual(min_lb, 0.0, places=6)
        self.assertAlmostEqual(max_lb, 250.0, places=6)

    def test_fit_linear_range_from_profile_in_current_mode(self) -> None:
        points = [
            _Point(analog_value=4.0, plc_displayed_lbs=0.0),
            _Point(analog_value=20.0, plc_displayed_lbs=300.0),
        ]
        min_lb, max_lb = _fit_linear_range_from_profile(points, "4_20mA")
        self.assertAlmostEqual(min_lb, 0.0, places=6)
        self.assertAlmostEqual(max_lb, 300.0, places=6)


if __name__ == "__main__":
    unittest.main()
