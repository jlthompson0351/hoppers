from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Protocol

from src.core.zeroing import calibration_zero_signal, estimate_lbs_per_mv


class CalibrationPointLike(Protocol):
    known_weight_lbs: float
    signal: float


EventSink = Callable[[str, str, str, Optional[dict]], None]


@dataclass(frozen=True)
class PostDumpRezeroConfig:
    enabled: bool
    min_delay_s: float
    window_s: float
    empty_threshold_lb: float
    max_correction_lb: float


@dataclass(frozen=True)
class PostDumpRezeroStep:
    """One update result from the post-dump controller."""

    active: bool
    state: str
    reason: str
    dump_age_s: float

    should_apply: bool = False
    new_zero_offset_mv: Optional[float] = None
    new_zero_offset_lbs: Optional[float] = None
    drift_mv: Optional[float] = None
    drift_lbs: Optional[float] = None
    delta_offset_lbs: Optional[float] = None

    time_to_stable_s: Optional[float] = None
    time_to_empty_s: Optional[float] = None
    time_to_fill_resume_s: Optional[float] = None


class PostDumpRezeroController:
    """State-aware post-dump re-zero (one-shot) controller.

    This is intentionally NOT continuous zero tracking. It only arms when a dump is
    detected by the throughput/cycle state machine, then attempts a single capture
    of the new zero reference once the scale has settled and the hopper is empty.
    """

    def __init__(self, *, event_sink: Optional[EventSink] = None) -> None:
        self._event_sink = event_sink
        self.reset()

    def reset(self) -> None:
        self._dump_time_s: Optional[float] = None
        self._first_stable_s: Optional[float] = None
        self._first_empty_s: Optional[float] = None
        self._fill_resume_s: Optional[float] = None
        self._apply_requested: bool = False

    def trigger(self, *, now_s: float) -> None:
        """Arm the controller after a detected dump event."""
        self._dump_time_s = float(now_s)
        self._first_stable_s = None
        self._first_empty_s = None
        self._fill_resume_s = None
        self._apply_requested = False
        self._emit(
            level="INFO",
            code="POST_DUMP_REZERO_TRIGGERED",
            message="Post-dump re-zero armed.",
            details={"dump_time_s": float(now_s)},
        )

    def update(
        self,
        *,
        now_s: float,
        raw_mv: float,
        gross_lbs: float,
        is_stable: bool,
        current_zero_offset_mv: float,
        cal_points: Iterable[CalibrationPointLike],
        cfg: PostDumpRezeroConfig,
    ) -> PostDumpRezeroStep:
        """Advance the post-dump controller and (optionally) request a re-zero apply.

        Args:
            gross_lbs: Current gross weight (already zeroed, before tare).
            current_zero_offset_mv: Current stored zero offset (canonical signal-domain value).
        """
        now_s = float(now_s)
        dump_time = self._dump_time_s

        if not cfg.enabled:
            # If disabled while armed, drop state silently (no spam).
            self.reset()
            return PostDumpRezeroStep(active=False, state="disabled", reason="disabled", dump_age_s=0.0)

        if dump_time is None:
            return PostDumpRezeroStep(active=False, state="idle", reason="idle", dump_age_s=0.0)

        age_s = max(0.0, now_s - float(dump_time))
        window_s = max(0.0, float(cfg.window_s))
        if window_s > 0.0 and age_s > window_s:
            step = PostDumpRezeroStep(
                active=False,
                state="expired",
                reason="window_expired",
                dump_age_s=age_s,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )
            self._emit(
                level="WARNING",
                code="POST_DUMP_REZERO_EXPIRED",
                message="Post-dump re-zero window expired (no correction applied).",
                details={
                    "dump_age_s": age_s,
                    "window_s": window_s,
                    "time_to_stable_s": step.time_to_stable_s,
                    "time_to_empty_s": step.time_to_empty_s,
                    "time_to_fill_resume_s": step.time_to_fill_resume_s,
                },
            )
            self.reset()
            return step

        if is_stable and self._first_stable_s is None:
            self._first_stable_s = now_s
        if abs(float(gross_lbs)) <= float(cfg.empty_threshold_lb) and self._first_empty_s is None:
            self._first_empty_s = now_s

        # Fill-resume telemetry (best-effort): after we've seen "empty", record when
        # weight rises meaningfully above the empty threshold again.
        if self._first_empty_s is not None and self._fill_resume_s is None:
            fill_resume_threshold = float(cfg.empty_threshold_lb) + max(1.0, float(cfg.empty_threshold_lb) * 0.5)
            if float(gross_lbs) > fill_resume_threshold:
                self._fill_resume_s = now_s

        if self._apply_requested:
            # After one-shot apply, keep telemetry armed long enough to measure
            # when fill resumes; this metric is useful for cycle timing analysis.
            if self._fill_resume_s is not None:
                step = PostDumpRezeroStep(
                    active=False,
                    state="completed",
                    reason="fill_resumed",
                    dump_age_s=age_s,
                    time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                    time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                    time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
                )
                self._emit(
                    level="INFO",
                    code="POST_DUMP_REZERO_FILL_RESUME",
                    message="Post-dump fill resumed.",
                    details={
                        "dump_age_s": age_s,
                        "time_to_stable_s": step.time_to_stable_s,
                        "time_to_empty_s": step.time_to_empty_s,
                        "time_to_fill_resume_s": step.time_to_fill_resume_s,
                    },
                )
                self.reset()
                return step

            return PostDumpRezeroStep(
                active=False,
                state="applied_waiting_fill_resume",
                reason="awaiting_fill_resume",
                dump_age_s=age_s,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )

        min_delay_s = max(0.0, float(cfg.min_delay_s))
        if age_s < min_delay_s:
            return PostDumpRezeroStep(
                active=True,
                state="settling",
                reason="min_delay",
                dump_age_s=age_s,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )

        if not is_stable:
            return PostDumpRezeroStep(
                active=True,
                state="waiting_stable",
                reason="unstable",
                dump_age_s=age_s,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )

        # Empty gate: do not apply if hopper is not clearly empty.
        if abs(float(gross_lbs)) > float(cfg.empty_threshold_lb):
            return PostDumpRezeroStep(
                active=True,
                state="waiting_empty",
                reason="not_empty",
                dump_age_s=age_s,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )

        slope_near_zero = estimate_lbs_per_mv(cal_points)
        if slope_near_zero is None or abs(float(slope_near_zero)) <= 1e-9:
            step = PostDumpRezeroStep(
                active=False,
                state="skipped",
                reason="no_cal_slope",
                dump_age_s=age_s,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )
            self._emit(
                level="WARNING",
                code="POST_DUMP_REZERO_SKIPPED",
                message="Post-dump re-zero skipped (calibration slope unavailable).",
                details={"reason": step.reason, "dump_age_s": age_s},
            )
            self.reset()
            return step

        cal_zero_sig = calibration_zero_signal(cal_points)
        drift_mv = float(raw_mv) - float(cal_zero_sig)
        drift_lbs = drift_mv * float(slope_near_zero)

        # Absolute drift guard: if the raw signal implies a large non-zero weight,
        # do not attempt to capture a new zero automatically.
        if abs(drift_lbs) > float(cfg.max_correction_lb):
            step = PostDumpRezeroStep(
                active=False,
                state="skipped",
                reason="drift_too_large",
                dump_age_s=age_s,
                drift_mv=drift_mv,
                drift_lbs=drift_lbs,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )
            self._emit(
                level="WARNING",
                code="POST_DUMP_REZERO_SKIPPED",
                message="Post-dump re-zero skipped (raw drift exceeds max).",
                details={
                    "reason": step.reason,
                    "dump_age_s": age_s,
                    "gross_lbs": float(gross_lbs),
                    "drift_mv": drift_mv,
                    "drift_lbs": drift_lbs,
                    "max_correction_lb": float(cfg.max_correction_lb),
                },
            )
            self.reset()
            return step

        # Correction limit: apply only if the correction delta is within the allowed bound.
        delta_mv = drift_mv - float(current_zero_offset_mv)
        delta_lbs = delta_mv * float(slope_near_zero)
        if abs(delta_lbs) > float(cfg.max_correction_lb):
            step = PostDumpRezeroStep(
                active=False,
                state="skipped",
                reason="correction_too_large",
                dump_age_s=age_s,
                drift_mv=drift_mv,
                drift_lbs=drift_lbs,
                delta_offset_lbs=delta_lbs,
                time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
                time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
                time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
            )
            self._emit(
                level="WARNING",
                code="POST_DUMP_REZERO_SKIPPED",
                message="Post-dump re-zero skipped (correction exceeds max).",
                details={
                    "reason": step.reason,
                    "dump_age_s": age_s,
                    "gross_lbs": float(gross_lbs),
                    "drift_mv": drift_mv,
                    "drift_lbs": drift_lbs,
                    "delta_offset_lbs": delta_lbs,
                    "max_correction_lb": float(cfg.max_correction_lb),
                },
            )
            self.reset()
            return step

        # Request apply: set canonical offset to the signal drift relative to cal-zero.
        new_zero_offset_mv = drift_mv
        new_zero_offset_lbs = drift_lbs

        step = PostDumpRezeroStep(
            active=False,
            state="applied",
            reason="rezero",
            dump_age_s=age_s,
            should_apply=True,
            new_zero_offset_mv=new_zero_offset_mv,
            new_zero_offset_lbs=new_zero_offset_lbs,
            drift_mv=drift_mv,
            drift_lbs=drift_lbs,
            delta_offset_lbs=delta_lbs,
            time_to_stable_s=self._delta_or_none(self._first_stable_s, dump_time),
            time_to_empty_s=self._delta_or_none(self._first_empty_s, dump_time),
            time_to_fill_resume_s=self._delta_or_none(self._fill_resume_s, dump_time),
        )

        self._emit(
            level="INFO",
            code="POST_DUMP_REZERO_APPLY_REQUEST",
            message="Post-dump re-zero requested (one-shot capture).",
            details={
                "dump_age_s": age_s,
                "gross_lbs": float(gross_lbs),
                "new_zero_offset_mv": new_zero_offset_mv,
                "new_zero_offset_lbs": new_zero_offset_lbs,
                "delta_offset_lbs": delta_lbs,
                "empty_threshold_lb": float(cfg.empty_threshold_lb),
                "max_correction_lb": float(cfg.max_correction_lb),
                "time_to_stable_s": step.time_to_stable_s,
                "time_to_empty_s": step.time_to_empty_s,
                "time_to_fill_resume_s": step.time_to_fill_resume_s,
            },
        )
        # One-shot apply requested: keep telemetry armed until fill resumes so
        # time_to_fill_resume_s can be captured reliably.
        self._apply_requested = True
        return step

    def _emit(self, *, level: str, code: str, message: str, details: Optional[dict]) -> None:
        if self._event_sink is None:
            return
        try:
            self._event_sink(str(level), str(code), str(message), details)
        except Exception:
            # Never allow telemetry to break acquisition loop behavior.
            return

    @staticmethod
    def _delta_or_none(ts: Optional[float], anchor: float) -> Optional[float]:
        if ts is None:
            return None
        return max(0.0, float(ts) - float(anchor))

