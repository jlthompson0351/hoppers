from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.app import create_app
from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.state import LiveState


class ThroughputApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="throughput-api-tests-")
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self.db_path = Path(self._tmp) / "app.sqlite3"
        ensure_db(self.db_path)
        self.repo = AppRepository(self.db_path)

        cfg = self.repo.get_latest_config()
        cfg.setdefault("ui", {})
        cfg["ui"]["timezone"] = "America/New_York"
        self.repo.save_config(cfg)

        self.repo.add_throughput_event(
            timestamp_utc="2026-02-02T04:30:00+00:00",  # 2026-02-01 23:30 local
            processed_lbs=100.0,
            full_lbs=101.0,
            empty_lbs=1.0,
            duration_ms=120000,
            confidence=0.93,
            device_id="hopper-a",
        )
        self.repo.add_throughput_event(
            timestamp_utc="2026-02-02T05:30:00+00:00",  # 2026-02-02 00:30 local
            processed_lbs=120.0,
            full_lbs=121.2,
            empty_lbs=1.2,
            duration_ms=118000,
            confidence=0.95,
            device_id="hopper-a",
        )
        self.repo.add_throughput_event(
            timestamp_utc="2026-02-03T12:00:00+00:00",
            processed_lbs=90.0,
            full_lbs=91.0,
            empty_lbs=1.0,
            duration_ms=110000,
            confidence=0.89,
            device_id="hopper-b",
        )
        self.repo.add_throughput_event(
            timestamp_utc="2025-12-31T23:30:00+00:00",
            processed_lbs=80.0,
            full_lbs=81.0,
            empty_lbs=1.0,
            duration_ms=98000,
            confidence=0.87,
            device_id="hopper-a",
        )
        self.repo.add_throughput_event(
            timestamp_utc="2026-03-01T05:10:00+00:00",  # 2026-03-01 00:10 local
            processed_lbs=130.0,
            full_lbs=131.5,
            empty_lbs=1.5,
            duration_ms=126000,
            confidence=0.96,
            device_id="hopper-a",
        )

        app = create_app()
        app.config["REPO"] = self.repo
        app.config["LIVE_STATE"] = LiveState()
        self.client = app.test_client()

    def test_summary_groups_by_site_timezone_day_boundaries(self) -> None:
        resp = self.client.get(
            "/throughput/summary?bucket=daily&start=2026-02-01&end=2026-02-03&deviceId=hopper-a"
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data.decode("utf-8"))

        self.assertEqual(body["timezone"], "America/New_York")
        self.assertEqual(body["event_count"], 2)
        self.assertAlmostEqual(body["total_processed_lbs"], 220.0, places=6)
        self.assertAlmostEqual(body["avg_per_event_lbs"], 110.0, places=6)

        series = {row["bucket_start"]: row for row in body["series"]}
        self.assertIn("2026-02-01", series)
        self.assertIn("2026-02-02", series)
        self.assertAlmostEqual(series["2026-02-01"]["processed_lbs"], 100.0, places=6)
        self.assertAlmostEqual(series["2026-02-02"]["processed_lbs"], 120.0, places=6)

    def test_events_endpoint_paginates_and_sorts_newest_first(self) -> None:
        resp = self.client.get("/throughput/events?start=2026-02-01&end=2026-02-04&page=1&pageSize=2")
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data.decode("utf-8"))

        self.assertEqual(body["page"], 1)
        self.assertEqual(body["pageSize"], 2)
        self.assertEqual(body["total"], 3)
        self.assertEqual(len(body["events"]), 2)
        self.assertEqual(body["events"][0]["timestamp"], "2026-02-03T12:00:00+00:00")
        self.assertEqual(body["events"][1]["timestamp"], "2026-02-02T05:30:00+00:00")

        resp_filtered = self.client.get(
            "/throughput/events?start=2026-02-01&end=2026-02-04&deviceId=hopper-a&page=1&pageSize=50"
        )
        self.assertEqual(resp_filtered.status_code, 200)
        filtered = json.loads(resp_filtered.data.decode("utf-8"))
        self.assertEqual(filtered["total"], 2)
        self.assertEqual(len(filtered["events"]), 2)
        self.assertTrue(all(evt["device_id"] == "hopper-a" for evt in filtered["events"]))

    def test_summary_supports_week_month_year_buckets(self) -> None:
        weekly_resp = self.client.get(
            "/throughput/summary?bucket=weekly&start=2026-01-26&end=2026-02-09&deviceId=hopper-a"
        )
        self.assertEqual(weekly_resp.status_code, 200)
        weekly = json.loads(weekly_resp.data.decode("utf-8"))
        self.assertEqual(weekly["event_count"], 2)
        self.assertAlmostEqual(weekly["total_processed_lbs"], 220.0, places=6)
        weekly_series = {row["bucket_start"]: row for row in weekly["series"]}
        self.assertAlmostEqual(weekly_series["2026-01-26"]["processed_lbs"], 100.0, places=6)
        self.assertAlmostEqual(weekly_series["2026-02-02"]["processed_lbs"], 120.0, places=6)

        monthly_resp = self.client.get(
            "/throughput/summary?bucket=monthly&start=2026-01-01&end=2026-04-01&deviceId=hopper-a"
        )
        self.assertEqual(monthly_resp.status_code, 200)
        monthly = json.loads(monthly_resp.data.decode("utf-8"))
        self.assertEqual(monthly["event_count"], 3)
        self.assertAlmostEqual(monthly["total_processed_lbs"], 350.0, places=6)
        monthly_series = {row["bucket_start"]: row for row in monthly["series"]}
        self.assertAlmostEqual(monthly_series["2026-02-01"]["processed_lbs"], 220.0, places=6)
        self.assertAlmostEqual(monthly_series["2026-03-01"]["processed_lbs"], 130.0, places=6)

        yearly_resp = self.client.get(
            "/throughput/summary?bucket=yearly&start=2025-01-01&end=2027-01-01&deviceId=hopper-a"
        )
        self.assertEqual(yearly_resp.status_code, 200)
        yearly = json.loads(yearly_resp.data.decode("utf-8"))
        self.assertEqual(yearly["event_count"], 4)
        self.assertAlmostEqual(yearly["total_processed_lbs"], 430.0, places=6)
        yearly_series = {row["bucket_start"]: row for row in yearly["series"]}
        self.assertAlmostEqual(yearly_series["2025-01-01"]["processed_lbs"], 80.0, places=6)
        self.assertAlmostEqual(yearly_series["2026-01-01"]["processed_lbs"], 350.0, places=6)

    def test_csv_export_respects_filters_and_order(self) -> None:
        resp = self.client.get("/throughput/events.csv?start=2026-01-01&end=2026-04-01&deviceId=hopper-a")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "text/csv")

        rows = list(csv.reader(io.StringIO(resp.data.decode("utf-8"))))
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(
            rows[0],
            [
                "id",
                "timestamp_utc",
                "processed_lbs",
                "full_lbs",
                "empty_lbs",
                "duration_ms",
                "confidence",
                "device_id",
                "hopper_id",
                "created_at",
            ],
        )
        # Filter range includes exactly three hopper-a events in 2026.
        self.assertEqual(len(rows) - 1, 3)
        # CSV is newest-first by timestamp.
        self.assertEqual(rows[1][1], "2026-03-01T05:10:00+00:00")
        self.assertEqual(rows[1][7], "hopper-a")

    def test_delete_events_endpoint_supports_filtered_and_all_delete(self) -> None:
        filtered_delete = self.client.post(
            "/throughput/events/delete",
            json={
                "start": "2026-02-01",
                "end": "2026-02-04",
                "deviceId": "hopper-a",
            },
        )
        self.assertEqual(filtered_delete.status_code, 200)
        filtered_delete_body = json.loads(filtered_delete.data.decode("utf-8"))
        self.assertEqual(filtered_delete_body["deleted"], 2)

        remaining_after_filtered = self.client.get(
            "/throughput/events?start=2025-01-01&end=2027-01-01&page=1&pageSize=100"
        )
        self.assertEqual(remaining_after_filtered.status_code, 200)
        remaining_after_filtered_body = json.loads(remaining_after_filtered.data.decode("utf-8"))
        self.assertEqual(remaining_after_filtered_body["total"], 3)

        guard_resp = self.client.post("/throughput/events/delete", json={"deleteAll": True})
        self.assertEqual(guard_resp.status_code, 400)

        delete_all = self.client.post(
            "/throughput/events/delete",
            json={"deleteAll": True, "confirmAll": True},
        )
        self.assertEqual(delete_all.status_code, 200)
        delete_all_body = json.loads(delete_all.data.decode("utf-8"))
        self.assertEqual(delete_all_body["deleted"], 3)

        remaining_after_all = self.client.get(
            "/throughput/events?start=2025-01-01&end=2027-01-01&page=1&pageSize=100"
        )
        self.assertEqual(remaining_after_all.status_code, 200)
        remaining_after_all_body = json.loads(remaining_after_all.data.decode("utf-8"))
        self.assertEqual(remaining_after_all_body["total"], 0)


if __name__ == "__main__":
    unittest.main()
