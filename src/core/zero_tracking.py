from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ZeroTrackingConfig:
    enabled: bool
    range_lb: float
    deadband_lb: float
    hold_s: float
    rate_lbs: float
    persist_interval_s: float


@dataclass(frozen=True)
class ZeroTrackingStep:
    zero_offset_mv: float
    signal_correction_mv: float
    weight_correction_lbs: float
    active: bool
    locked: bool
    reason: str
    should_persist: bool
    hold_elapsed_s: float


class ZeroTracker:
    """Stateful zero-tracking gate + rate-limited correction engine."""

    def __init__(self) -> None:
        self._gate_started_s: Optional[float] = None
        self._last_persist_s: float = -1e9

    def reset(self) -> None:
        self._gate_started_s = None
        self._last_persist_s = -1e9

    def _locked(
        self,
        *,
        zero_offset_mv: float,
        reason: str,
        hold_elapsed_s: float = 0.0,
        reset_gate: bool = True,
    ) -> ZeroTrackingStep:
        if reset_gate:
            self._gate_started_s = None
        return ZeroTrackingStep(
            zero_offset_mv=float(zero_offset_mv),
            signal_correction_mv=0.0,
            weight_correction_lbs=0.0,
            active=False,
            locked=True,
            reason=reason,
            should_persist=False,
            hold_elapsed_s=max(0.0, float(hold_elapsed_s)),
        )

    def step(
        self,
        *,
        now_s: float,
        dt_s: float,
        filtered_lbs: float,
        tare_offset_lbs: float,
        is_stable: bool,
        lbs_per_mv: Optional[float],
        current_zero_offset_mv: float,
        cfg: ZeroTrackingConfig,
        spike_detected: bool = False,
    ) -> ZeroTrackingStep:
        now_s = float(now_s)
        dt_s = max(1e-6, float(dt_s))
        filtered_lbs = float(filtered_lbs)
        tare_offset_lbs = float(tare_offset_lbs)
        current_zero_offset_mv = float(current_zero_offset_mv)

        if not cfg.enabled:
            return self._locked(zero_offset_mv=current_zero_offset_mv, reason="disabled")
        if not is_stable:
            return self._locked(zero_offset_mv=current_zero_offset_mv, reason="unstable")
        if spike_detected:
            return self._locked(zero_offset_mv=current_zero_offset_mv, reason="spike")
        if abs(tare_offset_lbs) > 1e-6:
            return self._locked(zero_offset_mv=current_zero_offset_mv, reason="tare_active")
        if abs(filtered_lbs) > float(cfg.range_lb):
            return self._locked(zero_offset_mv=current_zero_offset_mv, reason="load_present")
        if lbs_per_mv is None or abs(float(lbs_per_mv)) <= 1e-9:
            return self._locked(zero_offset_mv=current_zero_offset_mv, reason="no_calibration")

        if self._gate_started_s is None:
            self._gate_started_s = now_s
        hold_elapsed_s = max(0.0, now_s - self._gate_started_s)
        if hold_elapsed_s < float(cfg.hold_s):
            return self._locked(
                zero_offset_mv=current_zero_offset_mv,
                reason="holdoff",
                hold_elapsed_s=hold_elapsed_s,
                reset_gate=False,
            )

        if abs(filtered_lbs) <= float(cfg.deadband_lb):
            return ZeroTrackingStep(
                zero_offset_mv=current_zero_offset_mv,
                signal_correction_mv=0.0,
                weight_correction_lbs=0.0,
                active=True,
                locked=False,
                reason="deadband",
                should_persist=False,
                hold_elapsed_s=hold_elapsed_s,
            )

        max_correction_lb = max(0.0, float(cfg.rate_lbs)) * dt_s
        if max_correction_lb <= 0.0:
            return ZeroTrackingStep(
                zero_offset_mv=current_zero_offset_mv,
                signal_correction_mv=0.0,
                weight_correction_lbs=0.0,
                active=True,
                locked=False,
                reason="rate_limited_to_zero",
                should_persist=False,
                hold_elapsed_s=hold_elapsed_s,
            )

        weight_correction_lbs = max(-max_correction_lb, min(max_correction_lb, filtered_lbs))
        signal_correction_mv = weight_correction_lbs / float(lbs_per_mv)
        next_zero_offset_mv = current_zero_offset_mv + signal_correction_mv

        should_persist = (
            abs(signal_correction_mv) > 1e-12
            and (now_s - self._last_persist_s) >= float(cfg.persist_interval_s)
        )
        if should_persist:
            self._last_persist_s = now_s

        return ZeroTrackingStep(
            zero_offset_mv=next_zero_offset_mv,
            signal_correction_mv=signal_correction_mv,
            weight_correction_lbs=weight_correction_lbs,
            active=True,
            locked=False,
            reason="tracking",
            should_persist=should_persist,
            hold_elapsed_s=hold_elapsed_s,
        )
