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


class SnapshotPlcOutputTests(unittest.TestCase):
    def test_snapshot_exposes_mapping_status_fields(self) -> None:
        tmp = tempfile.mkdtemp(prefix="snapshot-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))

        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        repo = AppRepository(db_path)
        state = LiveState()
        state.set(
            output_mode="0_10V",
            output_command=2.0,
            output_units="V",
            output_armed=True,
            output_mapping_mode="profile",
            output_profile_active=True,
            output_profile_points=3,
        )

        app = create_app()
        app.config["REPO"] = repo
        app.config["LIVE_STATE"] = state

        with app.test_client() as client:
            resp = client.get("/api/snapshot")
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.data.decode("utf-8"))

        plc = body["plcOutput"]
        self.assertEqual(plc["mapping_mode"], "profile")
        self.assertTrue(plc["profile_active"])
        self.assertEqual(plc["profile_points"], 3)
        self.assertIn("range_min_lb", plc)
        self.assertIn("range_max_lb", plc)


if __name__ == "__main__":
    unittest.main()
