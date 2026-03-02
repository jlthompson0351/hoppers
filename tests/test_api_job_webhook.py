"""Tests for /api/job/* endpoints with simplified threshold-based logic."""
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


class _StubJobService:
    def __init__(self) -> None:
        self.last_ingest = None
        self.status_payload = {
            "set_weight": 0.0,
            "active": False,
            "meta": None,
        }
        self.clear_calls = 0

    def ingest_job_webhook(
        self,
        *,
        job_id: str,
        target_weight_lb: float,
        step_id: str | None = None,
        event_id: str | None = None,
        source: str = "webhook",
        line_id: str | None = None,
        machine_id: str | None = None,
        set_weight_value: float | None = None,
        set_weight_unit: str | None = None,
        erp_timestamp_utc: str | None = None,
        product_id: str | None = None,
        operator_id: str | None = None,
        payload: dict | None = None,
    ) -> dict:
        self.last_ingest = {
            "job_id": job_id,
            "target_weight_lb": float(target_weight_lb),
            "step_id": step_id,
            "event_id": event_id,
            "source": source,
            "line_id": line_id,
            "machine_id": machine_id,
            "set_weight_value": set_weight_value,
            "set_weight_unit": set_weight_unit,
            "erp_timestamp_utc": erp_timestamp_utc,
            "product_id": product_id,
            "operator_id": operator_id,
            "payload": payload,
        }
        self.status_payload["set_weight"] = float(target_weight_lb)
        self.status_payload["active"] = True
        self.status_payload["meta"] = {
            "job_id": job_id,
            "step_id": step_id,
            "event_id": event_id,
            "target_weight_lb": float(target_weight_lb),
        }
        return {
            "accepted": True,
            "duplicate": False,
            "action": "activated",
            "status": dict(self.status_payload),
        }

    def get_job_control_status(self) -> dict:
        return dict(self.status_payload)

    def clear_job_control(self, reason: str = "manual_clear") -> dict:
        self.clear_calls += 1
        self.status_payload["set_weight"] = 0.0
        self.status_payload["active"] = False
        self.status_payload["meta"] = None
        return {"cleared": True, "status": dict(self.status_payload)}


