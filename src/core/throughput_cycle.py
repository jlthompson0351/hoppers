from __future__ import annotations

import logging as _logging
from dataclasses import dataclass
from typing import Optional

_log = _logging.getLogger(__name__)


@dataclass(frozen=True)
class ThroughputCycleConfig:
    # Below this = hopper is empty
    empty_threshold_lb: float
    # Weight must cross this to start a fill cycle (above empty)
    rise_trigger_lb: float
    # "Full" = weight reaches this target (dynamic: set_weight * full_pct_of_target)
    full_min_lb: float
    # Dump detected when weight drops MORE than this from the peak (must be large enough
    # to ignore machine vibration - set to ~25% of set weight minimum)
    dump_drop_lb: float
    # Not used for stability gate anymore - kept for interface compatibility
    full_stability_s: float
    # Confirm empty: weight must stay below empty_threshold for this long after a dump
    empty_confirm_s: float
    # Minimum processed lbs to bother recording a cycle
    min_processed_lb: float
    # Abort fill if it takes longer than this (seconds)
    max_cycle_s: float


@dataclass(frozen=True)
class ThroughputCycleEvent:
    processed_lbs: float
    full_lbs: float
    empty_lbs: float
    duration_ms: int
    confidence: float
    fill_time_ms: int = 0
    dump_time_ms: int = 0


