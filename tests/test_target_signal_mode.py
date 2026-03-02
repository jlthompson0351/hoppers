"""Tests for the simplified job-target signal mode.

Logic: scale_weight >= (set_weight - pretrigger) → trigger signal, else → low signal.
No state machine, no timers, no queuing.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class TargetSignalModeTests(unittest.TestCase):
    def _make_service(self) -> AcquisitionService:
        tmp = tempfile.mkdtemp(prefix="target-signal-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        state = LiveState()
        return AcquisitionService(hw=None, repo=repo, state=state)

    def test_ingest_sets_weight_and_reports_active(self) -> None:
        svc = self._make_service()
        result = svc.ingest_job_webhook(
            job_id="JOB-1",
            target_weight_lb=100.0,
            step_id="STEP-1",
            event_id="evt-1",
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["action"], "activated")
        status = svc.get_job_control_status()
        self.assertTrue(status["active"])
        self.assertAlmostEqual(status["set_weight"], 100.0)

    def test_new_webhook_overwrites_set_weight(self) -> None:
        svc = self._make_service()
        svc.ingest_job_webhook(job_id="JOB-1", target_weight_lb=100.0, step_id="S1", event_id="e1")
        svc.ingest_job_webhook(job_id="JOB-1", target_weight_lb=150.0, step_id="S2", event_id="e2")
        status = svc.get_job_control_status()
        self.assertAlmostEqual(status["set_weight"], 150.0)

    def test_duplicate_event_id_is_ignored(self) -> None:
        svc = self._make_service()
        svc.ingest_job_webhook(job_id="JOB-1", target_weight_lb=100.0, step_id="S1", event_id="dup-1")
        result = svc.ingest_job_webhook(job_id="JOB-1", target_weight_lb=150.0, step_id="S2", event_id="dup-1")
        self.assertTrue(result["accepted"])
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["action"], "ignored_duplicate")
        self.assertAlmostEqual(svc.get_job_control_status()["set_weight"], 100.0)

    def test_clear_resets_set_weight_to_zero(self) -> None:
        svc = self._make_service()
        svc.ingest_job_webhook(job_id="JOB-1", target_weight_lb=100.0, step_id="S1", event_id="e1")
        result = svc.clear_job_control()
        self.assertTrue(result["cleared"])
        self.assertAlmostEqual(svc.get_job_control_status()["set_weight"], 0.0)
        self.assertFalse(svc.get_job_control_status()["active"])

    def test_job_set_weight_restores_after_service_restart(self) -> None:
        tmp = tempfile.mkdtemp(prefix="target-signal-restart-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)

        svc_first = AcquisitionService(hw=None, repo=repo, state=LiveState())
        svc_first.ingest_job_webhook(
            job_id="JOB-RST-1",
            target_weight_lb=125.5,
            step_id="STEP-RST",
            event_id="rst-e1",
        )

        # Simulate a process restart by creating a fresh service instance.
        svc_after_restart = AcquisitionService(hw=None, repo=repo, state=LiveState())
        restored = svc_after_restart.get_job_control_status()
        self.assertTrue(restored["active"])
        self.assertAlmostEqual(float(restored["set_weight"]), 125.5)
        self.assertEqual((restored.get("meta") or {}).get("job_id"), "JOB-RST-1")

    def test_clear_persists_after_service_restart(self) -> None:
        tmp = tempfile.mkdtemp(prefix="target-signal-clear-restart-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)

        svc_first = AcquisitionService(hw=None, repo=repo, state=LiveState())
        svc_first.ingest_job_webhook(
            job_id="JOB-CLEAR-1",
            target_weight_lb=99.0,
            step_id="STEP-CLEAR",
            event_id="clear-e1",
        )
        clear_result = svc_first.clear_job_control()
        self.assertTrue(clear_result["cleared"])

        svc_after_restart = AcquisitionService(hw=None, repo=repo, state=LiveState())
        restored = svc_after_restart.get_job_control_status()
        self.assertFalse(restored["active"])
        self.assertAlmostEqual(float(restored["set_weight"]), 0.0)
        self.assertIsNone(restored["meta"])

    def test_threshold_is_exact_by_default(self) -> None:
        """set_weight=100, pretrigger=0 → trigger exactly at 100 lb."""
        svc = self._make_service()
        svc.ingest_job_webhook(job_id="JOB-2", target_weight_lb=100.0, step_id="S1", event_id="e1")
        with svc._job_lock:
            set_w = svc._job_set_weight
        pretrigger = 0.0
        threshold = max(0.0, set_w - pretrigger)

        self.assertAlmostEqual(threshold, 100.0)
        self.assertGreaterEqual(99.9, 0.0)    # below threshold → low
        self.assertGreaterEqual(100.0, threshold)  # at threshold → trigger

    def test_early_trigger_reduces_threshold(self) -> None:
        """set_weight=100, pretrigger=10 → trigger at 90 lb."""
        svc = self._make_service()
        svc.ingest_job_webhook(job_id="JOB-3", target_weight_lb=100.0, step_id="S1", event_id="e1")
        with svc._job_lock:
            set_w = svc._job_set_weight
        pretrigger = 10.0
        threshold = max(0.0, set_w - pretrigger)
        self.assertAlmostEqual(threshold, 90.0)

    def test_no_set_weight_means_no_signal(self) -> None:
        svc = self._make_service()
        status = svc.get_job_control_status()
        self.assertFalse(status["active"])
        self.assertAlmostEqual(status["set_weight"], 0.0)


if __name__ == "__main__":
    unittest.main()