class ApiJobWebhookTests(unittest.TestCase):
    @staticmethod
    def _payload(
        *,
        job_id: str = "JOB-1",
        load_size: float = 100.0,
        idempotency_key: str = "JOB-1:100:evt-1",
    ) -> dict:
        return {
            "event": "job.load_size_updated",
            "jobId": job_id,
            "machineKey": "PLP6",
            "loadSize": float(load_size),
            "idempotencyKey": idempotency_key,
            "timestamp": "2026-02-27T14:38:45.000Z",
        }

    def _make_app(self) -> tuple:
        tmp = tempfile.mkdtemp(prefix="api-job-webhook-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update(
                {
                    "enabled": True,
                    "mode": "target_signal_mode",
                    "webhook_token": "secret-123",
                }
            ),
        )
        state = LiveState()
        svc = _StubJobService()

        app = create_app()
        app.config["REPO"] = repo
        app.config["LIVE_STATE"] = state
        app.config["ACQ_SERVICE"] = svc
        app.config["TESTING"] = True
        return app, repo, state, svc

    def test_webhook_requires_job_id(self) -> None:
        app, _repo, _state, _svc = self._make_app()
        payload = self._payload()
        payload.pop("jobId", None)
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"X-API-Key": "secret-123"},
            )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertFalse(body.get("success"))
        self.assertIn("jobId", body.get("error", ""))

    def test_webhook_rejects_invalid_token(self) -> None:
        app, _repo, _state, _svc = self._make_app()
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(self._payload()),
                content_type="application/json",
                headers={"X-API-Key": "wrong"},
            )
        self.assertEqual(resp.status_code, 401)

    def test_webhook_rejects_when_target_mode_disabled(self) -> None:
        app, repo, _state, _svc = self._make_app()
        repo.update_config_section(
            "job_control",
            lambda section, _cfg: section.update({"enabled": False, "mode": "legacy_weight_mapping"}),
        )
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(self._payload()),
                content_type="application/json",
                headers={"X-API-Key": "secret-123"},
            )
        self.assertEqual(resp.status_code, 409)

    def test_webhook_requires_idempotency_key(self) -> None:
        app, _repo, _state, _svc = self._make_app()
        payload = self._payload()
        payload.pop("idempotencyKey", None)
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"X-API-Key": "secret-123"},
            )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertIn("idempotencyKey", body.get("error", ""))

    def test_webhook_rejects_whitespace_only_idempotency_key(self) -> None:
        app, _repo, _state, _svc = self._make_app()
        payload = self._payload(idempotency_key="   ")
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"X-API-Key": "secret-123"},
            )
        self.assertEqual(resp.status_code, 400)

    def test_webhook_accepts_valid_payload(self) -> None:
        app, _repo, _state, svc = self._make_app()
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(
                    self._payload(
                        job_id="1703487",
                        load_size=100.0,
                        idempotency_key="1703487:100:6d1c4f60-6ea4-4d0f-9cc9-2a2f5f0e8b2a",
                    )
                ),
                content_type="application/json",
                headers={"X-API-Key": "secret-123"},
            )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.data.decode("utf-8"))
        self.assertTrue(body.get("success"))
        self.assertEqual(body.get("action"), "activated")
        self.assertIsNotNone(svc.last_ingest)
        self.assertEqual(svc.last_ingest["job_id"], "1703487")
        self.assertAlmostEqual(float(svc.last_ingest["target_weight_lb"]), 100.0)
        self.assertEqual(
            svc.last_ingest["event_id"],
            "1703487:100:6d1c4f60-6ea4-4d0f-9cc9-2a2f5f0e8b2a",
        )

    def test_webhook_accepts_bearer_token(self) -> None:
        app, _repo, _state, _svc = self._make_app()
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(self._payload()),
                content_type="application/json",
                headers={"Authorization": "Bearer secret-123"},
            )
        self.assertEqual(resp.status_code, 200)

    def test_webhook_maps_extended_payload_fields_and_units(self) -> None:
        app, _repo, _state, svc = self._make_app()
        payload = {
            "event": "job.load_size_updated",
            "jobId": "JOB-EXT-1",
            "line_id": "line-7",
            "machine_id": "mixer-2",
            "set_weight": 50.0,
            "unit": "kg",
            "idempotencyKey": "ext-evt-1",
            "timestamp": "2026-03-02T14:00:00.000Z",
            "product_id": "SKU-77",
            "operator_id": "op-9",
        }
        with app.test_client() as client:
            resp = client.post(
                "/api/job/webhook",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"X-API-Key": "secret-123"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(svc.last_ingest)
        self.assertEqual(svc.last_ingest["line_id"], "line-7")
        self.assertEqual(svc.last_ingest["machine_id"], "mixer-2")
        self.assertEqual(svc.last_ingest["set_weight_unit"], "kg")
        self.assertAlmostEqual(float(svc.last_ingest["set_weight_value"]), 50.0)
        self.assertAlmostEqual(float(svc.last_ingest["target_weight_lb"]), 110.231131, places=5)
        self.assertEqual(svc.last_ingest["product_id"], "SKU-77")
        self.assertEqual(svc.last_ingest["operator_id"], "op-9")

    def test_job_status_and_clear_endpoints(self) -> None:
        app, _repo, _state, svc = self._make_app()
        svc.status_payload["set_weight"] = 80.0
        svc.status_payload["active"] = True

        with app.test_client() as client:
            status_resp = client.get("/api/job/status", headers={"X-API-Key": "secret-123"})
            self.assertEqual(status_resp.status_code, 200)
            status_body = json.loads(status_resp.data.decode("utf-8"))
            self.assertTrue(status_body.get("success"))
            self.assertAlmostEqual(float(status_body["status"]["set_weight"]), 80.0)

            clear_resp = client.post("/api/job/clear", headers={"Authorization": "Bearer secret-123"})
            self.assertEqual(clear_resp.status_code, 200)
            clear_body = json.loads(clear_resp.data.decode("utf-8"))
            self.assertTrue(clear_body.get("success"))
            self.assertTrue(clear_body.get("cleared"))
            self.assertEqual(svc.clear_calls, 1)

    def test_status_and_clear_require_valid_token(self) -> None:
        app, _repo, _state, _svc = self._make_app()
        with app.test_client() as client:
            self.assertEqual(client.get("/api/job/status").status_code, 401)
            self.assertEqual(client.post("/api/job/clear").status_code, 401)

    def test_capture_trigger_from_nudge(self) -> None:
        app, repo, _state, _svc = self._make_app()
        repo.update_config_section(
            "output",
            lambda section, _cfg: section.update({"mode": "0_10V", "nudge_value": 1.234}),
        )
        with app.test_client() as client:
            self.assertEqual(
                client.post("/api/job/trigger/from-nudge").status_code, 401
            )
            resp = client.post(
                "/api/job/trigger/from-nudge", headers={"X-API-Key": "secret-123"}
            )
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))
            self.assertTrue(body.get("success"))
            self.assertAlmostEqual(float(body.get("trigger_signal_value", 0.0)), 1.234, places=3)

        cfg = repo.get_latest_config()
        self.assertAlmostEqual(
            float((cfg.get("job_control") or {}).get("trigger_signal_value", 0.0)),
            1.234,
            places=3,
        )


if __name__ == "__main__":
    unittest.main()
