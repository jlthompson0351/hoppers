from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ThroughputCycleConfig:
    empty_threshold_lb: float
    rise_trigger_lb: float
    full_min_lb: float
    dump_drop_lb: float
    full_stability_s: float
    empty_confirm_s: float
    min_processed_lb: float
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
    """Detect hopper fill/dump cycles and emit one completed event per cycle."""

    def __init__(self) -> None:
        self.reset()

    @property
    def state(self) -> str:
        """Read-only access to the current detector state."""
        return self._state

    def reset(self) -> None:
        self._state = "EMPTY_STABLE"
        self._state_started_s = 0.0
        self._empty_baseline_lbs = 0.0
        self._fill_started_s: Optional[float] = None
        self._full_stable_started_s: Optional[float] = None
        self._dumping_started_s: Optional[float] = None
        self._peak_lbs = 0.0
        self._full_lbs: Optional[float] = None
        self._last_stable_full_lbs: Optional[float] = None
        self._full_candidate_s: Optional[float] = None
        self._empty_confirm_started_s: Optional[float] = None
        self._dump_min_lbs: Optional[float] = None

    def _transition(self, new_state: str, now_s: float) -> None:
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
        # Guard against stale/incomplete cycles.
        if self._fill_started_s is not None and (now_s - self._fill_started_s) > max(5.0, cfg.max_cycle_s):
            self.reset()
            self._state_started_s = now_s

        if self._state == "EMPTY_STABLE":
            if is_stable and gross_lbs <= cfg.empty_threshold_lb:
                # Baseline must represent "near-empty" around zero.
                # Negative compression/drift can appear briefly; if we let that
                # become the baseline, rise-trigger math can start false fills.
                self._empty_baseline_lbs = max(0.0, gross_lbs)
            if gross_lbs >= (self._empty_baseline_lbs + cfg.rise_trigger_lb):
                self._fill_started_s = now_s
                self._peak_lbs = gross_lbs
                self._full_lbs = None
                self._last_stable_full_lbs = None
                self._full_candidate_s = None
                self._empty_confirm_started_s = None
                self._dump_min_lbs = None
                self._transition("FILLING", now_s)
            return None

        if self._state == "FILLING":
            self._peak_lbs = max(self._peak_lbs, gross_lbs)
            if is_stable and gross_lbs >= cfg.full_min_lb:
                self._last_stable_full_lbs = gross_lbs

            # Full detection should not require "stable" in violent hopper motion.
            # We still require sustained time above threshold via full_stability_s.
            if gross_lbs >= cfg.full_min_lb:
                if self._full_candidate_s is None:
                    self._full_candidate_s = now_s
                elif (now_s - self._full_candidate_s) >= cfg.full_stability_s:
                    self._full_lbs = max(self._peak_lbs, gross_lbs)
                    self._full_stable_started_s = now_s
                    self._transition("FULL_STABLE", now_s)
            else:
                self._full_candidate_s = None

            # Abort a false start if load returns near empty quickly.
            if gross_lbs <= (self._empty_baseline_lbs + max(0.5, cfg.rise_trigger_lb * 0.25)):
                self.reset()
                self._state_started_s = now_s
            return None

        if self._state == "FULL_STABLE":
            self._peak_lbs = max(self._peak_lbs, gross_lbs)
            if is_stable and gross_lbs >= cfg.full_min_lb:
                self._last_stable_full_lbs = gross_lbs
            ref_full = self._full_lbs if self._full_lbs is not None else self._peak_lbs
            if gross_lbs <= (ref_full - cfg.dump_drop_lb):
                self._empty_confirm_started_s = None
                self._dump_min_lbs = gross_lbs
                # Reported "full" should represent the last stable pre-dump reading
                # when available, not a transient peak spike.
                if self._last_stable_full_lbs is not None:
                    self._full_lbs = float(self._last_stable_full_lbs)
                elif self._full_lbs is None:
                    self._full_lbs = ref_full
                self._dumping_started_s = now_s
                self._transition("DUMPING", now_s)
            return None

        if self._state == "DUMPING":
            if self._dump_min_lbs is None:
                self._dump_min_lbs = gross_lbs
            else:
                self._dump_min_lbs = min(self._dump_min_lbs, gross_lbs)

            # Empty confirm is based on dwell time below threshold; no strict stability requirement.
            # Violent machines often rebound/sway and never satisfy external "stable" logic in time.
            if gross_lbs <= cfg.empty_threshold_lb:
                if self._empty_confirm_started_s is None:
                    self._empty_confirm_started_s = now_s
                elif (now_s - self._empty_confirm_started_s) >= cfg.empty_confirm_s:
                    full_lbs = (
                        float(self._full_lbs)
                        if self._full_lbs is not None
                        else float(self._peak_lbs)
                    )
                    # Pull-type load cells can dip negative when the hopper compresses
                    # at the bottom of travel. Floor empty to pre-fill baseline so we do
                    # not overcount processed weight because of this transient.
                    raw_empty_lbs = gross_lbs
                    empty_lbs = max(raw_empty_lbs, self._empty_baseline_lbs)
                    
                    # If empty weight is negative (drift), ignore it for the processed total
                    # so we don't inflate the dump size. We still report the negative empty_lbs
                    # for diagnostics and auto-zero tracking.
                    effective_empty_lbs = max(0.0, empty_lbs)
                    processed_lbs = max(0.0, full_lbs - effective_empty_lbs)
                    duration_ms = int(max(0.0, (now_s - (self._fill_started_s or now_s))) * 1000.0)
                    fill_time_ms = int(max(0.0, (
                        (self._full_stable_started_s or now_s) - (self._fill_started_s or now_s)
                    )) * 1000.0)
                    dump_time_ms = int(max(0.0, (
                        now_s - (self._dumping_started_s or now_s)
                    )) * 1000.0)
                    confidence = self._confidence(
                        processed_lbs=processed_lbs,
                        full_lbs=full_lbs,
                        empty_lbs=empty_lbs,
                        cfg=cfg,
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
                self._empty_confirm_started_s = None

            # If weight rebounds strongly after making dump progress, treat as a new fill.
            # This avoids falsely restarting while the weight is still descending.
            dump_min = self._dump_min_lbs if self._dump_min_lbs is not None else gross_lbs
            rebound_trigger = dump_min + cfg.rise_trigger_lb
            near_empty_trigger = self._empty_baseline_lbs + cfg.rise_trigger_lb
            if gross_lbs >= max(rebound_trigger, near_empty_trigger):
                self._fill_started_s = now_s
                self._full_stable_started_s = None
                self._dumping_started_s = None
                self._peak_lbs = gross_lbs
                self._full_lbs = None
                self._last_stable_full_lbs = None
                self._full_candidate_s = None
                self._empty_confirm_started_s = None
                self._dump_min_lbs = None
                self._transition("FILLING", now_s)
            return None

        # Defensive fallback.
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
