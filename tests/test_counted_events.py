from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from src.db.migrate import ensure_db
from src.db.repo import AppRepository
from src.services.acquisition import AcquisitionService
from src.services.state import LiveState


class _StubMegaInd:
    def __init__(self, sequences: dict[int, list[bool]]) -> None:
        self._sequences = {int(ch): list(values) for ch, values in sequences.items()}
        self._positions = {int(ch): 0 for ch in self._sequences}

    def read_digital_in(self, ch: int) -> bool:
        values = self._sequences.get(int(ch), [False])
        pos = self._positions.get(int(ch), 0)
        if pos >= len(values):
            return bool(values[-1])
        self._positions[int(ch)] = pos + 1
        return bool(values[pos])


class _StubHardware:
    def __init__(self, sequences: dict[int, list[bool]]) -> None:
        self.megaind = _StubMegaInd(sequences)


class CountedEventTests(unittest.TestCase):
    def _make_repo(self) -> AppRepository:
        tmp = tempfile.mkdtemp(prefix="counted-events-tests-")
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        db_path = Path(tmp) / "app.sqlite3"
        ensure_db(db_path)
        return AppRepository(db_path)

    def test_job_window_counted_event_summary_filters_scope_and_type(self) -> None:
        repo = self._make_repo()
        repo.record_counted_event(
            timestamp_utc="2026-03-06T12:01:00+00:00",
            event_type="basket_dump",
            source="opto_input",
            source_channel=1,
            line_id="line-1",
            machine_id="machine-1",
        )
        repo.record_counted_event(
            timestamp_utc="2026-03-06T12:02:00+00:00",
            event_type="basket_dump",
            source="opto_input",
            source_channel=2,
            line_id="line-1",
            machine_id="machine-1",
        )
        repo.record_counted_event(
            timestamp_utc="2026-03-06T12:03:00+00:00",
            event_type="reject_cycle",
            source="opto_input",
            source_channel=3,
            line_id="line-1",
            machine_id="machine-1",
        )
        repo.record_counted_event(
            timestamp_utc="2026-03-06T12:02:30+00:00",
            event_type="basket_dump",
            source="opto_input",
            source_channel=1,
            line_id="line-2",
            machine_id="machine-1",
        )

        summary = repo.get_job_window_counted_event_summary(
            line_id="line-1",
            machine_id="machine-1",
            start_utc="2026-03-06T12:00:00+00:00",
            end_utc="2026-03-06T12:10:00+00:00",
        )

        self.assertEqual(summary.get("basket_dump"), 2)
        self.assertEqual(summary.get("reject_cycle"), 1)

    def test_poll_buttons_counts_basket_dump_once_per_rising_edge(self) -> None:
        repo = self._make_repo()
        repo.save_config(
            {
                **repo.get_latest_config(),
                "opto_actions": {"1": "basket_dump", "2": "none", "3": "none", "4": "none"},
            }
        )
        hw = _StubHardware(
            {
                1: [False, True, True, True, False, True, True],
                2: [False] * 7,
                3: [False] * 7,
                4: [False] * 7,
            }
        )
        svc = AcquisitionService(hw=hw, repo=repo, state=LiveState())
        cfg = svc._load_cfg()

        # First rising edge fires normally. Reset cooldown between the two edges so
        # this test validates rising-edge detection independently of the 30s cooldown.
        svc._poll_buttons(cfg, raw_mv=0.0, gross_lbs=0.0)  # False → no action
        svc._poll_buttons(cfg, raw_mv=0.0, gross_lbs=0.0)  # True  → rising edge #1
        svc._last_basket_dump_s = -1e9                      # reset cooldown
        svc._poll_buttons(cfg, raw_mv=0.0, gross_lbs=0.0)  # True  → sustained, no action
        svc._poll_buttons(cfg, raw_mv=0.0, gross_lbs=0.0)  # True  → sustained, no action
        svc._poll_buttons(cfg, raw_mv=0.0, gross_lbs=0.0)  # False → falling edge
        svc._last_basket_dump_s = -1e9                      # reset cooldown
        svc._poll_buttons(cfg, raw_mv=0.0, gross_lbs=0.0)  # True  → rising edge #2
        svc._poll_buttons(cfg, raw_mv=0.0, gross_lbs=0.0)  # True  → sustained, no action

        summary = repo.get_job_window_counted_event_summary(
            line_id="default_line",
            machine_id="default_machine",
            start_utc="0001-01-01T00:00:00+00:00",
            end_utc="9999-12-31T23:59:59+00:00",
        )

        self.assertEqual(summary.get("basket_dump"), 2)

    def test_basket_dump_cooldown_suppresses_second_pulse(self) -> None:
        repo = self._make_repo()
        repo.save_config(
            {
                **repo.get_latest_config(),
                "opto_actions": {"1": "basket_dump", "2": "none", "3": "none", "4": "none"},
            }
        )
        svc = AcquisitionService(hw=None, repo=repo, state=LiveState())
        cfg = svc._load_cfg()

        # Fire two basket_dump edges with no time gap (simulates double-pulse within cooldown).
        svc._handle_button("basket_dump", raw_mv=0.0, gross_lbs=0.0, cfg=cfg, channel=1)
        svc._handle_button("basket_dump", raw_mv=0.0, gross_lbs=0.0, cfg=cfg, channel=1)

        summary = repo.get_job_window_counted_event_summary(
            line_id="default_line",
            machine_id="default_machine",
            start_utc="0001-01-01T00:00:00+00:00",
            end_utc="9999-12-31T23:59:59+00:00",
        )

        self.assertEqual(summary.get("basket_dump"), 1)


if __name__ == "__main__":
    unittest.main()
