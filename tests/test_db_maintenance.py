"""Tests for repo.run_maintenance() — 7-day archive-then-prune strategy.

Verifies that old rows are deleted, recent rows are preserved,
config_versions keeps the newest N, and permanent tables are untouched.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.db.migrate import ensure_db
from src.db.repo import AppRepository


def _utc_iso(days_ago: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat(timespec="seconds")


class _RepoTestBase(unittest.TestCase):
    def _make_repo(self) -> AppRepository:
        tmp = tempfile.mkdtemp(prefix="db-maintenance-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        return AppRepository(db_path)

    def _count(self, repo: AppRepository, table: str) -> int:
        with repo._conn() as conn:
            cur = conn.execute(f"SELECT COUNT(*) AS cnt FROM {table};")
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0

    def _insert_event(self, repo: AppRepository, days_ago: int, code: str = "TEST") -> None:
        ts = _utc_iso(days_ago)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO events(ts, level, code, message, details_json) VALUES (?,?,?,?,?);",
                (ts, "INFO", code, "test event", "{}"),
            )

    def _insert_config_version(self, repo: AppRepository, days_ago: int, label: str = "v") -> None:
        ts = _utc_iso(days_ago)
        cfg = json.dumps({"label": label, "ts": ts})
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO config_versions(ts, config_json) VALUES (?,?);",
                (ts, cfg),
            )

    def _insert_counted_event(self, repo: AppRepository, days_ago: int) -> None:
        ts = _utc_iso(days_ago)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO counted_events(timestamp_utc, event_type, source, source_channel, "
                "line_id, machine_id, created_at) VALUES (?,?,?,?,?,?,?);",
                (ts, "basket_dump", "opto_input", 1, "L1", "PLP6", ts),
            )

    def _insert_throughput_event(self, repo: AppRepository, days_ago: int) -> None:
        ts = _utc_iso(days_ago)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO throughput_events(timestamp_utc, processed_lbs, created_at) VALUES (?,?,?);",
                (ts, 100.0, ts),
            )

    def _insert_production_dump(self, repo: AppRepository, days_ago: int) -> None:
        ts = _utc_iso(days_ago)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO production_dumps(ts, prev_stable_lbs, new_stable_lbs, processed_lbs) "
                "VALUES (?,?,?,?);",
                (ts, 250.0, 5.0, 245.0),
            )

    def _insert_set_weight_history(self, repo: AppRepository, days_ago: int) -> None:
        ts = _utc_iso(days_ago)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO set_weight_history("
                "received_at_utc, record_time_set_utc, line_id, machine_id, "
                "set_weight_value, set_weight_unit, set_weight_lbs, source, "
                "metadata_json, applied_to_current, duplicate_event, state_seq, created_at_utc"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);",
                (ts, ts, "L1", "PLP6", 100.0, "lb", 100.0, "webhook", "{}", 1, 0, 1, ts),
            )

    def _insert_outbox_sent(self, repo: AppRepository, days_ago: int) -> None:
        ts = _utc_iso(days_ago)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO job_completion_outbox("
                "created_at_utc, line_id, machine_id, job_id, "
                "job_start_record_time_set_utc, job_end_record_time_set_utc, "
                "payload_json, status, attempt_count, next_retry_at_utc, sent_at_utc"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?);",
                (ts, "L1", "PLP6", f"job-{days_ago}", ts, ts, "{}", "sent", 1, ts, ts),
            )

    def _insert_outbox_pending(self, repo: AppRepository, days_ago: int) -> None:
        ts = _utc_iso(days_ago)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO job_completion_outbox("
                "created_at_utc, line_id, machine_id, job_id, "
                "job_start_record_time_set_utc, job_end_record_time_set_utc, "
                "payload_json, status, attempt_count, next_retry_at_utc"
                ") VALUES (?,?,?,?,?,?,?,?,?,?);",
                (ts, "L1", "PLP6", f"pending-{days_ago}", ts, ts, "{}", "pending", 0, ts),
            )


class TestRunMaintenance(_RepoTestBase):

    def test_events_old_pruned_recent_kept(self):
        repo = self._make_repo()
        self._insert_event(repo, days_ago=10)
        self._insert_event(repo, days_ago=8)
        self._insert_event(repo, days_ago=3)
        self._insert_event(repo, days_ago=1)

        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["events"], 2)
        self.assertEqual(self._count(repo, "events"), 2)

    def test_counted_events_pruned(self):
        repo = self._make_repo()
        self._insert_counted_event(repo, days_ago=14)
        self._insert_counted_event(repo, days_ago=2)

        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["counted_events"], 1)
        self.assertEqual(self._count(repo, "counted_events"), 1)

    def test_throughput_events_pruned(self):
        repo = self._make_repo()
        self._insert_throughput_event(repo, days_ago=20)
        self._insert_throughput_event(repo, days_ago=5)

        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["throughput_events"], 1)
        self.assertEqual(self._count(repo, "throughput_events"), 1)

    def test_production_dumps_pruned(self):
        repo = self._make_repo()
        self._insert_production_dump(repo, days_ago=30)
        self._insert_production_dump(repo, days_ago=1)

        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["production_dumps"], 1)
        self.assertEqual(self._count(repo, "production_dumps"), 1)

    def test_set_weight_history_pruned(self):
        repo = self._make_repo()
        self._insert_set_weight_history(repo, days_ago=15)
        self._insert_set_weight_history(repo, days_ago=0)

        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["set_weight_history"], 1)
        self.assertEqual(self._count(repo, "set_weight_history"), 1)

    def test_outbox_only_sent_rows_pruned(self):
        repo = self._make_repo()
        self._insert_outbox_sent(repo, days_ago=10)
        self._insert_outbox_sent(repo, days_ago=2)
        self._insert_outbox_pending(repo, days_ago=10)

        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["job_completion_outbox"], 1)
        remaining = self._count(repo, "job_completion_outbox")
        self.assertEqual(remaining, 2)

    def test_config_versions_keeps_newest_n(self):
        repo = self._make_repo()
        for i in range(60):
            self._insert_config_version(repo, days_ago=60 - i, label=f"v{i}")

        self.assertEqual(self._count(repo, "config_versions"), 60)

        result = repo.run_maintenance(keep_days=7, keep_config_versions=50)
        self.assertEqual(result["config_versions"], 10)
        self.assertEqual(self._count(repo, "config_versions"), 50)

        with repo._conn() as conn:
            cur = conn.execute(
                "SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1;"
            )
            newest = json.loads(cur.fetchone()["config_json"])
        self.assertEqual(newest["label"], "v59")

    def test_production_totals_never_touched(self):
        repo = self._make_repo()
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO production_totals(period_type, period_start, total_lbs) "
                "VALUES (?,?,?);",
                ("day", "2026-01-01", 5000.0),
            )
        repo.run_maintenance(keep_days=7)
        self.assertEqual(self._count(repo, "production_totals"), 1)

    def test_calibration_points_never_touched(self):
        repo = self._make_repo()
        repo.add_calibration_point(known_weight_lbs=50.0, signal=1.5)
        repo.run_maintenance(keep_days=7)
        self.assertEqual(self._count(repo, "calibration_points"), 1)

    def test_nothing_to_prune_returns_zeros(self):
        repo = self._make_repo()
        self._insert_event(repo, days_ago=1)
        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["events"], 0)
        self.assertEqual(self._count(repo, "events"), 1)

    def test_keep_days_minimum_is_one(self):
        repo = self._make_repo()
        self._insert_event(repo, days_ago=0)
        result = repo.run_maintenance(keep_days=0)
        self.assertEqual(self._count(repo, "events"), 1)

    def test_trends_pruned(self):
        repo = self._make_repo()
        ts_old = _utc_iso(days_ago=10)
        ts_new = _utc_iso(days_ago=1)
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO trends_total(ts, total_lbs, stable, output_mode, output_cmd) "
                "VALUES (?,?,?,?,?);",
                (ts_old, 100.0, 1, "0_10V", 5.0),
            )
            conn.execute(
                "INSERT INTO trends_total(ts, total_lbs, stable, output_mode, output_cmd) "
                "VALUES (?,?,?,?,?);",
                (ts_new, 200.0, 1, "0_10V", 7.0),
            )
        result = repo.run_maintenance(keep_days=7)
        self.assertEqual(result["trends_total"], 1)
        self.assertEqual(self._count(repo, "trends_total"), 1)


if __name__ == "__main__":
    unittest.main()
