from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class _StubSuccessResponse:
    status = 204

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class JobCompletionWebhookTests(unittest.TestCase):
    def _make_repo_and_service(self) -> tuple[AppRepository, AcquisitionService]:
        tmp = tempfile.mkdtemp(prefix="job-completion-webhook-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        svc = AcquisitionService(hw=None, repo=repo, state=LiveState())
        return repo, svc

    def test_transition_enqueues_summary_payload(self) -> None:
        repo, svc = self._make_repo_and_service()
        line_id = "line-1"
        machine_id = "machine-1"

        repo.set_job_lifecycle_state(
            line_id=line_id,
            machine_id=machine_id,
            active_job_id="JOB-1",
            active_job_started_record_time_set_utc="2026-03-05T12:00:00+00:00",
            active_job_last_record_time_set_utc="2026-03-05T12:05:00+00:00",
            active_job_first_erp_timestamp_utc="2026-03-05T12:00:00+00:00",
            active_job_last_erp_timestamp_utc="2026-03-05T12:05:00+00:00",
            override_count=0,
            last_set_weight_lbs=125.0,
            last_set_weight_unit="lb",
            last_source_event_id="job-1-initial",
        )
        repo.record_set_weight_receipt(
            line_id=line_id,
            machine_id=machine_id,
            set_weight_value=125.0,
            set_weight_unit="lb",
            set_weight_lbs=125.0,
            source="api_job_webhook:test",
            source_event_id="job-1-initial",
            state_seq=1,
            received_at_utc="2026-03-05T12:00:00+00:00",
            record_time_set_utc="2026-03-05T12:00:00+00:00",
            job_id="JOB-1",
        )
        repo.record_set_weight_receipt(
            line_id=line_id,
            machine_id=machine_id,
            set_weight_value=130.0,
            set_weight_unit="lb",
            set_weight_lbs=130.0,
            source="manual_override:overridden:hdmi:test",
            source_event_id=None,
            state_seq=2,
            received_at_utc="2026-03-05T12:03:00+00:00",
            record_time_set_utc="2026-03-05T12:03:00+00:00",
            job_id="MANUAL_OVERRIDE",
            metadata={"manual_override": True, "overridden": True},
        )
        repo.increment_job_lifecycle_override(
            line_id=line_id,
            machine_id=machine_id,
            last_record_time_set_utc="2026-03-05T12:03:00+00:00",
            last_set_weight_lbs=130.0,
            last_set_weight_unit="lb",
        )
        repo.add_throughput_event(
            timestamp_utc="2026-03-05T12:01:00+00:00",
            processed_lbs=100.0,
            full_lbs=140.0,
            empty_lbs=40.0,
            duration_ms=4000,
            confidence=0.9,
            dump_type="full",
        )
        repo.add_throughput_event(
            timestamp_utc="2026-03-05T12:02:00+00:00",
            processed_lbs=50.0,
            full_lbs=90.0,
            empty_lbs=40.0,
            duration_ms=6000,
            confidence=0.9,
            dump_type="end_of_lot",
        )
        repo.add_throughput_event(
            timestamp_utc="2026-03-05T12:04:00+00:00",
            processed_lbs=5.0,
            full_lbs=45.0,
            empty_lbs=40.0,
            duration_ms=2000,
            confidence=0.8,
            dump_type="empty",
        )
        repo.record_counted_event(
            timestamp_utc="2026-03-05T12:01:30+00:00",
            event_type="basket_dump",
            source="opto_input",
            source_channel=1,
            line_id=line_id,
            machine_id=machine_id,
        )
        repo.record_counted_event(
            timestamp_utc="2026-03-05T12:02:30+00:00",
            event_type="basket_dump",
            source="opto_input",
            source_channel=1,
            line_id=line_id,
            machine_id=machine_id,
        )
        repo.record_counted_event(
            timestamp_utc="2026-03-05T12:11:00+00:00",
            event_type="basket_dump",
            source="opto_input",
            source_channel=1,
            line_id=line_id,
            machine_id="machine-other",
        )

        svc._job_rezero_warning_seen = True
        svc._job_rezero_warning_reason = "outside_tolerance"
        svc._job_rezero_warning_weight_lbs = 21.5
        svc._job_rezero_warning_threshold_lbs = 20.0
        svc._job_post_dump_rezero_applied = True
        svc._job_post_dump_rezero_last_apply_utc = "2026-03-05T12:06:00+00:00"

        svc.ingest_job_webhook(
            job_id="JOB-2",
            target_weight_lb=140.0,
            event_id="job-2-first",
            line_id=line_id,
            machine_id=machine_id,
            set_weight_value=140.0,
            set_weight_unit="lb",
            erp_timestamp_utc="2026-03-05T12:10:00+00:00",
        )

        pending = repo.get_pending_job_completion_outbox(
            now_utc="9999-12-31T23:59:59+00:00",
            limit=20,
        )
        self.assertEqual(len(pending), 1)
        payload = pending[0]["payload"]
        self.assertEqual(payload["job_id"], "JOB-1")
        self.assertEqual(payload["line_id"], line_id)
        self.assertEqual(payload["machine_id"], machine_id)
        self.assertEqual(int(payload["cycle_count"]), 3)
        self.assertEqual(int(payload["dump_count"]), 2)
        self.assertAlmostEqual(float(payload["total_processed_lbs"]), 150.0, places=6)
        self.assertAlmostEqual(float(payload["avg_weight_lbs"]), 75.0, places=6)
        self.assertEqual(int(payload["avg_cycle_time_ms"]), 5000)
        self.assertEqual(int(payload["basket_dump_count"]), 2)
        self.assertTrue(bool(payload["override_seen"]))
        self.assertEqual(int(payload["override_count"]), 1)
        self.assertAlmostEqual(float(payload["final_set_weight_lbs"]), 130.0, places=6)
        self.assertTrue(bool(payload["rezero_warning_seen"]))
        self.assertEqual(payload["rezero_warning_reason"], "outside_tolerance")
        self.assertAlmostEqual(float(payload["rezero_warning_weight_lbs"]), 21.5, places=6)
        self.assertAlmostEqual(float(payload["rezero_warning_threshold_lbs"]), 20.0, places=6)
        self.assertTrue(bool(payload["post_dump_rezero_applied"]))
        self.assertEqual(payload["post_dump_rezero_last_apply_utc"], "2026-03-05T12:06:00+00:00")

        lifecycle_state = repo.get_job_lifecycle_state(line_id=line_id, machine_id=machine_id)
        self.assertIsNotNone(lifecycle_state)
        self.assertEqual(lifecycle_state.active_job_id, "JOB-2")

    def test_orphan_manual_override_is_ignored_for_job_lifecycle(self) -> None:
        repo, svc = self._make_repo_and_service()
        line_id = "line-2"
        machine_id = "machine-2"

        svc.ingest_job_webhook(
            job_id="MANUAL_OVERRIDE",
            target_weight_lb=110.0,
            line_id=line_id,
            machine_id=machine_id,
            set_weight_value=110.0,
            set_weight_unit="lb",
            source="manual_override:overridden:hdmi:test",
            erp_timestamp_utc="2026-03-05T12:15:00+00:00",
        )

        lifecycle_state = repo.get_job_lifecycle_state(line_id=line_id, machine_id=machine_id)
        self.assertIsNone(lifecycle_state)
        pending = repo.get_pending_job_completion_outbox(
            now_utc="9999-12-31T23:59:59+00:00",
            limit=20,
        )
        self.assertEqual(len(pending), 0)

    @mock.patch("src.services.acquisition.urllib_request.urlopen")
    def test_outbox_dispatch_marks_sent_on_success(self, mock_urlopen) -> None:
        repo, svc = self._make_repo_and_service()
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update(
                {
                    "completed_job_webhook_url": "http://example.com/job-complete",
                    "completed_job_webhook_timeout_s": 2.0,
                    "completed_job_webhook_dispatch_interval_s": 1.0,
                    "completed_job_webhook_retry_min_s": 2.0,
                    "completed_job_webhook_retry_max_s": 30.0,
                }
            ),
        )
        mock_urlopen.return_value = _StubSuccessResponse()
        repo.enqueue_job_completion_outbox(
            line_id="line-3",
            machine_id="machine-3",
            job_id="JOB-3",
            job_start_record_time_set_utc="2026-03-05T10:00:00+00:00",
            job_end_record_time_set_utc="2026-03-05T10:30:00+00:00",
            payload={"job_id": "JOB-3"},
        )

        cfg = svc._load_cfg()
        svc._dispatch_job_completion_outbox(cfg=cfg, now_s=time.monotonic())

        pending = repo.get_pending_job_completion_outbox(
            now_utc="9999-12-31T23:59:59+00:00",
            limit=20,
        )
        self.assertEqual(len(pending), 0)

    def test_outbox_dispatch_schedules_retry_on_failure(self) -> None:
        repo, svc = self._make_repo_and_service()
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update(
                {
                    "completed_job_webhook_url": "http://127.0.0.1:9/job-complete",
                    "completed_job_webhook_timeout_s": 1.0,
                    "completed_job_webhook_dispatch_interval_s": 1.0,
                    "completed_job_webhook_retry_min_s": 2.0,
                    "completed_job_webhook_retry_max_s": 2.0,
                }
            ),
        )
        outbox_id = repo.enqueue_job_completion_outbox(
            line_id="line-4",
            machine_id="machine-4",
            job_id="JOB-4",
            job_start_record_time_set_utc="2026-03-05T10:00:00+00:00",
            job_end_record_time_set_utc="2026-03-05T10:30:00+00:00",
            payload={"job_id": "JOB-4"},
        )

        cfg = svc._load_cfg()
        svc._dispatch_job_completion_outbox(cfg=cfg, now_s=time.monotonic())

        rows = repo.get_pending_job_completion_outbox(
            now_utc="9999-12-31T23:59:59+00:00",
            limit=20,
        )
        target = next((row for row in rows if int(row["id"]) == int(outbox_id)), None)
        self.assertIsNotNone(target)
        self.assertEqual(int(target["attempt_count"]), 1)
        self.assertTrue(str(target.get("last_error", "") or ""))


if __name__ == "__main__":
    unittest.main()
