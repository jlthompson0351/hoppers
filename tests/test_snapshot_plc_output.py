from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.app import create_app
from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.state import LiveState


class SnapshotPlcOutputTests(unittest.TestCase):
    def _make_app(self) -> tuple:
        """Create test app with repo and state."""
        tmp = tempfile.mkdtemp(prefix="snapshot-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        state = LiveState()

        app = create_app()
        app.config["REPO"] = repo
        app.config["LIVE_STATE"] = state
        app.config["TESTING"] = True

        return app, repo, state

    def test_snapshot_exposes_mapping_status_fields(self) -> None:
        app, repo, state = self._make_app()
        state.set(
            output_mode="0_10V",
            output_command=2.0,
            output_units="V",
            output_armed=True,
            output_mapping_mode="profile",
            output_profile_active=True,
            output_profile_points=3,
        )

        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

        plc = body["plcOutput"]
        self.assertEqual(plc["mapping_mode"], "profile")
        self.assertTrue(plc["profile_active"])
        self.assertEqual(plc["profile_points"], 3)
        # range_min_lb / range_max_lb removed from snapshot (no longer exposed in UI)
        
        # Verify excitation block is absent (removed from API)
        self.assertNotIn("excitation", body, "excitation block should be removed from snapshot")

    def test_snapshot_zero_offset_unit_consistency(self) -> None:
        """Snapshot must keep zero_offset_mv and zero_offset_lbs internally consistent."""
        app, repo, state = self._make_app()

        # Add calibration to establish slope
        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)
        expected_slope = 50.0 / (6.26 - 5.88)  # ≈ 131.58 lbs/mV

        # Set a known zero offset in lbs
        zero_offset_lbs = 2.5
        repo.update_config_section(
            "scale",
            lambda section, _: section.update(
                {
                    "zero_offset_lbs": zero_offset_lbs,
                    "zero_offset_updated_utc": "2026-02-15T10:00:00+00:00",
                }
            ),
        )

        # Set state with consistent lbs_per_mv
        state.set(
            zero_offset_lbs=zero_offset_lbs,
            lbs_per_mv=expected_slope,
            total_weight_lbs=10.0,
            stable=True,
        )

        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

        weight = body["weight"]
        zero_lbs = float(weight["zero_offset_lbs"])
        zero_mv = float(weight["zero_offset_mv"])

        # Unit consistency: zero_offset_mv should be derived from zero_offset_lbs / lbs_per_mv
        expected_mv = zero_offset_lbs / expected_slope
        self.assertAlmostEqual(zero_lbs, zero_offset_lbs, places=9)
        self.assertAlmostEqual(zero_mv, expected_mv, places=6)

    def test_snapshot_zero_offset_when_no_calibration(self) -> None:
        """When no calibration exists, snapshot should show zero offset in lbs but zero mV."""
        app, repo, state = self._make_app()

        # No calibration points, so lbs_per_mv = 0
        zero_offset_lbs = 1.5
        repo.update_config_section(
            "scale",
            lambda section, _: section.update({"zero_offset_lbs": zero_offset_lbs}),
        )
        state.set(zero_offset_lbs=zero_offset_lbs, lbs_per_mv=0.0, stable=False)

        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

        weight = body["weight"]
        zero_lbs = float(weight["zero_offset_lbs"])
        zero_mv = float(weight["zero_offset_mv"])

        self.assertAlmostEqual(zero_lbs, zero_offset_lbs, places=9)
        self.assertAlmostEqual(zero_mv, 0.0, places=9)  # Division by zero protection

    def test_snapshot_zero_offset_legacy_keys(self) -> None:
        """Verify legacy keys zero_offset_signal and zero_offset_mv are present for compatibility."""
        app, repo, state = self._make_app()

        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)
        slope = 50.0 / (6.26 - 5.88)

        zero_offset_lbs = 3.0
        state.set(zero_offset_lbs=zero_offset_lbs, lbs_per_mv=slope)

        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

        weight = body["weight"]
        self.assertIn("zero_offset_signal", weight)
        self.assertIn("zero_offset_mv", weight)
        self.assertIn("zero_offset_lbs", weight)

        # All should be consistent
        zero_mv = float(weight["zero_offset_mv"])
        zero_signal = float(weight["zero_offset_signal"])
        zero_lbs = float(weight["zero_offset_lbs"])

        self.assertAlmostEqual(zero_signal, zero_mv, places=9)
        self.assertAlmostEqual(zero_lbs, zero_mv * slope, places=6)

    def test_snapshot_prefers_canonical_mv_when_both_fields_present(self) -> None:
        """When mV and lbs disagree, snapshot should treat mV as canonical."""
        app, repo, state = self._make_app()

        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)
        slope = 50.0 / (6.26 - 5.88)

        # Intentionally conflicting values: canonical mV should win.
        state.set(
            zero_offset_mv=0.020,
            zero_offset_lbs=99.0,
            lbs_per_mv=slope,
            stable=True,
        )

        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

        weight = body["weight"]
        self.assertAlmostEqual(float(weight["zero_offset_mv"]), 0.020, places=9)
        self.assertAlmostEqual(float(weight["zero_offset_signal"]), 0.020, places=9)
        self.assertAlmostEqual(float(weight["zero_offset_lbs"]), 0.020 * slope, places=6)


if __name__ == "__main__":
    unittest.main()
