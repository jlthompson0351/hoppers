from __future__ import annotations

import unittest
from dataclasses import dataclass

from src.core.zeroing import (
    calibration_model_from_points,
    calibration_zero_signal,
    estimate_lbs_per_mv,
    map_signal_to_weight,
    select_active_calibration_points,
)


@dataclass(frozen=True)
class _Point:
    id: int
    ts: str
    known_weight_lbs: float
    signal: float


class ZeroingCalibrationTests(unittest.TestCase):
    def test_select_active_points_uses_latest_id_per_weight(self) -> None:
        points = [
            _Point(id=1, ts="2026-02-01T10:00:00+00:00", known_weight_lbs=0.0, signal=5.0),
            _Point(id=2, ts="2026-02-01T10:00:05+00:00", known_weight_lbs=50.0, signal=7.0),
            _Point(id=3, ts="2026-02-08T10:00:00+00:00", known_weight_lbs=50.0, signal=7.2),
            _Point(id=4, ts="2026-02-08T10:00:10+00:00", known_weight_lbs=100.0, signal=9.4),
        ]
        active = select_active_calibration_points(points)
        self.assertEqual(len(active), 3)
        self.assertAlmostEqual(active[1].known_weight_lbs, 50.0, places=6)
        self.assertAlmostEqual(active[1].signal, 7.2, places=6)

    def test_model_and_mapping_are_two_point_linear(self) -> None:
        points = [
            _Point(id=1, ts="2026-02-01T10:00:00+00:00", known_weight_lbs=0.0, signal=5.0),
            _Point(id=2, ts="2026-02-01T10:00:05+00:00", known_weight_lbs=50.0, signal=7.0),
            _Point(id=3, ts="2026-02-08T10:00:00+00:00", known_weight_lbs=50.0, signal=7.2),
            _Point(id=4, ts="2026-02-08T10:00:10+00:00", known_weight_lbs=100.0, signal=9.4),
        ]
        model = calibration_model_from_points(points)
        self.assertEqual(model.method, "two_point_linear")
        self.assertIsNotNone(model.slope_lbs_per_mv)
        self.assertIsNotNone(model.intercept_lbs)
        self.assertEqual(model.active_points_count, 3)
        self.assertEqual(model.total_points_count, 4)
        self.assertEqual(model.last_calibration_utc, "2026-02-08T10:00:10+00:00")

        # Endpoints are (0 lb @ 5.0 mV) and (100 lb @ 9.4 mV)
        # Slope = 100 / 4.4 = 22.727272...
        self.assertAlmostEqual(model.slope_lbs_per_mv or 0.0, 22.727272727, places=6)
        self.assertAlmostEqual(model.intercept_lbs or 0.0, -113.636363636, places=6)

        mapped_50, slope = map_signal_to_weight(7.2, points)
        self.assertIsNotNone(mapped_50)
        self.assertIsNotNone(slope)
        self.assertAlmostEqual(mapped_50 or 0.0, 50.0, places=6)
        self.assertAlmostEqual(slope or 0.0, model.slope_lbs_per_mv or 0.0, places=9)

    def test_single_point_fallback_and_zero_signal(self) -> None:
        points = [_Point(id=11, ts="2026-02-10T09:00:00+00:00", known_weight_lbs=50.0, signal=2.0)]
        model = calibration_model_from_points(points)
        self.assertEqual(model.method, "single_point_linear")
        self.assertAlmostEqual(model.slope_lbs_per_mv or 0.0, 25.0, places=6)
        self.assertAlmostEqual(model.intercept_lbs or 0.0, 0.0, places=6)

        mapped, slope = map_signal_to_weight(1.5, points)
        self.assertAlmostEqual(mapped or 0.0, 37.5, places=6)
        self.assertAlmostEqual(slope or 0.0, 25.0, places=6)
        self.assertAlmostEqual(calibration_zero_signal(points), 2.0, places=6)
        self.assertAlmostEqual(estimate_lbs_per_mv(points) or 0.0, 25.0, places=6)

    def test_uncalibrated_returns_none(self) -> None:
        model = calibration_model_from_points([])
        self.assertEqual(model.method, "uncalibrated")
        self.assertIsNone(model.slope_lbs_per_mv)
        self.assertIsNone(model.intercept_lbs)

        mapped, slope = map_signal_to_weight(3.0, [])
        self.assertIsNone(mapped)
        self.assertIsNone(slope)
        self.assertIsNone(estimate_lbs_per_mv([]))


if __name__ == "__main__":
    unittest.main()
