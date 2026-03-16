from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class RezeroWarningTests(unittest.TestCase):
    def _make_service(self) -> AcquisitionService:
        tmp = tempfile.mkdtemp(prefix="rezero-warning-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        return AcquisitionService(hw=None, repo=repo, state=LiveState())

    def test_warning_activates_after_dump_cycle_when_stable_and_outside_tolerance(self) -> None:
        svc = self._make_service()
        cfg = svc._load_cfg()
        cfg.post_dump_rezero_min_delay_s = 0.0
        cfg.post_dump_rezero_empty_threshold_lb = 4.0
        cfg.rezero_warning_threshold_lb = 20.0
        svc._arm_rezero_warning_cycle(now_s=10.0)
        svc._update_rezero_warning_state(
            now_s=10.0,
            now_utc="2026-03-16T17:00:00+00:00",
            target_relative_lbs=21.5,
            is_stable=True,
            cfg=cfg,
        )
        self.assertTrue(svc._rezero_warning_active)
        self.assertTrue(svc._job_rezero_warning_seen)
        self.assertEqual(svc._rezero_warning_reason, "outside_tolerance")

    def test_warning_clears_once_weight_returns_inside_tolerance(self) -> None:
        svc = self._make_service()
        cfg = svc._load_cfg()
        cfg.rezero_warning_threshold_lb = 20.0
        svc._set_rezero_warning(
            reason="outside_tolerance",
            weight_lbs=21.5,
            threshold_lbs=20.0,
            now_utc="2026-03-16T17:00:00+00:00",
        )
        svc._update_rezero_warning_state(
            now_s=12.0,
            now_utc="2026-03-16T17:00:12+00:00",
            target_relative_lbs=0.3,
            is_stable=True,
            cfg=cfg,
        )
        self.assertFalse(svc._rezero_warning_active)
        self.assertEqual(svc._rezero_warning_reason, "idle")


if __name__ == "__main__":
    unittest.main()
