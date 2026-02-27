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
            startup_lockout_s=0.0,
        )

        offset_lbs = 1.234
        now = 0.0
        for _ in range(30):
            now += 0.1
            step = tracker.step(
                now_s=now,
                dt_s=0.1,
                display_lbs=5.0,  # Simulate real load on scale.
                tare_offset_lbs=0.0,
                is_stable=True,
                current_zero_offset_lbs=offset_lbs,
                cfg=cfg,
                spike_detected=False,
            )
            offset_lbs += step.zero_offset_delta_lbs
            self.assertTrue(step.locked)
            self.assertEqual(step.reason, "load_present")
            self.assertAlmostEqual(step.weight_correction_lbs, 0.0, places=9)

        self.assertAlmostEqual(offset_lbs, 1.234, places=9)

    def test_baseline_slowly_corrects_unloaded_drift(self) -> None:
        tracker = ZeroTracker()
        cfg = ZeroTrackingConfig(
            enabled=True,
            range_lb=0.5,
            deadband_lb=0.05,
            hold_s=1.0,
            rate_lbs=0.1,  # Max correction = 0.01 lb per 100 ms step.
            persist_interval_s=1.0,
            startup_lockout_s=0.0,
        )

        offset_lbs = 0.0
        now = 0.0
        seen_active = False

        for i in range(40):
            now += 0.1
            step = tracker.step(
                now_s=now,
                dt_s=0.1,
                display_lbs=0.4,  # Near zero drift error while unloaded.
                tare_offset_lbs=0.0,
                is_stable=True,
                current_zero_offset_lbs=offset_lbs,
                cfg=cfg,
                spike_detected=False,
            )
            offset_lbs += step.zero_offset_delta_lbs

            if i < 5:
                self.assertTrue(step.locked)
                self.assertEqual(step.reason, "holdoff")

            if step.active:
                seen_active = True
                self.assertFalse(step.locked)
                self.assertLessEqual(abs(step.weight_correction_lbs), 0.0100001)

        self.assertTrue(seen_active)
        self.assertGreater(offset_lbs, 0.0)
        # Rate limit is 0.1 lb/s * 0.1s/step * ~30 active steps ≈ 0.30 lb max.
        self.assertLess(offset_lbs, 0.40)

    def test_manual_zero_sets_expected_baseline_offset(self) -> None:
        points = [
            _Point(known_weight_lbs=0.0, signal=5.61),
            _Point(known_weight_lbs=25.0, signal=6.37),
        ]
        zero_offset_mv, cal_zero_signal = compute_zero_offset(5.85, points)

        self.assertAlmostEqual(cal_zero_signal, 5.61, places=6)
        self.assertAlmostEqual(zero_offset_mv, 0.24, places=6)

    def test_holdoff_resets_after_transient_load(self) -> None:
        tracker = ZeroTracker()
        cfg = ZeroTrackingConfig(
            enabled=True,
            range_lb=0.5,
            deadband_lb=0.05,
            hold_s=1.0,
            rate_lbs=0.1,
            persist_interval_s=1.0,
            startup_lockout_s=0.0,
        )

        step1 = tracker.step(
            now_s=0.1,
            dt_s=0.1,
            display_lbs=0.4,
            tare_offset_lbs=0.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        self.assertEqual(step1.reason, "holdoff")
        self.assertAlmostEqual(step1.hold_elapsed_s, 0.0, places=6)

        # Transient load should lock and reset hold gate.
        step2 = tracker.step(
            now_s=0.2,
            dt_s=0.1,
            display_lbs=5.0,
            tare_offset_lbs=0.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        self.assertEqual(step2.reason, "load_present")

        # Returning to near-zero should restart holdoff from ~0.
        step3 = tracker.step(
            now_s=0.3,
            dt_s=0.1,
            display_lbs=0.4,
            tare_offset_lbs=0.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        self.assertEqual(step3.reason, "holdoff")
        self.assertLess(step3.hold_elapsed_s, 0.2)

    def test_out_of_range_negative_blocks_corrections(self) -> None:
        tracker = ZeroTracker()
        cfg = ZeroTrackingConfig(
            enabled=True,
            range_lb=0.5,
            deadband_lb=0.1,
            hold_s=0.0,
            rate_lbs=0.1,
            persist_interval_s=1.0,
            startup_lockout_s=0.0,
        )
        step = tracker.step(
            now_s=1.0,
            dt_s=0.1,
            display_lbs=-1.0,
            tare_offset_lbs=0.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        self.assertTrue(step.locked)
        self.assertEqual(step.reason, "load_present")
        self.assertAlmostEqual(step.zero_offset_delta_lbs, 0.0, places=9)
        self.assertAlmostEqual(step.weight_correction_lbs, 0.0, places=9)

    def test_tare_lock_then_resume_with_fresh_holdoff(self) -> None:
        tracker = ZeroTracker()
        cfg = ZeroTrackingConfig(
            enabled=True,
            range_lb=0.5,
            deadband_lb=0.05,
            hold_s=0.5,
            rate_lbs=0.1,
            persist_interval_s=1.0,
            startup_lockout_s=0.0,
        )

        tracker.step(
            now_s=0.1,
            dt_s=0.1,
            display_lbs=0.4,
            tare_offset_lbs=0.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        active = tracker.step(
            now_s=0.8,
            dt_s=0.1,
            display_lbs=0.4,
            tare_offset_lbs=0.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        self.assertTrue(active.active)
        self.assertIn(active.reason, ("tracking", "deadband"))

        locked = tracker.step(
            now_s=0.9,
            dt_s=0.1,
            display_lbs=0.4,
            tare_offset_lbs=10.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        self.assertTrue(locked.locked)
        self.assertEqual(locked.reason, "tare_active")

        resumed = tracker.step(
            now_s=1.0,
            dt_s=0.1,
            display_lbs=0.4,
            tare_offset_lbs=0.0,
            is_stable=True,
            current_zero_offset_lbs=0.0,
            cfg=cfg,
            spike_detected=False,
        )
        self.assertEqual(resumed.reason, "holdoff")
        self.assertLess(resumed.hold_elapsed_s, 0.2)


if __name__ == "__main__":
    unittest.main()
