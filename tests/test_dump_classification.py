from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.core.throughput_cycle import ThroughputCycleEvent
from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class DumpClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="dump-classification-tests-")
        self.addCleanup(lambda: shutil.rmtree(self._tmp, ignore_errors=True))
        self.db_path = Path(self._tmp) / "app.sqlite3"
        ensure_db(self.db_path)
        self.repo = AppRepository(self.db_path)
        self.service = AcquisitionService(hw=None, repo=self.repo, state=LiveState())

    @staticmethod
    def _cfg(max_lb: float = 300.0, min_processed_lb: float = 5.0) -> SimpleNamespace:
        return SimpleNamespace(
            range_max_lb=float(max_lb),
            throughput_device_id="hopper-a",
            throughput_hopper_id="line-1",
            zero_target_lb=0.0,
            zero_offset_mv=0.35,
            zero_offset_lbs=39.2,
            throughput_min_processed_lb=float(min_processed_lb),
        )

    def _persist(
        self,
        processed_lbs: float,
        target_set_weight_lbs: float | None = None,
        cfg: SimpleNamespace | None = None,
    ) -> bool:
        if cfg is None:
            cfg = self._cfg()
        return self.service._persist_throughput_cycle_event(
            throughput_evt=ThroughputCycleEvent(
                processed_lbs=processed_lbs,
                full_lbs=processed_lbs + 5.0,
                empty_lbs=5.0,
                duration_ms=120000,
                confidence=0.90,
            ),
            cfg=cfg,
            event_ts="2026-03-04T15:00:00+00:00",
            throughput_full_lbs=processed_lbs + 5.0,
            throughput_empty_lbs=5.0,
            raw_mv=5.50,
            adjusted_signal_mv=5.15,
            filtered_lbs=processed_lbs,
            target_relative_lbs=processed_lbs,
            throughput_full_min_relative_lb=15.0,
            target_set_weight_lbs=target_set_weight_lbs,
        )

    def test_full_dump_with_set_weight(self) -> None:
        self._persist(185.0, target_set_weight_lbs=190.0)
        last = self.repo.get_last_dump()
        assert last is not None
        self.assertEqual(last["dump_type"], "full")

    def test_end_of_lot_dump_with_set_weight(self) -> None:
        self._persist(50.0, target_set_weight_lbs=190.0)
        last = self.repo.get_last_dump()
        assert last is not None
        self.assertEqual(last["dump_type"], "end_of_lot")

    def test_empty_dump_with_set_weight(self) -> None:
        self._persist(2.0, target_set_weight_lbs=190.0)
        last = self.repo.get_last_dump()
        assert last is not None
        self.assertEqual(last["dump_type"], "empty")

    def test_full_dump_without_set_weight(self) -> None:
        self._persist(150.0, target_set_weight_lbs=None)
        last = self.repo.get_last_dump()
        assert last is not None
        self.assertEqual(last["dump_type"], "full")

    def test_empty_dump_without_set_weight(self) -> None:
        self._persist(2.0, target_set_weight_lbs=None)
        last = self.repo.get_last_dump()
        assert last is not None
        self.assertEqual(last["dump_type"], "empty")

    def test_end_of_lot_counts_toward_daily_total(self) -> None:
        self._persist(185.0, target_set_weight_lbs=190.0)
        self._persist(50.0, target_set_weight_lbs=190.0)
        totals = self.repo.get_production_totals(["day"])
        self.assertAlmostEqual(totals["day"], 235.0, places=6)

    def test_empty_does_not_count_toward_daily_total(self) -> None:
        self._persist(185.0, target_set_weight_lbs=190.0)
        self._persist(2.0, target_set_weight_lbs=190.0)
        totals = self.repo.get_production_totals(["day"])
        self.assertAlmostEqual(totals["day"], 185.0, places=6)

    def test_dump_count_only_includes_full(self) -> None:
        self._persist(185.0, target_set_weight_lbs=190.0)
        self._persist(50.0, target_set_weight_lbs=190.0)
        self._persist(2.0, target_set_weight_lbs=190.0)
        count = self.repo.get_dump_count("day")
        self.assertEqual(count, 1)

    def test_dump_type_persists_to_throughput_events(self) -> None:
        self._persist(185.0, target_set_weight_lbs=190.0)
        self._persist(50.0, target_set_weight_lbs=190.0)
        self._persist(2.0, target_set_weight_lbs=190.0)
        events = self.repo.get_throughput_events_range(order_desc=False)
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0]["dump_type"], "full")
        self.assertEqual(events[1]["dump_type"], "end_of_lot")
        self.assertEqual(events[2]["dump_type"], "empty")

    def test_65_percent_boundary(self) -> None:
        self._persist(123.5, target_set_weight_lbs=190.0)
        last = self.repo.get_last_dump()
        assert last is not None
        self.assertEqual(last["dump_type"], "full")

        self.repo2 = AppRepository(self.db_path)
        svc2 = AcquisitionService(hw=None, repo=self.repo2, state=LiveState())
        svc2._persist_throughput_cycle_event(
            throughput_evt=ThroughputCycleEvent(
                processed_lbs=123.0,
                full_lbs=128.0,
                empty_lbs=5.0,
                duration_ms=120000,
                confidence=0.90,
            ),
            cfg=self._cfg(),
            event_ts="2026-03-04T15:01:00+00:00",
            throughput_full_lbs=128.0,
            throughput_empty_lbs=5.0,
            raw_mv=5.50,
            adjusted_signal_mv=5.15,
            filtered_lbs=123.0,
            target_relative_lbs=123.0,
            throughput_full_min_relative_lb=15.0,
            target_set_weight_lbs=190.0,
        )
        last2 = self.repo2.get_last_dump()
        assert last2 is not None
        self.assertEqual(last2["dump_type"], "end_of_lot")


if __name__ == "__main__":
    unittest.main()
