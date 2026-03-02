"""Tests for PIN-protected HDMI manual override endpoint."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.app import create_app
from src.app.routes import _hash_manager_override_pin
from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class ApiJobOverrideTests(unittest.TestCase):
    def _make_app(self, *, pin_hash: str = "", mode: str = "target_signal_mode", enabled: bool = True):
        tmp = tempfile.mkdtemp(prefix="api-job-override-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update(
                {
                    "enabled": bool(enabled),
                    "mode": str(mode),
                    "override_pin_hash": str(pin_hash or ""),
                }
            ),
        )
        state = LiveState()
        svc = AcquisitionService(hw=None, repo=repo, state=state)

        app = create_app()
        app.config["REPO"] = repo
        app.config["LIVE_STATE"] = state
        app.config["ACQ_SERVICE"] = svc
        app.config["TESTING"] = True
        return app, repo, svc

    def test_override_requires_pin_configuration(self) -> None:
        app, _repo, _svc = self._make_app(pin_hash="")
        with app.test_client() as client:
            resp = client.post(
                "/api/job/override",
                data=json.dumps({"pin": "1234", "set_weight": 100.0}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 503)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertFalse(body.get("success"))
        self.assertIn("PIN", body.get("error", ""))

    def test_override_rejects_invalid_pin(self) -> None:
        app, _repo, _svc = self._make_app(pin_hash=_hash_manager_override_pin("1234"))
        with app.test_client() as client:
            resp = client.post(
                "/api/job/override",
                data=json.dumps({"pin": "0000", "set_weight": 100.0}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 401)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertFalse(body.get("success"))

    def test_override_rejects_when_target_mode_disabled(self) -> None:
        app, _repo, _svc = self._make_app(
            pin_hash=_hash_manager_override_pin("1234"),
            mode="legacy_weight_mapping",
            enabled=False,
        )
        with app.test_client() as client:
            resp = client.post(
                "/api/job/override",
                data=json.dumps({"pin": "1234", "set_weight": 100.0}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 409)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertFalse(body.get("success"))

    def test_override_updates_current_and_history_with_override_marker(self) -> None:
        app, repo, svc = self._make_app(pin_hash=_hash_manager_override_pin("1234"))
        with app.test_client() as client:
            resp = client.post(
                "/api/job/override",
                data=json.dumps({"pin": "1234", "set_weight": 100.0}),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertTrue(body.get("success"))
        self.assertTrue(body.get("overridden"))
        self.assertEqual(body.get("action"), "activated")

        status = svc.get_job_control_status()
        self.assertTrue(status["active"])
        self.assertAlmostEqual(float(status["set_weight"]), 100.0)

        current = repo.get_set_weight_current("default_line", "default_machine")
        self.assertIsNotNone(current)
        self.assertAlmostEqual(float(current.set_weight_lbs), 100.0)
        self.assertIn("manual_override:overridden:hdmi", str(current.source))

        history = repo.get_set_weight_history_range(
            line_id="default_line",
            machine_id="default_machine",
            limit=5,
        )
        self.assertGreaterEqual(len(history), 1)
        row = history[0]
        self.assertIn("manual_override:overridden:hdmi", str(row.get("source", "")))
        metadata = row.get("metadata") or {}
        self.assertTrue(metadata.get("manual_override"))
        self.assertTrue(metadata.get("overridden"))
        self.assertEqual(metadata.get("reason"), "overridden")
        self.assertTrue(row.get("applied_to_current"))

    def test_settings_post_hashes_valid_override_pin(self) -> None:
        app, repo, _svc = self._make_app(pin_hash="")
        with app.test_client() as client:
            resp = client.post("/settings", data={"job_override_pin": "2468"})
        self.assertEqual(resp.status_code, 302)
        cfg = repo.get_latest_config()
        saved_hash = str((cfg.get("job_control") or {}).get("override_pin_hash", "") or "")
        self.assertEqual(saved_hash, _hash_manager_override_pin("2468"))

    def test_settings_post_keeps_existing_hash_when_pin_blank(self) -> None:
        existing_hash = _hash_manager_override_pin("1357")
        app, repo, _svc = self._make_app(pin_hash=existing_hash)
        with app.test_client() as client:
            resp = client.post("/settings", data={"job_override_pin": "   "})
        self.assertEqual(resp.status_code, 302)
        cfg = repo.get_latest_config()
        saved_hash = str((cfg.get("job_control") or {}).get("override_pin_hash", "") or "")
        self.assertEqual(saved_hash, existing_hash)


if __name__ == "__main__":
    unittest.main()
