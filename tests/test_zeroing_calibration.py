from __future__ import annotations

import unittest
from dataclasses import dataclass

from src.core.zeroing import (
    calibration_model_from_points,
    calibration_zero_signal,
    compute_zero_offset,
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

    def test_model_and_mapping_use_all_active_points(self) -> None:
        points = [
            _Point(id=1, ts="2026-02-01T10:00:00+00:00", known_weight_lbs=0.0, signal=5.0),
            _Point(id=2, ts="2026-02-01T10:00:05+00:00", known_weight_lbs=50.0, signal=7.0),
            _Point(id=3, ts="2026-02-08T10:00:00+00:00", known_weight_lbs=50.0, signal=7.2),
            _Point(id=4, ts="2026-02-08T10:00:10+00:00", known_weight_lbs=100.0, signal=9.4),
        ]
        model = calibration_model_from_points(points)
        self.assertEqual(model.method, "piecewise_linear")
        self.assertIsNotNone(model.slope_lbs_per_mv)
        self.assertIsNone(model.intercept_lbs)
        self.assertEqual(model.active_points_count, 3)
        self.assertEqual(model.total_points_count, 4)
        self.assertEqual(model.last_calibration_utc, "2026-02-08T10:00:10+00:00")

        # Local near-zero slope uses adjacent segment around 0 lb.
        self.assertAlmostEqual(model.slope_lbs_per_mv or 0.0, 22.727272727, places=6)

        mapped_50, slope = map_signal_to_weight(7.2, points)
        self.assertIsNotNone(mapped_50)
        self.assertIsNotNone(slope)
        self.assertAlmostEqual(mapped_50 or 0.0, 50.0, places=6)
        self.assertAlmostEqual(slope or 0.0, model.slope_lbs_per_mv or 0.0, places=9)

    def test_zero_signal_without_explicit_zero_point_is_extrapolated(self) -> None:
        points = [
            _Point(id=1, ts="2026-02-01T10:00:00+00:00", known_weight_lbs=25.0, signal=2.5),
            _Point(id=2, ts="2026-02-01T10:00:05+00:00", known_weight_lbs=50.0, signal=5.0),
        ]
        self.assertAlmostEqual(calibration_zero_signal(points), 0.0, places=6)

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

    # ── Calibration-signal-referenced zero drift tests ────────────

    def test_drift_from_calibration_zero_signal_small(self) -> None:
        """Real-world scenario: 6-point cal with 0 lb at 5.88 mV.
        Current raw signal is 5.86 mV → drift is small (~-2.6 lb)."""
        points = [
            _Point(id=1, ts="2026-02-13T10:00:00+00:00", known_weight_lbs=0.0, signal=5.879963),
            _Point(id=2, ts="2026-02-13T10:00:01+00:00", known_weight_lbs=25.0, signal=6.070754),
            _Point(id=3, ts="2026-02-13T10:00:02+00:00", known_weight_lbs=50.0, signal=6.262027),
            _Point(id=4, ts="2026-02-13T10:00:03+00:00", known_weight_lbs=75.0, signal=6.451758),
            _Point(id=5, ts="2026-02-13T10:00:04+00:00", known_weight_lbs=100.0, signal=6.643406),
            _Point(id=6, ts="2026-02-13T10:00:05+00:00", known_weight_lbs=150.0, signal=7.023742),
        ]
        cal_zero = calibration_zero_signal(points)
        self.assertAlmostEqual(cal_zero, 5.879963, places=6)

        slope = estimate_lbs_per_mv(points)
        self.assertIsNotNone(slope)
        # Slope near 0 lb: 25 / (6.070754 - 5.879963) ≈ 131.0
        self.assertAlmostEqual(slope, 25.0 / (6.070754 - 5.879963), places=3)

        # Simulate raw signal slightly below cal zero (drift)
        raw_signal = 5.86
        drift_mv, ref_signal = compute_zero_offset(raw_signal, points)
        self.assertAlmostEqual(ref_signal, 5.879963, places=6)
        # drift_mv is negative (signal dropped)
        expected_drift_mv = 5.86 - 5.879963
        self.assertAlmostEqual(drift_mv, expected_drift_mv, places=6)

        # Convert to lbs: small value, not hundreds
        drift_lbs = drift_mv * slope
        self.assertAlmostEqual(drift_lbs, expected_drift_mv * slope, places=3)
        self.assertGreater(abs(drift_lbs), 0.5)
        self.assertLess(abs(drift_lbs), 10.0)  # Must be small, not 250+

    def test_drift_zero_when_signal_matches_cal(self) -> None:
        """When raw signal exactly matches calibration zero, drift is 0."""
        points = [
            _Point(id=1, ts="2026-02-13T10:00:00+00:00", known_weight_lbs=0.0, signal=5.88),
            _Point(id=2, ts="2026-02-13T10:00:01+00:00", known_weight_lbs=50.0, signal=6.26),
        ]
        drift_mv, cal_zero = compute_zero_offset(5.88, points)
        self.assertAlmostEqual(drift_mv, 0.0, places=9)
        self.assertAlmostEqual(cal_zero, 5.88, places=6)

    def test_drift_no_cal_points_returns_zero_signal(self) -> None:
        """With no calibration, cal_zero_signal returns 0 and slope is None."""
        cal_zero = calibration_zero_signal([])
        self.assertAlmostEqual(cal_zero, 0.0, places=9)
        slope = estimate_lbs_per_mv([])
        self.assertIsNone(slope)


if __name__ == "__main__":
    unittest.main()
