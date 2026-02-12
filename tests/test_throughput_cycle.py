from __future__ import annotations

import unittest

from src.core.throughput_cycle import ThroughputCycleConfig, ThroughputCycleDetector


class ThroughputCycleDetectorTests(unittest.TestCase):
    def test_emits_event_for_completed_cycle(self) -> None:
        detector = ThroughputCycleDetector()
        cfg = ThroughputCycleConfig(
            empty_threshold_lb=2.0,
            rise_trigger_lb=8.0,
            full_min_lb=15.0,
            dump_drop_lb=6.0,
            full_stability_s=1.0,
            empty_confirm_s=1.0,
            min_processed_lb=5.0,
            max_cycle_s=600.0,
        )

        now = 0.0

        def step(weight: float, stable: bool, dt: float = 0.5):
            nonlocal now
            now += dt
            return detector.update(now_s=now, gross_lbs=weight, is_stable=stable, cfg=cfg)

        for _ in range(4):
            self.assertIsNone(step(0.4, stable=True))

        for w in (4.0, 9.0, 14.0, 20.0, 24.0):
            self.assertIsNone(step(w, stable=False))

        for _ in range(3):
            self.assertIsNone(step(24.2, stable=True))

        for w in (19.0, 13.0, 8.0, 3.0):
            self.assertIsNone(step(w, stable=False))

        evt = None
        for _ in range(4):
            evt = step(0.8, stable=True)
            if evt is not None:
                break

        self.assertIsNotNone(evt)
        assert evt is not None
        self.assertGreaterEqual(evt.processed_lbs, 20.0)
        self.assertLessEqual(evt.processed_lbs, 24.0)
        self.assertAlmostEqual(evt.full_lbs, 24.2, places=1)
        self.assertAlmostEqual(evt.empty_lbs, 0.8, places=1)
        self.assertGreater(evt.duration_ms, 0)
        self.assertGreaterEqual(evt.confidence, 0.0)
        self.assertLessEqual(evt.confidence, 1.0)

    def test_rejects_cycle_below_min_processed(self) -> None:
        detector = ThroughputCycleDetector()
        cfg = ThroughputCycleConfig(
            empty_threshold_lb=2.0,
            rise_trigger_lb=3.0,
            full_min_lb=5.0,
            dump_drop_lb=2.0,
            full_stability_s=0.5,
            empty_confirm_s=0.5,
            min_processed_lb=10.0,
            max_cycle_s=600.0,
        )

        now = 0.0

        def step(weight: float, stable: bool, dt: float = 0.5):
            nonlocal now
            now += dt
            return detector.update(now_s=now, gross_lbs=weight, is_stable=stable, cfg=cfg)

        for _ in range(2):
            self.assertIsNone(step(0.2, stable=True))

        for w in (1.5, 3.5, 5.5, 6.2):
            self.assertIsNone(step(w, stable=False))

        for _ in range(2):
            self.assertIsNone(step(6.1, stable=True))

        for w in (4.0, 2.5):
            self.assertIsNone(step(w, stable=False))

        for _ in range(3):
            self.assertIsNone(step(1.8, stable=True))

    def test_gradual_dump_does_not_restart_as_fill(self) -> None:
        detector = ThroughputCycleDetector()
        cfg = ThroughputCycleConfig(
            empty_threshold_lb=2.0,
            rise_trigger_lb=8.0,
            full_min_lb=15.0,
            dump_drop_lb=6.0,
            full_stability_s=1.0,
            empty_confirm_s=1.0,
            min_processed_lb=5.0,
            max_cycle_s=600.0,
        )

        now = 0.0

        def step(weight: float, stable: bool, dt: float = 0.5):
            nonlocal now
            now += dt
            return detector.update(now_s=now, gross_lbs=weight, is_stable=stable, cfg=cfg)

        for _ in range(4):
            self.assertIsNone(step(0.5, stable=True))

        for w in (6.0, 12.0, 25.0, 40.0, 50.0):
            self.assertIsNone(step(w, stable=False))

        for _ in range(3):
            self.assertIsNone(step(49.8, stable=True))

        # Gradual unloading: many samples remain above rise_trigger after dumping starts.
        # Older logic could treat these as a new fill and never complete the cycle.
        for w in (45.0, 42.0, 38.0, 30.0, 20.0, 12.0, 7.0, 3.0):
            self.assertIsNone(step(w, stable=False))

        evt = None
        for _ in range(5):
            evt = step(0.8, stable=True)
            if evt is not None:
                break

        self.assertIsNotNone(evt)
        assert evt is not None
        self.assertGreater(evt.processed_lbs, 40.0)

    def test_fast_cycle_without_stable_flags_still_emits_event(self) -> None:
        detector = ThroughputCycleDetector()
        cfg = ThroughputCycleConfig(
            empty_threshold_lb=2.0,
            rise_trigger_lb=8.0,
            full_min_lb=15.0,
            dump_drop_lb=6.0,
            full_stability_s=0.4,
            empty_confirm_s=0.3,
            min_processed_lb=5.0,
            max_cycle_s=600.0,
        )

        now = 0.0

        def step(weight: float, stable: bool, dt: float = 0.2):
            nonlocal now
            now += dt
            return detector.update(now_s=now, gross_lbs=weight, is_stable=stable, cfg=cfg)

        # Establish empty baseline quickly.
        for _ in range(4):
            self.assertIsNone(step(0.3, stable=True))

        # Fill phase with motion (stable=False) but enough dwell above full_min.
        for w in (5.0, 12.0, 20.0, 35.0, 48.0):
            self.assertIsNone(step(w, stable=False))
        for _ in range(3):  # 0.6 s dwell > full_stability_s
            self.assertIsNone(step(47.0, stable=False))

        # Fast dump with motion; briefly under empty threshold.
        for w in (30.0, 18.0, 9.0, 3.0):
            self.assertIsNone(step(w, stable=False))
        evt = None
        for _ in range(3):  # 0.6 s dwell > empty_confirm_s
            evt = step(1.2, stable=False)
            if evt is not None:
                break

        self.assertIsNotNone(evt)
        assert evt is not None
        self.assertGreater(evt.processed_lbs, 20.0)

    def test_negative_empty_compression_is_floored_to_baseline(self) -> None:
        detector = ThroughputCycleDetector()
        cfg = ThroughputCycleConfig(
            empty_threshold_lb=2.0,
            rise_trigger_lb=8.0,
            full_min_lb=15.0,
            dump_drop_lb=6.0,
            full_stability_s=0.4,
            empty_confirm_s=0.3,
            min_processed_lb=5.0,
            max_cycle_s=600.0,
        )

        now = 0.0

        def step(weight: float, stable: bool, dt: float = 0.2):
            nonlocal now
            now += dt
            return detector.update(now_s=now, gross_lbs=weight, is_stable=stable, cfg=cfg)

        # Empty baseline around +0.4 lb
        for _ in range(4):
            self.assertIsNone(step(0.4, stable=True))

        for w in (6.0, 14.0, 28.0, 40.0):
            self.assertIsNone(step(w, stable=False))
        for _ in range(3):  # dwell above full_min
            self.assertIsNone(step(39.0, stable=False))

        for w in (20.0, 8.0, 2.5):
            self.assertIsNone(step(w, stable=False))

        # Hopper compression at bottom drives apparent weight negative.
        evt = None
        for _ in range(3):  # dwell below empty threshold
            evt = step(-3.0, stable=False)
            if evt is not None:
                break

        self.assertIsNotNone(evt)
        assert evt is not None
        # Empty should be floored to pre-fill baseline (0.4), not -3.0.
        self.assertAlmostEqual(evt.empty_lbs, 0.4, places=3)
        # Processed should not be inflated by negative compression dip.
        self.assertLess(evt.processed_lbs, 40.0)


if __name__ == "__main__":
    unittest.main()
