from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.app import create_app
from src.core.throughput_cycle import ThroughputCycleEvent
from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class ThroughputGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="throughput-guard-tests-")
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self.db_path = Path(self._tmp) / "app.sqlite3"
        ensure_db(self.db_path)
        self.repo = AppRepository(self.db_path)
        self.service = AcquisitionService(hw=None, repo=self.repo, state=LiveState())

    @staticmethod
    def _cfg(max_lb: float) -> SimpleNamespace:
        return SimpleNamespace(
            range_max_lb=float(max_lb),
            throughput_device_id="hopper-a",
            throughput_hopper_id="line-1",
            zero_target_lb=0.0,
            zero_offset_mv=0.35,
            zero_offset_lbs=39.2,
            throughput_min_processed_lb=5.0,
        )

    def test_rejects_cycle_above_max_and_logs_anomaly(self) -> None:
        accepted = self.service._persist_throughput_cycle_event(
            throughput_evt=ThroughputCycleEvent(
                processed_lbs=301.0,
                full_lbs=305.0,
                empty_lbs=4.0,
                duration_ms=121000,
                confidence=0.92,
            ),
            cfg=self._cfg(300.0),
            event_ts="2026-02-26T13:52:02+00:00",
            throughput_full_lbs=305.0,
            throughput_empty_lbs=4.0,
            raw_mv=6.10,
            adjusted_signal_mv=5.75,
            filtered_lbs=301.0,
            target_relative_lbs=301.0,
            throughput_full_min_relative_lb=15.0,
            target_set_weight_lbs=190.0,
        )

        self.assertFalse(accepted)
        totals = self.repo.get_throughput_totals()
        self.assertEqual(totals["event_count"], 0)
        self.assertAlmostEqual(totals["total_processed_lbs"], 0.0, places=9)
        self.assertIsNone(self.repo.get_last_dump())

        events = self.repo.get_recent_events(limit=20)
        rejected = next(e for e in events if e["code"] == "THROUGHPUT_CYCLE_REJECTED_MAX_WEIGHT")
        details = rejected["details"]
        self.assertAlmostEqual(float(details["processed_lbs"]), 301.0, places=6)
        self.assertAlmostEqual(float(details["max_allowed_lbs"]), 300.0, places=6)
        self.assertIn("raw_signal_mv", details)
        self.assertIn("adjusted_signal_mv", details)
        self.assertIn("zero_offset_mv", details)
        self.assertIn("target_relative_lbs", details)

    def test_accepts_cycle_below_or_equal_to_max(self) -> None:
        below_accepted = self.service._persist_throughput_cycle_event(
            throughput_evt=ThroughputCycleEvent(
                processed_lbs=250.0,
                full_lbs=252.5,
                empty_lbs=2.5,
                duration_ms=118000,
                confidence=0.95,
            ),
            cfg=self._cfg(300.0),
            event_ts="2026-02-26T14:00:00+00:00",
            throughput_full_lbs=252.5,
            throughput_empty_lbs=2.5,
            raw_mv=5.50,
            adjusted_signal_mv=5.15,
            filtered_lbs=250.0,
            target_relative_lbs=250.0,
            throughput_full_min_relative_lb=15.0,
            target_set_weight_lbs=175.0,
        )
        self.assertTrue(below_accepted)

        boundary_accepted = self.service._persist_throughput_cycle_event(
            throughput_evt=ThroughputCycleEvent(
                processed_lbs=300.0,
                full_lbs=304.0,
                empty_lbs=4.0,
                duration_ms=120000,
                confidence=0.90,
            ),
            cfg=self._cfg(300.0),
            event_ts="2026-02-26T14:05:00+00:00",
            throughput_full_lbs=304.0,
            throughput_empty_lbs=4.0,
            raw_mv=5.95,
            adjusted_signal_mv=5.60,
            filtered_lbs=300.0,
            target_relative_lbs=300.0,
            throughput_full_min_relative_lb=15.0,
            target_set_weight_lbs=190.0,
        )
        self.assertTrue(boundary_accepted)

        totals = self.repo.get_throughput_totals()
        self.assertEqual(totals["event_count"], 2)
        self.assertAlmostEqual(totals["total_processed_lbs"], 550.0, places=6)

        last_dump = self.repo.get_last_dump()
        self.assertIsNotNone(last_dump)
        assert last_dump is not None
        self.assertAlmostEqual(last_dump["processed_lbs"], 300.0, places=6)
        self.assertAlmostEqual(float(last_dump["target_set_weight_lbs"]), 190.0, places=6)

        events = self.repo.get_throughput_events_range(order_desc=False)
        self.assertEqual(len(events), 2)
        self.assertAlmostEqual(float(events[0]["target_set_weight_lbs"]), 175.0, places=6)
        self.assertAlmostEqual(float(events[1]["target_set_weight_lbs"]), 190.0, places=6)
        self.assertEqual(events[0]["dump_type"], "full")
        self.assertEqual(events[1]["dump_type"], "full")
        self.assertEqual(last_dump["dump_type"], "full")

        codes = [e["code"] for e in self.repo.get_recent_events(limit=20)]
        self.assertIn("THROUGHPUT_CYCLE_COMPLETE", codes)
        self.assertNotIn("THROUGHPUT_CYCLE_REJECTED_MAX_WEIGHT", codes)


class SettingsMaxWeightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="settings-max-weight-tests-")
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self.db_path = Path(self._tmp) / "app.sqlite3"
        ensure_db(self.db_path)
        self.repo = AppRepository(self.db_path)

        app = create_app()
        app.config["REPO"] = self.repo
        app.config["LIVE_STATE"] = LiveState()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_settings_page_exposes_and_persists_max_lb(self) -> None:
        get_resp = self.client.get("/settings")
        self.assertEqual(get_resp.status_code, 200)
        self.assertIn('name="max_lb"', get_resp.data.decode("utf-8"))

        post_resp = self.client.post(
            "/settings",
            data={
                "max_lb": "275.5",
                "output_mode": "0_10V",
                "output_channel": "1",
                "safe_output": "0.0",
            },
        )
        self.assertEqual(post_resp.status_code, 302)

        cfg = self.repo.get_latest_config()
        range_cfg = cfg.get("range") or {}
        self.assertAlmostEqual(float(range_cfg.get("max_lb", 0.0)), 275.5, places=6)


if __name__ == "__main__":
    unittest.main()
