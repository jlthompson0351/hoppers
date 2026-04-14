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
    # Legacy/deprecated (previous hopper-specific negative fast-path).
    # Kept only for backward compatibility with existing configs/routes.
    negative_hold_s: float = 1.0
    startup_lockout_s: float = 120.0   # No auto-zero for first 2 minutes after boot
    max_correction_lb: float = 20.0    # Reject any single correction larger than this


@dataclass(frozen=True)
class ZeroTrackingStep:
    zero_offset_delta_lbs: float
    weight_correction_lbs: float
    active: bool
    locked: bool
    reason: str
    should_persist: bool
    hold_elapsed_s: float


class ZeroTracker:
    """Stateful AZT (Automatic Zero Tracking) gate + rate-limited engine.

    This module implements ONLY the continuous/micro-range AZT behavior
    used by commercial indicators:
      - Only operate near true zero (tight range gate).
      - Only when stable (no motion) and no spikes detected.
      - Always rate-limited (never instant-correct).

    Larger corrections must be handled by a separate, state-aware
    post-process (e.g. post-dump re-zero in the batch/cycle logic).
    """

    def __init__(self) -> None:
        self._gate_started_s: Optional[float] = None
        self._last_persist_s: float = -1e9
        self._boot_time_s: Optional[float] = None  # Set on first step()

    def reset(self) -> None:
        self._gate_started_s = None
        self._last_persist_s = -1e9
        # Note: boot time is NOT reset -- it's a one-time anchor

    def _locked(
        self,
        *,
        zero_offset_lbs: float,
        reason: str,
        hold_elapsed_s: float = 0.0,
        reset_gate: bool = True,
    ) -> ZeroTrackingStep:
        if reset_gate:
            self._gate_started_s = None
        if zero_offset_lbs is not None:
            _ = float(zero_offset_lbs)  # Kept for call-site compatibility
        return ZeroTrackingStep(
            zero_offset_delta_lbs=0.0,
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
        display_lbs: float,
        tare_offset_lbs: float,
        is_stable: bool,
        current_zero_offset_lbs: float,
        cfg: ZeroTrackingConfig,
        spike_detected: bool = False,
    ) -> ZeroTrackingStep:
        """Compute next zero tracking step.

        Args:
            display_lbs: Weight after calibration and zero offset, before tare.
                         This is what the operator sees (ignoring tare).
                         Should be ~0 when the scale is empty.
            current_zero_offset_lbs: Current zero offset in pounds.
        """
        now_s = float(now_s)
        dt_s = max(1e-6, float(dt_s))
        display_lbs = float(display_lbs)
        tare_offset_lbs = float(tare_offset_lbs)
        current_zero_offset_lbs = float(current_zero_offset_lbs)

        # ── Startup lockout (wait for ADC/signal to stabilize) ────
        if self._boot_time_s is None:
            self._boot_time_s = now_s
        uptime_s = now_s - self._boot_time_s

        # ── Universal gates (always apply) ────────────────────────
        if not cfg.enabled:
            return self._locked(zero_offset_lbs=current_zero_offset_lbs, reason="disabled")
        if uptime_s < float(cfg.startup_lockout_s):
            return self._locked(zero_offset_lbs=current_zero_offset_lbs, reason="startup_lockout")
        if abs(tare_offset_lbs) > 1e-6:
            return self._locked(zero_offset_lbs=current_zero_offset_lbs, reason="tare_active")
        # Range gate: AZT only operates extremely close to true zero.
        if abs(display_lbs) > float(cfg.range_lb):
            return self._locked(zero_offset_lbs=current_zero_offset_lbs, reason="load_present")

        if not is_stable:
            return self._locked(
                zero_offset_lbs=current_zero_offset_lbs,
                reason="unstable",
            )
        if spike_detected:
            return self._locked(
                zero_offset_lbs=current_zero_offset_lbs,
                reason="spike",
            )

        if self._gate_started_s is None:
            self._gate_started_s = now_s
        hold_elapsed_s = max(0.0, now_s - self._gate_started_s)
        if hold_elapsed_s < float(cfg.hold_s):
            return self._locked(
                zero_offset_lbs=current_zero_offset_lbs,
                reason="holdoff",
                hold_elapsed_s=hold_elapsed_s,
                reset_gate=False,
            )

        if abs(display_lbs) <= float(cfg.deadband_lb):
            return ZeroTrackingStep(
                zero_offset_delta_lbs=0.0,
                weight_correction_lbs=0.0,
                active=True,
                locked=False,
                reason="deadband",
                should_persist=False,
                hold_elapsed_s=hold_elapsed_s,
            )

        # Rate-limited correction (always enforced, both signs).
        max_correction_lb = max(0.0, float(cfg.rate_lbs)) * dt_s
        if max_correction_lb <= 0.0:
            return ZeroTrackingStep(
                zero_offset_delta_lbs=0.0,
                weight_correction_lbs=0.0,
                active=True,
                locked=False,
                reason="rate_limited_to_zero",
                should_persist=False,
                hold_elapsed_s=hold_elapsed_s,
            )

        # Clamp correction to rate limit
        weight_correction_lbs = max(-max_correction_lb, min(max_correction_lb, display_lbs))

        should_persist = (
            abs(weight_correction_lbs) > 1e-12
            and (now_s - self._last_persist_s) >= float(cfg.persist_interval_s)
        )
        if should_persist:
            self._last_persist_s = now_s

        return ZeroTrackingStep(
            zero_offset_delta_lbs=weight_correction_lbs,
            weight_correction_lbs=weight_correction_lbs,
            active=True,
            locked=False,
            reason="tracking",
            should_persist=should_persist,
            hold_elapsed_s=hold_elapsed_s,
        )
