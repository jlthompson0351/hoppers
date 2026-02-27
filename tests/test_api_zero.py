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


class ApiZeroEndpointTests(unittest.TestCase):
    """Endpoint-level tests for /api/zero and /api/zero/clear with unit consistency."""

    def _make_app(self) -> tuple:
        """Create test app with repo and state."""
        tmp = tempfile.mkdtemp(prefix="api-zero-tests-")
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

    def test_zero_rejected_when_unstable(self) -> None:
        """Zero endpoint rejects request when scale is not stable."""
        app, repo, state = self._make_app()
        state.set(stable=False, total_signal=5.85)

        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 400)
            body = json.loads(resp.data.decode("utf-8"))
            self.assertFalse(body.get("success"))
            self.assertIn("not stable", body.get("error", "").lower())

    def test_zero_rejected_when_no_calibration(self) -> None:
        """Zero endpoint rejects when no calibration points exist (slope unavailable)."""
        app, repo, state = self._make_app()
        state.set(stable=True, raw_signal_mv=5.85, signal_for_cal=5.85, total_signal=5.85)

        # No calibration points -> slope is None
        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 400)
            body = json.loads(resp.data.decode("utf-8"))
            self.assertFalse(body.get("success"))
            self.assertIn("calibration", body.get("error", "").lower())

    def test_zero_computes_drift_in_mv_and_converts_to_lbs(self) -> None:
        """Zero endpoint computes zero_offset_mv as drift, converts to lbs using slope."""
        app, repo, state = self._make_app()

        # Add 2-point calibration: 0 lb at 5.88 mV, 50 lb at 6.26 mV
        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)

        # Slope near zero: 50 / (6.26 - 5.88) ≈ 131.58 lbs/mV
        expected_slope = 50.0 / (6.26 - 5.88)

        # Current signal is 5.86 mV (below calibration zero)
        raw_signal = 5.86
        drift_mv = raw_signal - 5.88  # ≈ -0.02 mV
        expected_offset_lbs = drift_mv * expected_slope  # ≈ -2.63 lb

        state.set(
            stable=True,
            raw_signal_mv=raw_signal,
            signal_for_cal=raw_signal,
            total_signal=raw_signal,
        )

        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

            self.assertTrue(body.get("success"))
            self.assertEqual(body.get("method"), "calibration_signal")

            # Verify drift is in mV (small value)
            drift_mv_returned = body.get("drift_mv")
            self.assertIsNotNone(drift_mv_returned)
            self.assertAlmostEqual(drift_mv_returned, drift_mv, places=6)
            self.assertAlmostEqual(float(body.get("zero_offset_mv") or 0.0), drift_mv, places=6)
            self.assertAlmostEqual(float(body.get("zero_offset_signal") or 0.0), drift_mv, places=6)

            # Verify zero_offset_lbs reflects drift converted to lbs
            zero_offset_lbs = body.get("zero_offset_lbs")
            self.assertIsNotNone(zero_offset_lbs)
            self.assertAlmostEqual(zero_offset_lbs, expected_offset_lbs, places=3)

            # Verify it's a small correction, not hundreds of lbs
            self.assertGreater(abs(zero_offset_lbs), 0.5)
            self.assertLess(abs(zero_offset_lbs), 10.0)

    def test_zero_offset_lbs_consistent_with_slope(self) -> None:
        """Ensure zero_offset_lbs = zero_offset_mv * slope (unit consistency)."""
        app, repo, state = self._make_app()

        # 6-point calibration (real-world scenario)
        points = [
            (0.0, 5.879963),
            (25.0, 6.070754),
            (50.0, 6.262027),
            (75.0, 6.451758),
            (100.0, 6.643406),
            (150.0, 7.023742),
        ]
        for weight, signal in points:
            repo.add_calibration_point(known_weight_lbs=weight, signal=signal)

        # Slope near zero: 25 / (6.070754 - 5.879963) ≈ 131.0 lbs/mV
        expected_slope = 25.0 / (6.070754 - 5.879963)

        # Current signal slightly below cal zero
        raw_signal = 5.86
        cal_zero = 5.879963
        drift_mv = raw_signal - cal_zero

        state.set(
            stable=True,
            raw_signal_mv=raw_signal,
            signal_for_cal=raw_signal,
            total_signal=raw_signal,
        )

        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

            drift_mv_returned = body.get("drift_mv")
            zero_offset_lbs = body.get("zero_offset_lbs")
            self.assertIsNotNone(drift_mv_returned)
            self.assertIsNotNone(zero_offset_lbs)

            # Unit consistency: zero_offset_lbs = drift_mv * slope
            expected_lbs = drift_mv * expected_slope
            self.assertAlmostEqual(zero_offset_lbs, expected_lbs, places=3)
            self.assertAlmostEqual(drift_mv_returned, drift_mv, places=6)

    def test_zero_persists_offset_to_config(self) -> None:
        """Zero endpoint persists zero_offset_lbs to config.scale section."""
        app, repo, state = self._make_app()

        # Add calibration
        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)

        raw_signal = 5.86
        state.set(stable=True, raw_signal_mv=raw_signal, signal_for_cal=raw_signal)

        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))
            zero_offset_lbs = body.get("zero_offset_lbs")
            zero_offset_mv = body.get("zero_offset_mv")

        # Verify persistence
        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        persisted_offset = float(scale.get("zero_offset_lbs", 0.0) or 0.0)
        self.assertAlmostEqual(persisted_offset, zero_offset_lbs, places=9)
        self.assertAlmostEqual(float(scale.get("zero_offset_mv", 0.0) or 0.0), float(zero_offset_mv or 0.0), places=9)
        self.assertAlmostEqual(float(scale.get("zero_offset_signal", 0.0) or 0.0), float(zero_offset_mv or 0.0), places=9)
        self.assertIsNotNone(scale.get("zero_offset_updated_utc"))

    def test_zero_updates_live_state(self) -> None:
        """Zero endpoint updates LiveState with new offset."""
        app, repo, state = self._make_app()

        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)

        raw_signal = 5.86
        state.set(stable=True, raw_signal_mv=raw_signal, signal_for_cal=raw_signal)

        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))
            zero_offset_lbs = body.get("zero_offset_lbs")
            zero_offset_mv = body.get("zero_offset_mv")

        # Check live state was updated
        snap = state.snapshot()
        self.assertAlmostEqual(
            float(snap.get("zero_offset_lbs") or 0.0), zero_offset_lbs, places=9
        )
        self.assertAlmostEqual(float(snap.get("zero_offset_mv") or 0.0), float(zero_offset_mv or 0.0), places=9)
        self.assertAlmostEqual(float(snap.get("zero_offset_signal") or 0.0), float(zero_offset_mv or 0.0), places=9)
        self.assertIsNotNone(snap.get("zero_offset_updated_utc"))

    def test_zero_clear_resets_offset_to_zero(self) -> None:
        """/api/zero/clear resets zero_offset_lbs to 0.0."""
        app, repo, state = self._make_app()

        # Set a non-zero offset
        repo.update_config_section(
            "scale",
            lambda section, _: section.update(
                {"zero_offset_lbs": 5.25, "zero_offset_updated_utc": "2026-02-15T10:00:00+00:00"}
            ),
        )

        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), 5.25, places=9)

        # Clear zero
        with app.test_client() as client:
            resp = client.post("/api/zero/clear")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))
            self.assertTrue(body.get("success"))
            self.assertAlmostEqual(body.get("zero_offset_mv"), 0.0, places=9)

        # Verify persistence
        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), 0.0, places=9)
        self.assertAlmostEqual(float(scale.get("zero_offset_mv") or 0.0), 0.0, places=9)
        self.assertAlmostEqual(float(scale.get("zero_offset_signal") or 0.0), 0.0, places=9)

    def test_zero_clear_logs_event(self) -> None:
        """/api/zero/clear logs a clear event."""
        app, repo, state = self._make_app()

        # Set non-zero offset in config
        repo.update_config_section(
            "scale",
            lambda section, _: section.update({
                "zero_offset_lbs": 3.5,
                "zero_offset_updated_utc": "2026-02-15T10:00:00+00:00"
            }),
        )

        with app.test_client() as client:
            resp = client.post("/api/zero/clear")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))
            self.assertTrue(body.get("success"))

        # Check that an event was logged
        events = repo.get_recent_events(limit=5)
        self.assertGreater(len(events), 0)
        # Find a zero-related event
        zero_event = next((e for e in events if "zero" in e.get("code", "").lower()), None)
        self.assertIsNotNone(zero_event, "Expected a zero-related event to be logged")

    def test_zero_with_positive_drift(self) -> None:
        """Test zero with positive drift (signal above calibration zero)."""
        app, repo, state = self._make_app()

        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)

        # Signal above cal zero
        raw_signal = 5.92
        drift_mv = raw_signal - 5.88  # +0.04 mV
        expected_slope = 50.0 / (6.26 - 5.88)

        state.set(stable=True, raw_signal_mv=raw_signal, signal_for_cal=raw_signal)

        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

            drift_mv_returned = body.get("drift_mv")
            zero_offset_lbs = body.get("zero_offset_lbs")

            self.assertAlmostEqual(drift_mv_returned, drift_mv, places=6)
            self.assertGreater(drift_mv_returned, 0.0)
            self.assertGreater(zero_offset_lbs, 0.0)
            self.assertAlmostEqual(zero_offset_lbs, drift_mv * expected_slope, places=3)

    def test_zero_at_exact_calibration_point(self) -> None:
        """When signal exactly matches calibration zero, offset should be ~0."""
        app, repo, state = self._make_app()

        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)

        # Signal exactly at cal zero
        raw_signal = 5.88

        state.set(stable=True, raw_signal_mv=raw_signal, signal_for_cal=raw_signal)

        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

            drift_mv_returned = body.get("drift_mv")
            zero_offset_lbs = body.get("zero_offset_lbs")

            self.assertAlmostEqual(drift_mv_returned, 0.0, places=9)
            self.assertAlmostEqual(zero_offset_lbs, 0.0, places=9)

    def test_zero_incremental_update(self) -> None:
        """Test that repeated zero calls accumulate drift correctly."""
        app, repo, state = self._make_app()

        repo.add_calibration_point(known_weight_lbs=0.0, signal=5.88)
        repo.add_calibration_point(known_weight_lbs=50.0, signal=6.26)

        expected_slope = 50.0 / (6.26 - 5.88)

        # First zero at 5.86 mV
        state.set(stable=True, raw_signal_mv=5.86, signal_for_cal=5.86)
        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body1 = json.loads(resp.data.decode("utf-8"))
            offset1 = body1.get("zero_offset_lbs")

        # Second zero at 5.84 mV (more drift)
        state.set(stable=True, raw_signal_mv=5.84, signal_for_cal=5.84)
        with app.test_client() as client:
            resp = client.post("/api/zero")
            self.assertEqual(resp.status_code, 200)
            body2 = json.loads(resp.data.decode("utf-8"))
            offset2 = body2.get("zero_offset_lbs")

        # Second offset should reflect the new drift (not cumulative from first)
        drift2_mv = 5.84 - 5.88
        expected_offset2 = drift2_mv * expected_slope
        self.assertAlmostEqual(offset2, expected_offset2, places=3)
        self.assertNotAlmostEqual(offset1, offset2, places=3)


if __name__ == "__main__":
    unittest.main()
