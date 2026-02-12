from __future__ import annotations

import unittest
from dataclasses import dataclass

from src.core.zero_tracking import ZeroTracker, ZeroTrackingConfig
from src.core.zeroing import compute_zero_offset


@dataclass(frozen=True)
class _Point:
    known_weight_lbs: float
    signal: float


class ZeroTrackingTests(unittest.TestCase):
    def test_baseline_remains_stable_with_load(self) -> None:
        tracker = ZeroTracker()
        cfg = ZeroTrackingConfig(
            enabled=True,
            range_lb=0.5,
            deadband_lb=0.1,
            hold_s=0.0,
            rate_lbs=0.1,
            persist_interval_s=1.0,
        )

        offset_mv = 1.234
        now = 0.0
        for _ in range(30):
            now += 0.1
            step = tracker.step(
                now_s=now,
                dt_s=0.1,
                filtered_lbs=5.0,  # Simulate real load on scale.
                tare_offset_lbs=0.0,
                is_stable=True,
                lbs_per_mv=2.0,
                current_zero_offset_mv=offset_mv,
                cfg=cfg,
                spike_detected=False,
            )
            offset_mv = step.zero_offset_mv
            self.assertTrue(step.locked)
            self.assertEqual(step.reason, "load_present")
            self.assertAlmostEqual(step.signal_correction_mv, 0.0, places=9)

        self.assertAlmostEqual(offset_mv, 1.234, places=9)

    def test_baseline_slowly_corrects_unloaded_drift(self) -> None:
        tracker = ZeroTracker()
        cfg = ZeroTrackingConfig(
            enabled=True,
            range_lb=0.5,
            deadband_lb=0.05,
            hold_s=1.0,
            rate_lbs=0.1,  # Max correction = 0.01 lb per 100 ms step.
            persist_interval_s=1.0,
        )

        offset_mv = 0.0
        now = 0.0
        seen_active = False

        for i in range(40):
            now += 0.1
            step = tracker.step(
                now_s=now,
                dt_s=0.1,
                filtered_lbs=0.4,  # Near zero drift error while unloaded.
                tare_offset_lbs=0.0,
                is_stable=True,
                lbs_per_mv=2.0,
                current_zero_offset_mv=offset_mv,
                cfg=cfg,
                spike_detected=False,
            )
            offset_mv = step.zero_offset_mv

            if i < 5:
                self.assertTrue(step.locked)
                self.assertEqual(step.reason, "holdoff")

            if step.active:
                seen_active = True
                self.assertFalse(step.locked)
                self.assertLessEqual(abs(step.weight_correction_lbs), 0.0100001)

        self.assertTrue(seen_active)
        self.assertGreater(offset_mv, 0.0)
        self.assertLess(offset_mv, 0.25)

    def test_manual_zero_sets_expected_baseline_offset(self) -> None:
        points = [
            _Point(known_weight_lbs=0.0, signal=5.61),
            _Point(known_weight_lbs=25.0, signal=6.37),
        ]
        zero_offset_mv, cal_zero_signal = compute_zero_offset(5.85, points)

        self.assertAlmostEqual(cal_zero_signal, 5.61, places=6)
        self.assertAlmostEqual(zero_offset_mv, 0.24, places=6)


if __name__ == "__main__":
    unittest.main()
