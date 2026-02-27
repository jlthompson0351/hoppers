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
    def __init__(self) -> None:
        self._gate_started_s: Optional[float] = None
        self._last_persist_s: float = -1e9

    def reset(self) -> None:
        self._gate_started_s = None
        self._last_persist_s = -1e9

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
        current_zero_offset_mv = float(current_zero_offset_mv)
        lbs_per_mv = float(lbs_per_mv or 0.0)

        def _locked(reason: str, hold: float = 0.0) -> ZeroTrackingStep:
            self._gate_started_s = None
            return ZeroTrackingStep(
                zero_offset_mv=current_zero_offset_mv,
                signal_correction_mv=0.0,
                weight_correction_lbs=0.0,
                active=False,
                locked=True,
                reason=reason,
                should_persist=False,
                hold_elapsed_s=max(0.0, hold),
            )

        if not cfg.enabled:
            return _locked("disabled")
        if abs(tare_offset_lbs) > 1e-6:
            return _locked("tare_active")
        if abs(filtered_lbs) > float(cfg.range_lb):
            return _locked("load_present")
        if not is_stable:
            return _locked("unstable")
        if spike_detected:
            return _locked("spike")

        if self._gate_started_s is None:
            self._gate_started_s = now_s
        hold_elapsed = max(0.0, now_s - self._gate_started_s)
        if hold_elapsed < float(cfg.hold_s):
            return ZeroTrackingStep(
                zero_offset_mv=current_zero_offset_mv,
                signal_correction_mv=0.0,
                weight_correction_lbs=0.0,
                active=False,
                locked=True,
                reason="holdoff",
                should_persist=False,
                hold_elapsed_s=hold_elapsed,
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
                hold_elapsed_s=hold_elapsed,
            )

        max_correction_lb = max(0.0, float(cfg.rate_lbs)) * dt_s
        if max_correction_lb <= 0.0 or abs(lbs_per_mv) <= 1e-9:
            return ZeroTrackingStep(
                zero_offset_mv=current_zero_offset_mv,
                signal_correction_mv=0.0,
                weight_correction_lbs=0.0,
                active=True,
                locked=False,
                reason="rate_zero",
                should_persist=False,
                hold_elapsed_s=hold_elapsed,
            )

        weight_correction = max(-max_correction_lb, min(max_correction_lb, filtered_lbs))
        signal_correction = weight_correction / lbs_per_mv
        new_offset = current_zero_offset_mv + signal_correction

        should_persist = (
            abs(signal_correction) > 1e-12
            and (now_s - self._last_persist_s) >= float(cfg.persist_interval_s)
        )
        if should_persist:
            self._last_persist_s = now_s

        return ZeroTrackingStep(
            zero_offset_mv=new_offset,
            signal_correction_mv=signal_correction,
            weight_correction_lbs=weight_correction,
            active=True,
            locked=False,
            reason="tracking",
            should_persist=should_persist,
            hold_elapsed_s=hold_elapsed,
        )
