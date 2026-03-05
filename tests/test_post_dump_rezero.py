from __future__ import annotations

import unittest
from dataclasses import dataclass

from src.core.post_dump_rezero import PostDumpRezeroConfig, PostDumpRezeroController


@dataclass(frozen=True)
class _Point:
    known_weight_lbs: float
    signal: float


class PostDumpRezeroTests(unittest.TestCase):
    def _points(self) -> list[_Point]:
        # 0 lb at 5.00 mV, 10 lb at 5.10 mV => 100 lb/mV near zero
        return [_Point(known_weight_lbs=0.0, signal=5.00), _Point(known_weight_lbs=10.0, signal=5.10)]

    def test_idle_until_triggered(self) -> None:
        ctrl = PostDumpRezeroController()
        cfg = PostDumpRezeroConfig(
            enabled=True,
            min_delay_s=1.0,
            window_s=10.0,
            empty_threshold_lb=4.0,
            max_correction_lb=8.0,
        )
        step = ctrl.update(
            now_s=0.0,
            raw_mv=5.00,
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=0.0,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertFalse(step.active)
        self.assertEqual(step.state, "idle")

    def test_waits_min_delay_then_applies_one_shot(self) -> None:
        ctrl = PostDumpRezeroController()
        cfg = PostDumpRezeroConfig(
            enabled=True,
            min_delay_s=1.0,
            window_s=10.0,
            empty_threshold_lb=4.0,
            max_correction_lb=8.0,
        )
        ctrl.trigger(now_s=0.0)

        settling = ctrl.update(
            now_s=0.5,
            raw_mv=5.03,
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=0.0,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertTrue(settling.active)
        self.assertEqual(settling.state, "settling")

        applied = ctrl.update(
            now_s=1.0,
            raw_mv=5.03,  # drift_mv=0.03 => 3 lb
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=0.0,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertTrue(applied.should_apply)
        self.assertEqual(applied.state, "applied")
        self.assertAlmostEqual(float(applied.new_zero_offset_mv or 0.0), 0.03, places=6)
        self.assertAlmostEqual(float(applied.new_zero_offset_lbs or 0.0), 3.0, places=6)

        # After one-shot apply, continue telemetry tracking until fill resumes.
        waiting_fill = ctrl.update(
            now_s=1.1,
            raw_mv=5.03,
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=0.03,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertEqual(waiting_fill.state, "applied_waiting_fill_resume")
        self.assertIsNone(waiting_fill.time_to_fill_resume_s)
        self.assertFalse(waiting_fill.should_apply)

        completed = ctrl.update(
            now_s=1.6,
            raw_mv=5.07,
            gross_lbs=7.0,
            is_stable=False,
            current_zero_offset_mv=0.03,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertEqual(completed.state, "completed")
        self.assertEqual(completed.reason, "fill_resumed")
        self.assertAlmostEqual(float(completed.time_to_fill_resume_s or 0.0), 1.6, places=3)

        idle = ctrl.update(
            now_s=1.7,
            raw_mv=5.03,
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=0.03,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertEqual(idle.state, "idle")

    def test_requires_stable(self) -> None:
        ctrl = PostDumpRezeroController()
        cfg = PostDumpRezeroConfig(
            enabled=True,
            min_delay_s=0.0,
            window_s=10.0,
            empty_threshold_lb=4.0,
            max_correction_lb=8.0,
        )
        ctrl.trigger(now_s=0.0)
        step = ctrl.update(
            now_s=1.0,
            raw_mv=5.02,
            gross_lbs=0.0,
            is_stable=False,
            current_zero_offset_mv=0.0,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertTrue(step.active)
        self.assertEqual(step.state, "waiting_stable")

    def test_requires_empty(self) -> None:
        ctrl = PostDumpRezeroController()
        cfg = PostDumpRezeroConfig(
            enabled=True,
            min_delay_s=0.0,
            window_s=10.0,
            empty_threshold_lb=4.0,
            max_correction_lb=8.0,
        )
        ctrl.trigger(now_s=0.0)
        step = ctrl.update(
            now_s=1.0,
            raw_mv=5.01,
            gross_lbs=6.0,  # not empty
            is_stable=True,
            current_zero_offset_mv=0.0,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertTrue(step.active)
        self.assertEqual(step.state, "waiting_empty")

    def test_skips_when_raw_drift_exceeds_max(self) -> None:
        ctrl = PostDumpRezeroController()
        cfg = PostDumpRezeroConfig(
            enabled=True,
            min_delay_s=0.0,
            window_s=10.0,
            empty_threshold_lb=4.0,
            max_correction_lb=8.0,
        )
        ctrl.trigger(now_s=0.0)
        step = ctrl.update(
            now_s=1.0,
            raw_mv=5.09,  # drift_mv=0.09 => 9 lb > max(8)
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=0.0,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertFalse(step.active)
        self.assertEqual(step.state, "skipped")
        self.assertEqual(step.reason, "drift_too_large")
        self.assertFalse(step.should_apply)

    def test_skips_when_delta_exceeds_max(self) -> None:
        ctrl = PostDumpRezeroController()
        cfg = PostDumpRezeroConfig(
            enabled=True,
            min_delay_s=0.0,
            window_s=10.0,
            empty_threshold_lb=4.0,
            max_correction_lb=8.0,
        )
        ctrl.trigger(now_s=0.0)

        # drift_mv=0.05 => drift_lbs=5, but current offset implies -10 lb,
        # so delta is 15 lb which exceeds max.
        current_zero_offset_mv = -0.10  # -10 lb at 100 lb/mV
        step = ctrl.update(
            now_s=1.0,
            raw_mv=5.05,
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=current_zero_offset_mv,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertEqual(step.state, "skipped")
        self.assertEqual(step.reason, "correction_too_large")
        self.assertFalse(step.should_apply)

    def test_expires_window(self) -> None:
        ctrl = PostDumpRezeroController()
        cfg = PostDumpRezeroConfig(
            enabled=True,
            min_delay_s=0.0,
            window_s=1.0,
            empty_threshold_lb=4.0,
            max_correction_lb=8.0,
        )
        ctrl.trigger(now_s=0.0)
        step = ctrl.update(
            now_s=2.0,
            raw_mv=5.00,
            gross_lbs=0.0,
            is_stable=True,
            current_zero_offset_mv=0.0,
            cal_points=self._points(),
            cfg=cfg,
        )
        self.assertEqual(step.state, "expired")


if __name__ == "__main__":
    unittest.main()

