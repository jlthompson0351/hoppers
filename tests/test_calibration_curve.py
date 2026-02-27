from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from src.core.zeroing import map_signal_to_weight, select_active_calibration_points
from src.db.migrate import ensure_db
from src.db.repo import AppRepository


@dataclass(frozen=True)
class _Point:
    known_weight_lbs: float
    signal: float


class CalibrationCurveTests(unittest.TestCase):
    def test_weekly_recalibration_replaces_same_weight_and_keeps_others(self) -> None:
        tmp = tempfile.mkdtemp(prefix="calibration-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        db_path = Path(tmp) / "calibration.db"
        ensure_db(db_path)
        repo = AppRepository(db_path)

        # Week 1
        self.assertFalse(repo.upsert_calibration_point(known_weight_lbs=25.0, signal=2.5))
        self.assertFalse(repo.upsert_calibration_point(known_weight_lbs=50.0, signal=5.0))

        # Week 2: 50 is recaptured (replaces old 50), 100 is newly added.
        self.assertTrue(repo.upsert_calibration_point(known_weight_lbs=50.0, signal=5.5))
        self.assertFalse(repo.upsert_calibration_point(known_weight_lbs=100.0, signal=10.0))

        points = repo.get_calibration_points()
        self.assertEqual([p.known_weight_lbs for p in points], [25.0, 50.0, 50.0, 100.0])

        active = select_active_calibration_points(points)
        self.assertEqual([p.known_weight_lbs for p in active], [25.0, 50.0, 100.0])

        fifty = next(p for p in active if abs(p.known_weight_lbs - 50.0) < 1e-9)
        self.assertAlmostEqual(fifty.signal, 5.5, places=9)

    def test_piecewise_mapping_uses_middle_segment(self) -> None:
        points = [
            _Point(known_weight_lbs=25.0, signal=2.5),
            _Point(known_weight_lbs=50.0, signal=6.0),
            _Point(known_weight_lbs=100.0, signal=10.0),
        ]
        weight_lbs, slope_lbs_per_mv = map_signal_to_weight(8.0, points)

        self.assertIsNotNone(weight_lbs)
        self.assertIsNotNone(slope_lbs_per_mv)
        self.assertAlmostEqual(float(weight_lbs), 75.0, places=6)
        self.assertAlmostEqual(float(slope_lbs_per_mv), 12.5, places=6)

    def test_zero_point_fallback_returns_none(self) -> None:
        weight_lbs, slope_lbs_per_mv = map_signal_to_weight(3.0, [])
        self.assertIsNone(weight_lbs)
        self.assertIsNone(slope_lbs_per_mv)

    def test_single_point_fallback_uses_zero_crossing(self) -> None:
        points = [_Point(known_weight_lbs=50.0, signal=4.0)]
        weight_lbs, slope_lbs_per_mv = map_signal_to_weight(5.0, points)

        self.assertIsNotNone(weight_lbs)
        self.assertIsNotNone(slope_lbs_per_mv)
        self.assertAlmostEqual(float(weight_lbs), 62.5, places=6)
        self.assertAlmostEqual(float(slope_lbs_per_mv), 12.5, places=6)


if __name__ == "__main__":
    unittest.main()
