"""Tests: /api/snapshot exposes the simplified jobControl block."""
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


class SnapshotJobControlTests(unittest.TestCase):
    def _make_app(self) -> tuple:
        tmp = tempfile.mkdtemp(prefix="snapshot-job-control-tests-")
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

    def test_snapshot_includes_job_control_block(self) -> None:
        app, repo, state = self._make_app()
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update(
                {
                    "enabled": True,
                    "mode": "target_signal_mode",
                    "trigger_mode": "exact",
                }
            ),
        )
        state.set(
            job_control_enabled=True,
            job_control_mode="target_signal_mode",
            job_control_trigger_mode="exact",
            job_control_pretrigger_lb=0.0,
            job_set_weight=100.0,
            job_active=True,
            job_meta={
                "job_id": "JOB-9",
                "step_id": "STEP-3",
                "event_id": "evt-9-3",
                "target_weight_lb": 100.0,
            },
        )

        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

        self.assertIn("jobControl", body)
        job = body["jobControl"]
        self.assertTrue(job["enabled"])
        self.assertEqual(job["mode"], "target_signal_mode")
        self.assertTrue(job["active"])
        self.assertAlmostEqual(float(job["set_weight"]), 100.0)

    def test_snapshot_job_control_defaults_when_no_state(self) -> None:
        app, _repo, _state = self._make_app()
        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))
        job = body.get("jobControl", {})
        self.assertFalse(job.get("active", True))
        self.assertAlmostEqual(float(job.get("set_weight", 0.0)), 0.0)


if __name__ == "__main__":
    unittest.main()
