from __future__ import annotations

import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from src.db.migrate import ensure_db
from src.db.repo import AppRepository


class RepoConfigAtomicTests(unittest.TestCase):
    def _make_repo(self) -> AppRepository:
        tmp = tempfile.mkdtemp(prefix="repo-atomic-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        return AppRepository(db_path)

    def test_update_config_section_updates_target_section(self) -> None:
        repo = self._make_repo()

        def _set_zero(scale: dict, _: dict) -> None:
            scale["zero_offset_lbs"] = 1.25
            scale["zero_offset_updated_utc"] = "2026-02-15T00:00:00+00:00"

        repo.update_config_section("scale", _set_zero)
        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}

        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), 1.25, places=9)
        self.assertEqual(scale.get("zero_offset_updated_utc"), "2026-02-15T00:00:00+00:00")

    def test_update_config_section_is_atomic_under_concurrency(self) -> None:
        repo = self._make_repo()
        workers = 6
        iterations = 40
        barrier = threading.Barrier(workers)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                barrier.wait()
                for _ in range(iterations):
                    def _increment(scale: dict, _: dict) -> None:
                        current = float(scale.get("zero_offset_lbs", 0.0) or 0.0)
                        scale["zero_offset_lbs"] = current + 1.0

                    repo.update_config_section("scale", _increment)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10.0)

        self.assertEqual(errors, [])
        scale = (repo.get_latest_config().get("scale") or {})
        expected = float(workers * iterations)
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), expected, places=6)

    def test_concurrent_zero_and_tare_updates_preserve_both_fields(self) -> None:
        repo = self._make_repo()
        iterations = 25
        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def zero_worker() -> None:
            try:
                barrier.wait()
                for i in range(iterations):
                    def _set_zero(scale: dict, _: dict) -> None:
                        scale["zero_offset_lbs"] = float(i)
                        scale["zero_offset_updated_utc"] = f"zero-{i}"

                    repo.update_config_section("scale", _set_zero)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def tare_worker() -> None:
            try:
                barrier.wait()
                for i in range(iterations):
                    def _set_tare(scale: dict, _: dict) -> None:
                        scale["tare_offset_lbs"] = float(i)
                        scale["last_tare_utc"] = f"tare-{i}"

                    repo.update_config_section("scale", _set_tare)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        t1 = threading.Thread(target=zero_worker, daemon=True)
        t2 = threading.Thread(target=tare_worker, daemon=True)
        t1.start()
        t2.start()
        t1.join(timeout=10.0)
        t2.join(timeout=10.0)

        self.assertEqual(errors, [])
        scale = (repo.get_latest_config().get("scale") or {})
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or -1.0), float(iterations - 1), places=9)
        self.assertAlmostEqual(float(scale.get("tare_offset_lbs") or -1.0), float(iterations - 1), places=9)

    def test_zero_update_persists_immediately(self) -> None:
        """Zero offset updates must persist immediately (no lost writes)."""
        repo = self._make_repo()

        # Initial zero
        def _set_initial(scale: dict, _: dict) -> None:
            scale["zero_offset_lbs"] = 1.0
            scale["zero_offset_updated_utc"] = "2026-02-15T10:00:00+00:00"

        repo.update_config_section("scale", _set_initial)

        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), 1.0, places=9)
        self.assertEqual(scale.get("zero_offset_updated_utc"), "2026-02-15T10:00:00+00:00")

        # Update zero
        def _update_zero(scale: dict, _: dict) -> None:
            scale["zero_offset_lbs"] = 2.5
            scale["zero_offset_updated_utc"] = "2026-02-15T10:01:00+00:00"

        repo.update_config_section("scale", _update_zero)

        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), 2.5, places=9)
        self.assertEqual(scale.get("zero_offset_updated_utc"), "2026-02-15T10:01:00+00:00")

    def test_zero_update_preserves_other_scale_fields(self) -> None:
        """Zero updates must not clobber other scale section fields."""
        repo = self._make_repo()

        # Set initial scale config with multiple fields
        def _set_initial(scale: dict, _: dict) -> None:
            scale["zero_offset_lbs"] = 1.0
            scale["tare_offset_lbs"] = 5.0
            scale["custom_field"] = "test_value"

        repo.update_config_section("scale", _set_initial)

        # Update only zero
        def _update_zero(scale: dict, _: dict) -> None:
            scale["zero_offset_lbs"] = 3.0
            scale["zero_offset_updated_utc"] = "2026-02-15T10:00:00+00:00"

        repo.update_config_section("scale", _update_zero)

        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), 3.0, places=9)
        self.assertAlmostEqual(float(scale.get("tare_offset_lbs") or 0.0), 5.0, places=9)
        self.assertEqual(scale.get("custom_field"), "test_value")

    def test_rapid_zero_updates_all_persist(self) -> None:
        """Rapid zero offset updates must all persist (no write collisions)."""
        repo = self._make_repo()
        iterations = 50

        for i in range(iterations):
            def _set_zero(scale: dict, _: dict) -> None:
                scale["zero_offset_lbs"] = float(i)
                scale["zero_offset_updated_utc"] = f"2026-02-15T10:00:{i:02d}+00:00"

            repo.update_config_section("scale", _set_zero)

        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(
            float(scale.get("zero_offset_lbs") or -1.0), float(iterations - 1), places=9
        )
        self.assertEqual(
            scale.get("zero_offset_updated_utc"), f"2026-02-15T10:00:{iterations-1:02d}+00:00"
        )

    def test_zero_clear_preserves_timestamp(self) -> None:
        """Clearing zero to 0.0 should still update timestamp."""
        repo = self._make_repo()

        # Set initial non-zero offset
        repo.update_config_section(
            "scale",
            lambda scale, _: scale.update({
                "zero_offset_lbs": 5.0,
                "zero_offset_updated_utc": "2026-02-15T10:00:00+00:00"
            })
        )

        # Verify initial state
        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs", 0.0)), 5.0, places=9)

        # Clear zero
        repo.update_config_section(
            "scale",
            lambda scale, _: scale.update({
                "zero_offset_lbs": 0.0,
                "zero_offset_updated_utc": "2026-02-15T10:05:00+00:00"
            })
        )

        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs", -1.0)), 0.0, places=9)
        self.assertEqual(scale.get("zero_offset_updated_utc"), "2026-02-15T10:05:00+00:00")

    def test_zero_mv_canonical_fields_persist_together(self) -> None:
        """Canonical mV + derived lbs + legacy signal alias persist coherently."""
        repo = self._make_repo()

        repo.update_config_section(
            "scale",
            lambda scale, _: scale.update(
                {
                    "zero_offset_mv": -0.020,
                    "zero_offset_signal": -0.020,
                    "zero_offset_lbs": -2.631578947,
                    "zero_offset_updated_utc": "2026-02-15T11:00:00+00:00",
                }
            ),
        )

        cfg = repo.get_latest_config()
        scale = cfg.get("scale") or {}
        self.assertAlmostEqual(float(scale.get("zero_offset_mv") or 0.0), -0.020, places=9)
        self.assertAlmostEqual(float(scale.get("zero_offset_signal") or 0.0), -0.020, places=9)
        self.assertAlmostEqual(float(scale.get("zero_offset_lbs") or 0.0), -2.631578947, places=9)
        self.assertEqual(scale.get("zero_offset_updated_utc"), "2026-02-15T11:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