class ThroughputCycleDetector:
    """
    Simple fill-time tracker.

    States:
        EMPTY   — hopper near zero after a dump (or at startup)
        FILLING — weight rising, fill timer running
        FULL    — weight reached target, watching for the dump
        DUMPING — big drop detected, confirming the hopper is empty

    A "dump" is defined as: weight drops MORE than dump_drop_lb from the
    recorded peak weight. This threshold should be large enough (~25 lbs)
    to ignore normal machine vibration (~5-10 lbs) while still catching
    a real dump (typically a 50-100 lb drop).

    Fill time = time from fill_started (weight crosses rise_trigger after
    last dump) to full_reached (weight first hits full_min_lb).
    """

    def __init__(self) -> None:
        self.reset()

    @property
    def state(self) -> str:
        return self._state

    def reset(self) -> None:
        self._state = "EMPTY_STABLE"
        self._state_started_s = 0.0
        self._fill_started_s: Optional[float] = None
        self._full_reached_s: Optional[float] = None
        self._dumping_started_s: Optional[float] = None
        self._peak_lbs = 0.0
        self._full_lbs: Optional[float] = None
        self._empty_lbs: Optional[float] = None
        self._empty_confirm_started_s: Optional[float] = None
        self._dump_min_lbs: Optional[float] = None
        self._empty_baseline_lbs = 0.0
        # Once we've seen the hopper go near-empty during a dump, lock in
        # so mechanical bounce doesn't cancel the confirmation.
        self._dump_seen_near_empty: bool = False

    def _transition(self, new_state: str, now_s: float) -> None:
        _log.debug("throughput state %s -> %s", self._state, new_state)
        self._state = new_state
        self._state_started_s = now_s

    def update(
        self,
        *,
        now_s: float,
        gross_lbs: float,
        is_stable: bool,
        cfg: ThroughputCycleConfig,
    ) -> Optional[ThroughputCycleEvent]:

        # Safety: abort if a cycle has been stuck for too long
        if self._fill_started_s is not None:
            if (now_s - self._fill_started_s) > max(10.0, cfg.max_cycle_s):
                _log.info("throughput: aborting stuck fill cycle (%.0fs)", now_s - self._fill_started_s)
                self.reset()
                self._state_started_s = now_s

        # ── EMPTY_STABLE ──────────────────────────────────────────────────────
        if self._state == "EMPTY_STABLE":
            # Track baseline when truly empty and stable
            if is_stable and gross_lbs <= cfg.empty_threshold_lb:
                self._empty_baseline_lbs = max(0.0, gross_lbs)

            # Fill starts when weight rises above rise_trigger above baseline
            if gross_lbs >= (self._empty_baseline_lbs + cfg.rise_trigger_lb):
                self._fill_started_s = now_s
                self._full_reached_s = None
                self._peak_lbs = gross_lbs
                self._full_lbs = None
                self._empty_lbs = None
                self._dump_min_lbs = None
                self._empty_confirm_started_s = None
                self._dump_seen_near_empty = False
                self._transition("FILLING", now_s)
            return None

        # ── FILLING ───────────────────────────────────────────────────────────
        if self._state == "FILLING":
            # Track peak as hopper fills
            self._peak_lbs = max(self._peak_lbs, gross_lbs)

            # Abort if weight drops back to near-empty (false start / no material)
            abort_threshold = self._empty_baseline_lbs + max(0.5, cfg.rise_trigger_lb * 0.25)
            if gross_lbs <= abort_threshold:
                self.reset()
                self._state_started_s = now_s
                return None

            # Full = weight has reached the target for the first time
            if gross_lbs >= cfg.full_min_lb:
                self._full_reached_s = now_s
                self._full_lbs = self._peak_lbs  # use the peak so far as full weight
                self._transition("FULL_STABLE", now_s)
            return None

        # ── FULL_STABLE ───────────────────────────────────────────────────────
        if self._state == "FULL_STABLE":
            # Keep updating peak as weight continues to rise/settle
            self._peak_lbs = max(self._peak_lbs, gross_lbs)

            # Dump detected = weight drops by more than dump_drop_lb from the peak.
            # dump_drop_lb should be large (≥25 lbs) so normal machine vibration
            # (typically ≤10 lbs) does NOT trigger a false dump.
            dump_threshold = self._peak_lbs - cfg.dump_drop_lb
            if gross_lbs <= dump_threshold:
                # Record "full" as the peak weight just before the drop
                self._full_lbs = float(self._peak_lbs)
                self._dump_min_lbs = gross_lbs
                self._dumping_started_s = now_s
                self._empty_confirm_started_s = None
                self._dump_seen_near_empty = False
                _log.info(
                    "THROUGHPUT DUMPING: gross=%.1f peak=%.1f threshold=%.1f",
                    gross_lbs, self._peak_lbs, dump_threshold,
                )
                self._transition("DUMPING", now_s)
            return None

        # ── DUMPING ───────────────────────────────────────────────────────────
        if self._state == "DUMPING":
            if self._dump_min_lbs is None:
                self._dump_min_lbs = gross_lbs
            else:
                self._dump_min_lbs = min(self._dump_min_lbs, gross_lbs)

            if gross_lbs <= cfg.empty_threshold_lb:
                # Weight is near zero — hopper is emptying
                self._dump_seen_near_empty = True
                if self._empty_confirm_started_s is None:
                    self._empty_confirm_started_s = now_s
                elif (now_s - self._empty_confirm_started_s) >= cfg.empty_confirm_s:
                    # Confirmed empty — emit the completed cycle
                    full_lbs = float(self._full_lbs) if self._full_lbs is not None else self._peak_lbs
                    raw_empty = float(gross_lbs)
                    empty_lbs = max(raw_empty, self._empty_baseline_lbs)
                    effective_empty = max(0.0, empty_lbs)
                    processed_lbs = max(0.0, full_lbs - effective_empty)

                    fill_started = self._fill_started_s or now_s
                    full_reached = self._full_reached_s or now_s
                    dumping_started = self._dumping_started_s or now_s

                    fill_time_ms = int(max(0.0, (full_reached - fill_started) * 1000.0))
                    dump_time_ms = int(max(0.0, (now_s - dumping_started) * 1000.0))
                    duration_ms = int(max(0.0, (now_s - fill_started) * 1000.0))

                    confidence = self._confidence(
                        processed_lbs=processed_lbs,
                        full_lbs=full_lbs,
                        empty_lbs=empty_lbs,
                        cfg=cfg,
                    )

                    _log.info(
                        "THROUGHPUT CYCLE COMPLETE: processed=%.1f full=%.1f fill_ms=%d dump_ms=%d conf=%.2f",
                        processed_lbs, full_lbs, fill_time_ms, dump_time_ms, confidence,
                    )
                    self.reset()
                    self._state_started_s = now_s
                    return ThroughputCycleEvent(
                        processed_lbs=processed_lbs,
                        full_lbs=full_lbs,
                        empty_lbs=empty_lbs,
                        duration_ms=duration_ms,
                        confidence=confidence,
                        fill_time_ms=fill_time_ms,
                        dump_time_ms=dump_time_ms,
                    )
            else:
                # Weight is above empty threshold during dump
                if not self._dump_seen_near_empty:
                    # Haven't confirmed empty yet — if weight shoots back up high,
                    # the "dump" might have been a false trigger (rare but possible).
                    # Only re-enter FILLING if weight rises strongly above the
                    # old peak (suggesting a re-fill before we confirmed empty).
                    rebound_trigger = (self._dump_min_lbs or gross_lbs) + cfg.rise_trigger_lb
                    near_empty_trigger = self._empty_baseline_lbs + cfg.rise_trigger_lb
                    if gross_lbs >= max(rebound_trigger, near_empty_trigger):
                        # Re-fill started before we saw empty — treat as new fill
                        self._fill_started_s = now_s
                        self._full_reached_s = None
                        self._peak_lbs = gross_lbs
                        self._full_lbs = None
                        self._dump_min_lbs = None
                        self._empty_confirm_started_s = None
                        self._transition("FILLING", now_s)
                else:
                    # We already saw near-empty — brief mechanical bounce back up.
                    # Reset the confirm timer only if we lose the near-empty signal.
                    self._empty_confirm_started_s = None
            return None

        # Defensive fallback
        self.reset()
        self._state_started_s = now_s
        return None

    @staticmethod
    def _confidence(
        *,
        processed_lbs: float,
        full_lbs: float,
        empty_lbs: float,
        cfg: ThroughputCycleConfig,
    ) -> float:
        score = 0.55
        if full_lbs >= cfg.full_min_lb:
            score += 0.15
        if abs(empty_lbs) <= cfg.empty_threshold_lb:
            score += 0.10
        if processed_lbs >= (cfg.min_processed_lb * 2.0):
            score += 0.10
        if processed_lbs >= (cfg.rise_trigger_lb * 0.8):
            score += 0.05
        if full_lbs > empty_lbs:
            score += 0.05
        return max(0.0, min(0.99, score))
