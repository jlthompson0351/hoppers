from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class SetWeightPersistenceTests(unittest.TestCase):
    def _make_repo(self) -> AppRepository:
        tmp = tempfile.mkdtemp(prefix="set-weight-persistence-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        return AppRepository(db_path)

    def test_repo_upserts_current_per_scope(self) -> None:
        repo = self._make_repo()
        repo.record_set_weight_receipt(
            line_id="line-a",
            machine_id="machine-a",
            set_weight_value=100.0,
            set_weight_unit="lb",
            set_weight_lbs=100.0,
            source="test",
            source_event_id="evt-a1",
            state_seq=1,
        )
        repo.record_set_weight_receipt(
            line_id="line-b",
            machine_id="machine-b",
            set_weight_value=55.0,
            set_weight_unit="lb",
            set_weight_lbs=55.0,
            source="test",
            source_event_id="evt-b1",
            state_seq=1,
        )
        repo.record_set_weight_receipt(
            line_id="line-a",
            machine_id="machine-a",
            set_weight_value=120.0,
            set_weight_unit="lb",
            set_weight_lbs=120.0,
            source="test",
            source_event_id="evt-a2",
            state_seq=2,
        )

        current_a = repo.get_set_weight_current("line-a", "machine-a")
        current_b = repo.get_set_weight_current("line-b", "machine-b")
        self.assertIsNotNone(current_a)
        self.assertIsNotNone(current_b)
        self.assertAlmostEqual(float(current_a.set_weight_lbs), 120.0)
        self.assertAlmostEqual(float(current_b.set_weight_lbs), 55.0)

    def test_repo_appends_history_for_duplicate_event(self) -> None:
        repo = self._make_repo()
        first = repo.record_set_weight_receipt(
            line_id="line-1",
            machine_id="machine-1",
            set_weight_value=100.0,
            set_weight_unit="lb",
            set_weight_lbs=100.0,
            source="test",
            source_event_id="dup-1",
            state_seq=1,
            received_at_utc="2026-03-02T12:00:00+00:00",
        )
        second = repo.record_set_weight_receipt(
            line_id="line-1",
            machine_id="machine-1",
            set_weight_value=150.0,
            set_weight_unit="lb",
            set_weight_lbs=150.0,
            source="test",
            source_event_id="dup-1",
            state_seq=2,
            received_at_utc="2026-03-02T12:00:10+00:00",
        )

        self.assertTrue(first.applied_to_current)
        self.assertFalse(first.duplicate_event)
        self.assertFalse(second.applied_to_current)
        self.assertTrue(second.duplicate_event)

        current = repo.get_set_weight_current("line-1", "machine-1")
        self.assertIsNotNone(current)
        self.assertAlmostEqual(float(current.set_weight_lbs), 100.0)

        history = repo.get_set_weight_history_range(line_id="line-1", machine_id="machine-1")
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0]["duplicate_event"])
        self.assertFalse(history[0]["applied_to_current"])
        self.assertAlmostEqual(float(history[0]["set_weight_lbs"]), 150.0)
        self.assertAlmostEqual(float(history[1]["set_weight_lbs"]), 100.0)

    def test_repo_history_range_filters_dates(self) -> None:
        repo = self._make_repo()
        repo.record_set_weight_receipt(
            line_id="line-1",
            machine_id="machine-1",
            set_weight_value=10.0,
            set_weight_unit="lb",
            set_weight_lbs=10.0,
            source="test",
            source_event_id="evt-1",
            state_seq=1,
            received_at_utc="2026-03-02T10:00:00+00:00",
        )
        repo.record_set_weight_receipt(
            line_id="line-1",
            machine_id="machine-1",
            set_weight_value=20.0,
            set_weight_unit="lb",
            set_weight_lbs=20.0,
            source="test",
            source_event_id="evt-2",
            state_seq=2,
            received_at_utc="2026-03-02T11:00:00+00:00",
        )
        repo.record_set_weight_receipt(
            line_id="line-1",
            machine_id="machine-1",
            set_weight_value=30.0,
            set_weight_unit="lb",
            set_weight_lbs=30.0,
            source="test",
            source_event_id="evt-3",
            state_seq=3,
            received_at_utc="2026-03-02T12:00:00+00:00",
        )

        history = repo.get_set_weight_history_range(
            line_id="line-1",
            machine_id="machine-1",
            start_utc="2026-03-02T10:30:00+00:00",
            end_utc="2026-03-02T12:00:00+00:00",
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["source_event_id"], "evt-2")

    def test_service_restore_prefers_current_table_over_legacy_config(self) -> None:
        repo = self._make_repo()
        svc_first = AcquisitionService(hw=None, repo=repo, state=LiveState())
        svc_first.ingest_job_webhook(
            job_id="JOB-1",
            target_weight_lb=42.0,
            event_id="evt-42",
            line_id="default_line",
            machine_id="default_machine",
        )

        # Write conflicting legacy config state; startup should prefer set_weight_current.
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update(
                {
                    "set_weight": 999.0,
                    "active": True,
                    "meta": {"job_id": "LEGACY"},
                    "state_seq": 999,
                }
            ),
        )

        svc_after_restart = AcquisitionService(hw=None, repo=repo, state=LiveState())
        restored = svc_after_restart.get_job_control_status()
        self.assertTrue(restored["active"])
        self.assertAlmostEqual(float(restored["set_weight"]), 42.0)
        self.assertEqual((restored.get("meta") or {}).get("job_id"), "JOB-1")

    def test_service_restore_falls_back_to_legacy_when_current_missing(self) -> None:
        repo = self._make_repo()
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update(
                {
                    "set_weight": 88.0,
                    "active": True,
                    "meta": {"job_id": "LEGACY-ONLY"},
                    "state_seq": 5,
                }
            ),
        )

        svc = AcquisitionService(hw=None, repo=repo, state=LiveState())
        restored = svc.get_job_control_status()
        self.assertTrue(restored["active"])
        self.assertAlmostEqual(float(restored["set_weight"]), 88.0)
        self.assertEqual((restored.get("meta") or {}).get("job_id"), "LEGACY-ONLY")


if __name__ == "__main__":
    unittest.main()
