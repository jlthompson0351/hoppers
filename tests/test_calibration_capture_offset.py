from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from src.app.routes import _apply_calibration_capture
from src.db.migrate import ensure_db
from src.db.repo import AppRepository


class CalibrationCaptureOffsetTests(unittest.TestCase):
    def test_capture_uses_raw_signal_and_resets_zero_offset(self) -> None:
        """Calibration capture stores the RAW signal (no zero adjustment).

        Zero offset operates in the weight domain, so calibration points
        always record the unmodified signal from the DAQ.
        """
        tmp = tempfile.mkdtemp(prefix="capture-offset-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)

        cfg = repo.get_latest_config()
        cfg.setdefault("scale", {})
        cfg["scale"]["zero_offset_lbs"] = 1.5
        cfg["scale"]["zero_offset_mv"] = 0.0
        cfg["scale"]["zero_offset_signal"] = 0.0
        repo.save_config(cfg)

        snap = {
            "signal_for_cal": 5.85,
            "total_signal": 5.85,
            "raw_signal_mv": 5.85,
            "zero_offset_lbs": 1.5,
            "stable": True,
            "zero_tracking_active": False,
        }

        result = _apply_calibration_capture(
            repo=repo,
            snap=snap,
            known_weight_lbs=25.0,
            requested_mode="overwrite",
            confirm_average=False,
            state=None,
        )
        self.assertTrue(result["success"])
        # Raw signal is stored without any zero adjustment.
        self.assertAlmostEqual(float(result["captured_signal_mv"]), 5.85, places=6)
        self.assertAlmostEqual(float(result["applied_signal_mv"]), 5.85, places=6)

        points = repo.get_calibration_points(limit=10)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(float(points[0].signal), 5.85, places=6)

        # Adding a calibration point changes the curve, so zero offset is reset.
        cfg_after = repo.get_latest_config()
        scale_after = cfg_after.get("scale") or {}
        self.assertAlmostEqual(float(scale_after.get("zero_offset_lbs") or 0.0), 0.0, places=9)
        self.assertNotAlmostEqual(float(scale_after.get("zero_offset_lbs") or 0.0), 1.5, places=9)


if __name__ == "__main__":
    unittest.main()
