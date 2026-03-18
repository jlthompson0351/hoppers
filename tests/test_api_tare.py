from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.app import create_app
from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class ApiTareEndpointTests(unittest.TestCase):
    def _make_app(self) -> tuple:
        tmp = tempfile.mkdtemp(prefix="api-tare-tests-")
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

    def test_tare_adds_current_weight_to_existing_offset_and_logs_source(self) -> None:
        app, repo, state = self._make_app()
        repo.update_config_section(
            "scale",
            lambda section, _: section.update({"tare_offset_lbs": 5.0}),
        )
        state.set(stable=True, total_weight_lbs=12.5)

        with app.test_client() as client:
            resp = client.post(
                "/api/tare",
                headers={
                    "Referer": "http://localhost/",
                    "User-Agent": "tare-test-agent",
                },
            )

        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertTrue(body.get("success"))
        self.assertAlmostEqual(float(body.get("tare_offset_lbs") or 0.0), 17.5, places=6)

        scale = repo.get_latest_config().get("scale") or {}
        self.assertAlmostEqual(float(scale.get("tare_offset_lbs") or 0.0), 17.5, places=6)
        self.assertTrue(scale.get("last_tare_utc"))

        events = repo.get_recent_events(limit=5)
        tare_event = next(e for e in events if e["code"] == "SCALE_TARED")
        details = tare_event["details"]
        self.assertEqual(details["trigger_type"], "web_api")
        self.assertEqual(details["source_surface"], "dashboard")
        self.assertEqual(details["request_path"], "/api/tare")
        self.assertAlmostEqual(float(details["current_weight"]), 12.5, places=6)
        self.assertAlmostEqual(float(details["current_tare"]), 5.0, places=6)
        self.assertAlmostEqual(float(details["previous_tare"]), 5.0, places=6)
        self.assertAlmostEqual(float(details["new_tare"]), 17.5, places=6)

    def test_tare_cooldown_logs_hdmi_source(self) -> None:
        app, repo, state = self._make_app()
        repo.update_config_section(
            "scale",
            lambda section, _: section.update(
                {
                    "tare_offset_lbs": 2.0,
                    "last_tare_utc": datetime.now(timezone.utc).isoformat(),
                }
            ),
        )
        state.set(stable=True, total_weight_lbs=4.0)

        with app.test_client() as client:
            resp = client.post(
                "/api/tare",
                headers={
                    "Referer": "http://localhost/hdmi",
                    "User-Agent": "hdmi-touch-test",
                },
            )

        self.assertEqual(resp.status_code, 429)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertFalse(body.get("success"))

        events = repo.get_recent_events(limit=5)
        cooldown_event = next(e for e in events if e["code"] == "TARE_REJECTED_COOLDOWN")
        details = cooldown_event["details"]
        self.assertEqual(details["trigger_type"], "web_api")
        self.assertEqual(details["source_surface"], "hdmi")
        self.assertEqual(details["request_path"], "/api/tare")
        self.assertAlmostEqual(float(details["current_weight"]), 4.0, places=6)
        self.assertAlmostEqual(float(details["current_tare"]), 2.0, places=6)
        self.assertGreater(float(details["remaining_s"]), 0.0)


class OptoTareTraceTests(unittest.TestCase):
    def test_blocked_opto_tare_logs_channel_context(self) -> None:
        tmp = tempfile.mkdtemp(prefix="opto-tare-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        svc = AcquisitionService(hw=None, repo=repo, state=LiveState())
        cfg = svc._load_cfg()
        cfg.allow_opto_tare = False

        svc._handle_button("tare", raw_mv=0.125, gross_lbs=9.5, cfg=cfg, channel=3)

        events = repo.get_recent_events(limit=5)
        blocked_event = next(e for e in events if e["code"] == "OPTO_TARE_BLOCKED")
        details = blocked_event["details"]
        self.assertEqual(details["trigger_type"], "opto_input")
        self.assertEqual(details["source_surface"], "opto_input")
        self.assertEqual(int(details["opto_channel"]), 3)
        self.assertEqual(details["opto_action"], "tare")
        self.assertAlmostEqual(float(details["gross_lbs"]), 9.5, places=6)
        self.assertAlmostEqual(float(details["raw_signal_mv"]), 0.125, places=6)
        self.assertFalse(details["allow_opto_tare"])
