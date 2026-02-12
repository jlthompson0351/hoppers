"""Acquisition loop for summing-board scale transmitter.

Reads one DAQ channel, applies Kalman filtering and linear scaling,
writes proportional 0-10V (or 4-20mA) to MegaIND for PLC.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from src.core.filtering import KalmanFilter, StabilityDetector
from src.core.plc_profile import PlcProfileCurve
from src.core.throughput_cycle import ThroughputCycleConfig, ThroughputCycleDetector
from src.core.zero_tracking import ZeroTracker, ZeroTrackingConfig
from src.core.zeroing import (
    calibration_model_from_points,
    compute_zero_offset,
    estimate_lbs_per_mv,
    map_signal_to_weight,
)
from src.db.repo import AppRepository
from src.hw.interfaces import HardwareBundle
from src.services.output_writer import OutputWriter
from src.services.state import LiveState

log = logging.getLogger(__name__)

HW_RETRY_INTERVAL_S = 5.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class _Cfg:
    """Cached runtime config -- reloaded every config_refresh_s."""
    channel: int
    enabled_channels: list[bool]
    gain_code: int
    avg_samples: int
    zero_offset_mv: float
    zero_offset_updated_utc: Optional[str]
    tare_offset_lbs: float
    zero_tracking_enabled: bool
    zero_tracking_range_lb: float
    zero_tracking_deadband_lb: float
    zero_tracking_hold_s: float
    zero_tracking_rate_lbs: float
    zero_tracking_persist_interval_s: float
    excitation_enabled: bool
    excitation_ai_channel: int
    excitation_warn_v: float
    excitation_fault_v: float
    startup_delay_s: float
    startup_output_value: float
    startup_auto_arm: bool
    output_mode: str
    ao_channel_v: int
    ao_channel_ma: int
    safe_v: float
    safe_ma: float
    armed: bool
    test_mode: bool
    test_value: float
    calibration_active: bool
    nudge_value: float
    deadband_enabled: bool
    deadband_lb: float
    ramp_enabled: bool
    ramp_rate_v: float
    ramp_rate_ma: float
    min_lb: float
    max_lb: float
    loop_hz: float
    config_refresh_s: float
    kalman_q: float
    kalman_r: float
    stability_window: int
    stability_stddev_lb: float
    stability_slope_lbs: float
    opto_actions: Dict[int, str]
    throughput_enabled: bool
    throughput_device_id: Optional[str]
    throughput_hopper_id: Optional[str]
    throughput_empty_threshold_lb: float
    throughput_rise_trigger_lb: float
    throughput_full_min_lb: float
    throughput_dump_drop_lb: float
    throughput_full_stability_s: float
    throughput_empty_confirm_s: float
    throughput_min_processed_lb: float
    throughput_max_cycle_s: float
    round_up_enabled: bool


class AcquisitionService:
    """Clean acquisition loop for summing-board architecture.

    One channel in -> Kalman filter -> linear scale -> 0-10V out.
    """

    def __init__(
        self,
        hw: Optional[HardwareBundle],
        repo: AppRepository,
        state: LiveState,
    ) -> None:
        self.hw = hw
        self.repo = repo
        self.state = state
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="acq-loop", daemon=True)
        self._start_t = time.monotonic()

        self._cfg: Optional[_Cfg] = None
        self._last_cfg_load = 0.0
        self._last_hw_retry = 0.0
        self._daq_online = hw is not None
        self._megaind_online = hw is not None

        # Signal processing
        self._kalman: Optional[KalmanFilter] = None
        self._stability: Optional[StabilityDetector] = None
        self._writer = OutputWriter()
        self._zero_tracker = ZeroTracker()
        self._throughput_detector = ThroughputCycleDetector()
        self._last_filtered_for_zero: Optional[float] = None
        self._zero_tracking_active = False
        self._zero_tracking_locked = True
        self._zero_tracking_reason = "disabled"
        self._zero_tracking_hold_elapsed_s = 0.0
        self._zero_tracking_spike_slope_lbs = 0.0
        self._last_zero_tracking_reason: Optional[str] = None

        # Opto button debounce
        self._opto_last: Dict[int, bool] = {}
        self._opto_count: Dict[int, int] = {}

        # Loop stats
        self._loop_count = 0

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: Optional[float] = None) -> None:
        self._thread.join(timeout=timeout)

    # ── Config ────────────────────────────────────────────────────

    def _load_cfg(self) -> _Cfg:
        c = self.repo.get_latest_config()
        daq = c.get("daq") or c.get("daq24b8vin") or {}
        scale = c.get("scale") or {}
        zero_tracking = c.get("zero_tracking") or {}
        excitation = c.get("excitation") or {}
        startup = c.get("startup") or {}
        out = c.get("output") or {}
        filt = c.get("filter") or {}
        timing = c.get("timing") or {}
        rng = c.get("range") or {}
        throughput = c.get("throughput") or {}
        display = c.get("display") or {}

        zero_offset_raw = scale.get("zero_offset_mv")
        if zero_offset_raw is None:
            zero_offset_raw = scale.get("zero_offset_signal", 0.0)

        # Channel selection + enable toggles
        channel = int(daq.get("channel", 7))
        gain_code = int(daq.get("gain_code", 6))
        enabled_channels = list(daq.get("enabled_channels") or [True] * 8)
        while len(enabled_channels) < 8:
            enabled_channels.append(True)
        enabled_channels = enabled_channels[:8]

        # Legacy fallback from old channels array
        channels = daq.get("channels")
        if channels and isinstance(channels, list):
            for i, ch in enumerate(channels[:8]):
                if isinstance(ch, dict):
                    enabled_channels[i] = bool(ch.get("enabled", enabled_channels[i]))
                    if enabled_channels[i]:
                        channel = i
                        gain_code = int(ch.get("gain_code", gain_code))
                        break

        channel = max(0, min(7, int(channel)))
        if not enabled_channels[channel]:
            try:
                channel = enabled_channels.index(True)
            except ValueError:
                enabled_channels = [True] * 8
                channel = 7

        output_mode = str(out.get("mode", "0_10V"))
        if output_mode not in ("0_10V", "4_20mA"):
            output_mode = "0_10V"
        ao_default = int(out.get("ao_channel", out.get("ao_channel_v", 1)) or 1)
        ao_channel_v = max(1, min(4, int(out.get("ao_channel_v", ao_default) or ao_default)))
        ao_channel_ma = max(1, min(4, int(out.get("ao_channel_ma", ao_default) or ao_default)))
        stability_stddev_lb = float(
            filt.get("stability_stddev_lb", filt.get("stability_threshold", 0.5)) or 0.5
        )
        stability_slope_lbs = float(
            filt.get("stability_slope_lbs", stability_stddev_lb * 2.0) or (stability_stddev_lb * 2.0)
        )

        return _Cfg(
            channel=channel,
            enabled_channels=enabled_channels,
            gain_code=gain_code,
            avg_samples=max(1, int(daq.get("average_samples", 2) or 2)),
            zero_offset_mv=float(zero_offset_raw or 0.0),
            zero_offset_updated_utc=scale.get("zero_offset_updated_utc"),
            tare_offset_lbs=float(scale.get("tare_offset_lbs", 0.0) or 0.0),
            zero_tracking_enabled=bool(zero_tracking.get("enabled", False)),
            zero_tracking_range_lb=max(0.0, float(zero_tracking.get("range_lb", 0.5) or 0.5)),
            zero_tracking_deadband_lb=max(0.0, float(zero_tracking.get("deadband_lb", 0.1) or 0.1)),
            zero_tracking_hold_s=max(0.0, float(zero_tracking.get("hold_s", 6.0) or 6.0)),
            zero_tracking_rate_lbs=max(0.0, float(zero_tracking.get("rate_lbs", 0.1) or 0.1)),
            zero_tracking_persist_interval_s=max(
                0.2, float(zero_tracking.get("persist_interval_s", 1.0) or 1.0)
            ),
            excitation_enabled=bool(excitation.get("enabled", True)),
            excitation_ai_channel=max(1, min(4, int(excitation.get("ai_channel", 1) or 1))),
            excitation_warn_v=float(excitation.get("warn_v", 9.0) or 9.0),
            excitation_fault_v=float(excitation.get("fault_v", 8.0) or 8.0),
            startup_delay_s=max(0.0, float(startup.get("delay_s", 0.0) or 0.0)),
            startup_output_value=float(startup.get("output_value", 0.0) or 0.0),
            startup_auto_arm=bool(startup.get("auto_arm", False)),
            output_mode=output_mode,
            ao_channel_v=ao_channel_v,
            ao_channel_ma=ao_channel_ma,
            safe_v=float(out.get("safe_v", 0.0)),
            safe_ma=float(out.get("safe_ma", 4.0)),
            armed=bool(out.get("armed", False)),
            test_mode=bool(out.get("test_mode", False)),
            test_value=float(out.get("test_value", 0.0) or 0.0),
            calibration_active=bool(out.get("calibration_active", False)),
            nudge_value=float(out.get("nudge_value", 0.0) or 0.0),
            deadband_enabled=bool(out.get("deadband_enabled", True)),
            deadband_lb=max(0.0, float(out.get("deadband_lb", 0.5) or 0.5)),
            ramp_enabled=bool(out.get("ramp_enabled", False)),
            ramp_rate_v=max(0.0, float(out.get("ramp_rate_v", 5.0) or 5.0)),
            ramp_rate_ma=max(0.0, float(out.get("ramp_rate_ma", 8.0) or 8.0)),
            min_lb=float(rng.get("min_lb", 0.0)),
            max_lb=float(rng.get("max_lb", 300.0)),
            loop_hz=float(timing.get("loop_rate_hz", 20) or 20),
            config_refresh_s=float(timing.get("config_refresh_s", 2.0) or 2.0),
            kalman_q=float(filt.get("kalman_q", filt.get("kalman_process_noise", 1.0)) or 1.0),
            kalman_r=float(filt.get("kalman_r", filt.get("kalman_measurement_noise", 50.0)) or 50.0),
            stability_window=int(filt.get("stability_window", 25) or 25),
            stability_stddev_lb=stability_stddev_lb,
            stability_slope_lbs=stability_slope_lbs,
            opto_actions={
                int(k): str(v)
                for k, v in (c.get("opto_actions") or {}).items()
            },
            throughput_enabled=bool(throughput.get("enabled", True)),
            throughput_device_id=(
                str(throughput.get("device_id")).strip()
                if throughput.get("device_id") not in (None, "")
                else None
            ),
            throughput_hopper_id=(
                str(throughput.get("hopper_id")).strip()
                if throughput.get("hopper_id") not in (None, "")
                else None
            ),
            throughput_empty_threshold_lb=max(
                0.0,
                float(throughput.get("empty_threshold_lb", 2.0) or 2.0),
            ),
            throughput_rise_trigger_lb=max(
                0.5,
                float(throughput.get("rise_trigger_lb", 8.0) or 8.0),
            ),
            throughput_full_min_lb=max(
                0.5,
                float(throughput.get("full_min_lb", 15.0) or 15.0),
            ),
            throughput_dump_drop_lb=max(
                0.5,
                float(throughput.get("dump_drop_lb", 6.0) or 6.0),
            ),
            throughput_full_stability_s=max(
                0.0,
                float(throughput.get("full_stability_s", 0.4) or 0.4),
            ),
            throughput_empty_confirm_s=max(
                0.0,
                float(throughput.get("empty_confirm_s", 0.3) or 0.3),
            ),
            throughput_min_processed_lb=max(
                0.0,
                float(throughput.get("min_processed_lb", 5.0) or 5.0),
            ),
            throughput_max_cycle_s=max(
                10.0,
                float(throughput.get("max_cycle_s", 900.0) or 900.0),
            ),
            round_up_enabled=bool(display.get("round_up_enabled", False)),
        )

    # ── Hardware reconnect ────────────────────────────────────────

    def _try_reinit(self) -> bool:
        from src.hw.factory import create_hardware_bundle
        cfg = self.repo.get_latest_config()
        result = create_hardware_bundle(cfg)

        self._daq_online = result.daq_online
        self._megaind_online = result.megaind_online

        self.state.set(
            io_live=result.ok,
            daq_online=result.daq_online,
            megaind_online=result.megaind_online,
            daq_error=result.daq_error,
            megaind_error=result.megaind_error,
        )

        if result.ok:
            self.hw = result.bundle
            self.state.set(fault=False, fault_reason=None)
            log.info("Hardware reconnected - I/O is LIVE")
            return True
        return False

    # ── Main loop ─────────────────────────────────────────────────

    def _run(self) -> None:
        last_t = time.monotonic()

        while not self._stop.is_set():
            t = time.monotonic()
            dt = max(1e-6, t - last_t)
            last_t = t

            # --- Offline: retry hardware ---
            if self.hw is None:
                if (t - self._last_hw_retry) >= HW_RETRY_INTERVAL_S:
                    self._last_hw_retry = t
                    self._try_reinit()
                self.state.set(io_live=False, fault=True, fault_reason="I/O Offline")
                time.sleep(1.0)
                continue

            # If one board dropped while loop is running, retry full init in background.
            if (not self._daq_online or not self._megaind_online) and (t - self._last_hw_retry) >= HW_RETRY_INTERVAL_S:
                self._last_hw_retry = t
                self._try_reinit()

            try:
                # --- Reload config periodically ---
                if self._cfg is None or (t - self._last_cfg_load) > (self._cfg.config_refresh_s if self._cfg else 2.0):
                    self._cfg = self._load_cfg()
                    self._last_cfg_load = t

                    # Re-init filters if noise params changed
                    if self._kalman is None or self._kalman.Q != self._cfg.kalman_q or self._kalman.R != self._cfg.kalman_r:
                        self._kalman = KalmanFilter(
                            process_noise=self._cfg.kalman_q,
                            measurement_noise=self._cfg.kalman_r,
                        )
                    if (
                        self._stability is None
                        or self._stability.window != self._cfg.stability_window
                        or self._stability.stddev_threshold != self._cfg.stability_stddev_lb
                        or self._stability.slope_threshold != self._cfg.stability_slope_lbs
                    ):
                        self._stability = StabilityDetector(
                            window=self._cfg.stability_window,
                            stddev_threshold=self._cfg.stability_stddev_lb,
                            slope_threshold=self._cfg.stability_slope_lbs,
                        )

                    # Apply gain to active channel
                    try:
                        self.hw.daq.set_gain_code(self._cfg.channel, self._cfg.gain_code)
                    except Exception:
                        pass

                cfg = self._cfg

                # 1. READ active channel
                raw_mv = 0.0
                try:
                    if not cfg.enabled_channels[cfg.channel]:
                        raise RuntimeError(f"Active channel {cfg.channel + 1} is disabled")
                    raw_mv = float(self.hw.daq.read_differential_mv(cfg.channel))
                    self._daq_online = True
                except Exception:
                    self._daq_online = False

                # 1b. READ excitation monitor from MegaIND AI
                excitation_v = 0.0
                excitation_fault = False
                if cfg.excitation_enabled:
                    excitation_status = "NOT_READ"
                    if self._megaind_online:
                        try:
                            excitation_v = float(self.hw.megaind.read_analog_in_v(cfg.excitation_ai_channel))
                            if excitation_v <= cfg.excitation_fault_v:
                                excitation_status = "FAULT"
                                excitation_fault = True
                            elif excitation_v <= cfg.excitation_warn_v:
                                excitation_status = "WARN"
                            else:
                                excitation_status = "OK"
                        except Exception:
                            self._megaind_online = False
                            excitation_status = "READ_ERROR"
                    else:
                        excitation_status = "OFFLINE"
                else:
                    excitation_status = "DISABLED"

                # 2. CALIBRATION: Get cal points for slope
                # CalibrationPointRow has .signal (mV) and .known_weight_lbs
                cal_points = self.repo.get_calibration_points()
                cal_model = calibration_model_from_points(cal_points)
                adjusted_mv = raw_mv - cfg.zero_offset_mv
                lbs_per_mv: Optional[float] = None

                mapped_weight_lbs, lbs_per_mv = map_signal_to_weight(adjusted_mv, cal_points)
                if mapped_weight_lbs is not None:
                    weight_lbs = float(mapped_weight_lbs)
                else:
                    # No cal: raw mV as rough weight (uncalibrated)
                    weight_lbs = adjusted_mv * 100.0  # Arbitrary scale so UI shows something

                # 3. FILTER
                filtered_lbs = self._kalman.update(weight_lbs)

                # 3b. ROUND UP (ceiling) if enabled
                if cfg.round_up_enabled and filtered_lbs > 0:
                    filtered_lbs = math.ceil(filtered_lbs)

                # 4. TARE
                net_lbs = filtered_lbs - cfg.tare_offset_lbs

                # 5. STABILITY
                is_stable = self._stability.update(filtered_lbs, dt)

                # 5b. Motion/spike guard used by zero tracker for explicit lock reason.
                spike_slope_lbs = 0.0
                spike_detected = False
                if self._last_filtered_for_zero is not None:
                    spike_slope_lbs = abs((filtered_lbs - self._last_filtered_for_zero) / dt)
                    spike_detected = spike_slope_lbs > max(2.0, cfg.stability_slope_lbs * 2.0)
                self._last_filtered_for_zero = filtered_lbs
                self._zero_tracking_spike_slope_lbs = spike_slope_lbs

                # 5c. THROUGHPUT CYCLE DETECTION (fill -> dump -> empty)
                if cfg.throughput_enabled:
                    throughput_cfg = ThroughputCycleConfig(
                        empty_threshold_lb=cfg.throughput_empty_threshold_lb,
                        rise_trigger_lb=cfg.throughput_rise_trigger_lb,
                        full_min_lb=cfg.throughput_full_min_lb,
                        dump_drop_lb=cfg.throughput_dump_drop_lb,
                        full_stability_s=cfg.throughput_full_stability_s,
                        empty_confirm_s=cfg.throughput_empty_confirm_s,
                        min_processed_lb=cfg.throughput_min_processed_lb,
                        max_cycle_s=cfg.throughput_max_cycle_s,
                    )
                    throughput_evt = self._throughput_detector.update(
                        now_s=t,
                        gross_lbs=filtered_lbs,
                        is_stable=is_stable,
                        cfg=throughput_cfg,
                    )
                    if throughput_evt is not None:
                        event_ts = _utc_now()
                        try:
                            self.repo.add_throughput_event(
                                timestamp_utc=event_ts,
                                processed_lbs=throughput_evt.processed_lbs,
                                full_lbs=throughput_evt.full_lbs,
                                empty_lbs=throughput_evt.empty_lbs,
                                duration_ms=throughput_evt.duration_ms,
                                confidence=throughput_evt.confidence,
                                device_id=cfg.throughput_device_id,
                                hopper_id=cfg.throughput_hopper_id,
                            )
                            # Keep legacy production totals in sync for existing dashboards.
                            self.repo.record_dump_and_increment_totals(
                                prev_stable_lbs=throughput_evt.full_lbs,
                                new_stable_lbs=throughput_evt.empty_lbs,
                                processed_lbs=throughput_evt.processed_lbs,
                            )
                            self.repo.log_event(
                                level="INFO",
                                code="THROUGHPUT_CYCLE_COMPLETE",
                                message=(
                                    f"Throughput cycle complete: {throughput_evt.processed_lbs:.2f} lb processed."
                                ),
                                details={
                                    "timestamp_utc": event_ts,
                                    "processed_lbs": throughput_evt.processed_lbs,
                                    "full_lbs": throughput_evt.full_lbs,
                                    "empty_lbs": throughput_evt.empty_lbs,
                                    "duration_ms": throughput_evt.duration_ms,
                                    "confidence": throughput_evt.confidence,
                                    "device_id": cfg.throughput_device_id,
                                    "hopper_id": cfg.throughput_hopper_id,
                                },
                            )
                        except Exception as event_err:  # noqa: BLE001
                            log.warning("Failed to persist throughput event: %s", event_err)
                else:
                    self._throughput_detector.reset()

                # 5d. ZERO TRACKING (automatic drift compensation when unloaded + stable)
                tracker_cfg = ZeroTrackingConfig(
                    enabled=self._daq_online and cfg.zero_tracking_enabled,
                    range_lb=cfg.zero_tracking_range_lb,
                    deadband_lb=cfg.zero_tracking_deadband_lb,
                    hold_s=cfg.zero_tracking_hold_s,
                    rate_lbs=cfg.zero_tracking_rate_lbs,
                    persist_interval_s=min(
                        cfg.zero_tracking_persist_interval_s,
                        max(0.2, cfg.config_refresh_s),
                    ),
                )
                tracking_step = self._zero_tracker.step(
                    now_s=t,
                    dt_s=dt,
                    filtered_lbs=filtered_lbs,
                    tare_offset_lbs=cfg.tare_offset_lbs,
                    is_stable=is_stable,
                    lbs_per_mv=lbs_per_mv,
                    current_zero_offset_mv=cfg.zero_offset_mv,
                    cfg=tracker_cfg,
                    spike_detected=spike_detected,
                )

                cfg.zero_offset_mv = tracking_step.zero_offset_mv
                self._zero_tracking_active = tracking_step.active
                self._zero_tracking_locked = tracking_step.locked
                self._zero_tracking_reason = tracking_step.reason
                self._zero_tracking_hold_elapsed_s = tracking_step.hold_elapsed_s

                if tracking_step.reason != self._last_zero_tracking_reason:
                    self._last_zero_tracking_reason = tracking_step.reason
                    self.repo.log_event(
                        level="INFO",
                        code="ZERO_TRACKING_STATE",
                        message=f"Zero tracking state changed: {tracking_step.reason}",
                        details={
                            "active": tracking_step.active,
                            "locked": tracking_step.locked,
                            "reason": tracking_step.reason,
                            "hold_elapsed_s": round(tracking_step.hold_elapsed_s, 3),
                            "filtered_lbs": filtered_lbs,
                            "tare_offset_lbs": cfg.tare_offset_lbs,
                            "range_lb": cfg.zero_tracking_range_lb,
                            "deadband_lb": cfg.zero_tracking_deadband_lb,
                            "spike_slope_lbs": spike_slope_lbs,
                        },
                    )

                if tracking_step.should_persist:
                    fresh_cfg = self.repo.get_latest_config()
                    fresh_scale = fresh_cfg.get("scale") or {}
                    previous_zero_offset = fresh_scale.get("zero_offset_mv")
                    if previous_zero_offset is None:
                        previous_zero_offset = fresh_scale.get("zero_offset_signal", 0.0)
                    previous_zero_offset = float(previous_zero_offset or 0.0)

                    updated_utc = _utc_now()
                    fresh_scale["zero_offset_mv"] = cfg.zero_offset_mv
                    fresh_scale["zero_offset_signal"] = cfg.zero_offset_mv
                    fresh_scale["zero_offset_updated_utc"] = updated_utc
                    fresh_cfg["scale"] = fresh_scale
                    self.repo.save_config(fresh_cfg)
                    cfg.zero_offset_updated_utc = updated_utc

                    self.repo.log_event(
                        level="INFO",
                        code="ZERO_TRACKING_APPLIED",
                        message=(
                            f"Auto zero tracking updated baseline by "
                            f"{tracking_step.signal_correction_mv:.6f} mV."
                        ),
                        details={
                            "raw_signal_mv": raw_mv,
                            "filtered_lbs": filtered_lbs,
                            "weight_correction_lbs": tracking_step.weight_correction_lbs,
                            "signal_correction_mv": tracking_step.signal_correction_mv,
                            "old_zero_offset_mv": previous_zero_offset,
                            "new_zero_offset_mv": cfg.zero_offset_mv,
                            "stable": is_stable,
                            "spike_slope_lbs": spike_slope_lbs,
                            "reason": tracking_step.reason,
                            "hold_elapsed_s": round(tracking_step.hold_elapsed_s, 3),
                        },
                    )

                # 6. OUTPUT
                is_ma_mode = (cfg.output_mode == "4_20mA")
                units = "mA" if is_ma_mode else "V"
                startup_value = cfg.startup_output_value
                if is_ma_mode:
                    startup_value = max(4.0, min(20.0, float(startup_value)))
                else:
                    startup_value = max(0.0, min(10.0, float(startup_value)))
                startup_active = (t - self._start_t) < cfg.startup_delay_s
                effective_armed = bool(cfg.armed or (cfg.startup_auto_arm and not startup_active))
                output_fault = (not self._daq_online) or (cfg.excitation_enabled and excitation_fault)
                plc_points = self.repo.get_plc_profile_points(output_mode=cfg.output_mode, limit=500)
                plc_curve: Optional[PlcProfileCurve] = None
                if len(plc_points) >= 2:
                    try:
                        plc_curve = PlcProfileCurve(
                            output_mode=cfg.output_mode,
                            points=[(p.plc_displayed_lbs, p.analog_value) for p in plc_points],
                        )
                    except Exception:
                        plc_curve = None

                if startup_active:
                    out_cmd = self._writer.compute(
                        weight_lb=net_lbs,
                        output_mode=cfg.output_mode,
                        min_lb=cfg.min_lb,
                        max_lb=cfg.max_lb,
                        plc_profile=plc_curve,
                        fault=True,
                        armed=True,
                        safe_v=(startup_value if not is_ma_mode else cfg.safe_v),
                        safe_ma=(startup_value if is_ma_mode else cfg.safe_ma),
                        deadband_lb=cfg.deadband_lb,
                        deadband_enabled=cfg.deadband_enabled,
                        ramp_enabled=cfg.ramp_enabled,
                        ramp_rate_v=cfg.ramp_rate_v,
                        ramp_rate_ma=cfg.ramp_rate_ma,
                        dt_s=dt,
                    )
                elif output_fault or (not effective_armed):
                    out_cmd = self._writer.compute(
                        weight_lb=net_lbs,
                        output_mode=cfg.output_mode,
                        min_lb=cfg.min_lb,
                        max_lb=cfg.max_lb,
                        plc_profile=plc_curve,
                        fault=output_fault,
                        armed=effective_armed,
                        safe_v=cfg.safe_v,
                        safe_ma=cfg.safe_ma,
                        deadband_lb=cfg.deadband_lb,
                        deadband_enabled=cfg.deadband_enabled,
                        ramp_enabled=cfg.ramp_enabled,
                        ramp_rate_v=cfg.ramp_rate_v,
                        ramp_rate_ma=cfg.ramp_rate_ma,
                        dt_s=dt,
                    )
                elif cfg.calibration_active:
                    nudge = float(cfg.nudge_value)
                    if is_ma_mode:
                        nudge = max(4.0, min(20.0, nudge))
                    else:
                        nudge = max(0.0, min(10.0, nudge))
                    out_cmd = self._writer.compute(
                        weight_lb=net_lbs,
                        output_mode=cfg.output_mode,
                        min_lb=cfg.min_lb,
                        max_lb=cfg.max_lb,
                        plc_profile=plc_curve,
                        fault=False,
                        armed=True,
                        safe_v=cfg.safe_v,
                        safe_ma=cfg.safe_ma,
                        deadband_lb=cfg.deadband_lb,
                        deadband_enabled=False,
                        ramp_enabled=False,
                        ramp_rate_v=cfg.ramp_rate_v,
                        ramp_rate_ma=cfg.ramp_rate_ma,
                        dt_s=dt,
                    )
                    out_cmd.value = nudge
                    self._writer.prime_output(out_cmd.value, units)
                elif cfg.test_mode:
                    test_val = float(cfg.test_value)
                    if is_ma_mode:
                        test_val = max(4.0, min(20.0, test_val))
                    else:
                        test_val = max(0.0, min(10.0, test_val))
                    out_cmd = self._writer.compute(
                        weight_lb=net_lbs,
                        output_mode=cfg.output_mode,
                        min_lb=cfg.min_lb,
                        max_lb=cfg.max_lb,
                        plc_profile=plc_curve,
                        fault=False,
                        armed=True,
                        safe_v=cfg.safe_v,
                        safe_ma=cfg.safe_ma,
                        deadband_lb=cfg.deadband_lb,
                        deadband_enabled=False,
                        ramp_enabled=False,
                        ramp_rate_v=cfg.ramp_rate_v,
                        ramp_rate_ma=cfg.ramp_rate_ma,
                        dt_s=dt,
                    )
                    out_cmd.value = test_val
                    self._writer.prime_output(out_cmd.value, units)
                else:
                    out_cmd = self._writer.compute(
                        weight_lb=net_lbs,
                        output_mode=cfg.output_mode,
                        min_lb=cfg.min_lb,
                        max_lb=cfg.max_lb,
                        plc_profile=plc_curve,
                        fault=False,
                        armed=True,
                        safe_v=cfg.safe_v,
                        safe_ma=cfg.safe_ma,
                        deadband_lb=cfg.deadband_lb,
                        deadband_enabled=cfg.deadband_enabled,
                        ramp_enabled=cfg.ramp_enabled,
                        ramp_rate_v=cfg.ramp_rate_v,
                        ramp_rate_ma=cfg.ramp_rate_ma,
                        dt_s=dt,
                    )

                # 7. WRITE to MegaIND
                if self._megaind_online:
                    try:
                        if cfg.output_mode == "4_20mA":
                            self.hw.megaind.write_analog_out_ma(cfg.ao_channel_ma, out_cmd.value)
                        else:
                            self.hw.megaind.write_analog_out_v(cfg.ao_channel_v, out_cmd.value)
                    except Exception:
                        self._megaind_online = False

                # 8. POLL opto buttons
                if self._megaind_online:
                    self._poll_buttons(cfg, raw_mv, weight_lbs)

                # 9. UPDATE state for UI
                self._loop_count += 1
                io_live = self._daq_online and self._megaind_online
                fault_state = (not self._daq_online) or (not self._megaind_online) or (
                    cfg.excitation_enabled and excitation_fault
                )
                fault_reason: Optional[str] = None
                if not self._daq_online:
                    fault_reason = "DAQ offline"
                elif not self._megaind_online:
                    fault_reason = "MegaIND offline"
                elif cfg.excitation_enabled and excitation_fault:
                    fault_reason = f"Excitation low ({excitation_v:.2f}V)"
                self.state.set(
                    # Raw data
                    raw_signal_mv=raw_mv,
                    total_signal=raw_mv,        # Legacy key for routes
                    signal_for_cal=raw_mv,      # Used by calibration endpoints
                    # Weight
                    raw_weight_lbs=weight_lbs,
                    total_weight_lbs=net_lbs,
                    filtered_weight_lbs=filtered_lbs,
                    lbs_per_mv=(float(lbs_per_mv) if lbs_per_mv is not None else 0.0),
                    tare_offset_lbs=cfg.tare_offset_lbs,
                    zero_offset_mv=cfg.zero_offset_mv,
                    zero_offset_signal=cfg.zero_offset_mv,  # Legacy key
                    zero_offset_updated_utc=cfg.zero_offset_updated_utc,
                    zero_tracking_enabled=cfg.zero_tracking_enabled,
                    zero_tracking_active=self._zero_tracking_active,
                    zero_tracking_locked=self._zero_tracking_locked,
                    zero_tracking_reason=self._zero_tracking_reason,
                    zero_tracking_hold_elapsed_s=self._zero_tracking_hold_elapsed_s,
                    zero_tracking_spike_slope_lbs=self._zero_tracking_spike_slope_lbs,
                    # Output
                    output_command=out_cmd.value,
                    output_units=out_cmd.units,
                    output_mode=cfg.output_mode,
                    output_armed=effective_armed,
                    output_test_mode=cfg.test_mode,
                    output_test_value=cfg.test_value,
                    output_calibration_active=cfg.calibration_active,
                    output_nudge_value=cfg.nudge_value,
                    output_mapping_mode=("profile" if plc_curve is not None else "linear"),
                    output_profile_active=(plc_curve is not None),
                    output_profile_points=len(plc_points),
                    ao_channel_v=cfg.ao_channel_v,
                    ao_channel_ma=cfg.ao_channel_ma,
                    # Hardware status
                    io_live=io_live,
                    daq_online=self._daq_online,
                    megaind_online=self._megaind_online,
                    # Stability / fault
                    stable=is_stable,
                    fault=fault_state,
                    fault_reason=fault_reason,
                    excitation_v=excitation_v,
                    excitation_status=excitation_status,
                    # Stats
                    loop_hz=(1.0 / dt if dt > 0 else 0.0),
                    last_update_utc=_utc_now(),
                    cal_points_count=len(cal_points),
                    cal_points_used=cal_model.active_points_count,  # Legacy key
                    calibration_method=cal_model.method,
                    calibration_slope_lbs_per_mv=(
                        float(cal_model.slope_lbs_per_mv)
                        if cal_model.slope_lbs_per_mv is not None
                        else 0.0
                    ),
                    calibration_intercept_lbs=cal_model.intercept_lbs,
                    calibration_last_utc=cal_model.last_calibration_utc,
                    active_channel=cfg.channel,
                    enabled_channels=cfg.enabled_channels,
                )

            except Exception as e:
                log.error("Acquisition loop error: %s", e)
                time.sleep(1.0)
                continue

            # Loop rate control
            target = 1.0 / cfg.loop_hz if cfg else 0.05
            elapsed = time.monotonic() - t
            time.sleep(max(0.0, target - elapsed))

    # ── Button handling ───────────────────────────────────────────

    def _poll_buttons(self, cfg: _Cfg, raw_mv: float, gross_lbs: float) -> None:
        try:
            for ch in (1, 2, 3, 4):
                pressed = self.hw.megaind.read_digital_in(ch)

                # Debounce: require 2 consecutive reads
                count = self._opto_count.get(ch, 0)
                count = (count + 1) if pressed else 0
                self._opto_count[ch] = count

                was_pressed = self._opto_last.get(ch, False)
                is_pressed = count >= 2

                # Rising edge
                if is_pressed and not was_pressed:
                    action = cfg.opto_actions.get(ch, "none").lower()
                    self._handle_button(action, raw_mv, gross_lbs, cfg)

                self._opto_last[ch] = is_pressed
        except Exception:
            pass

    def _handle_button(self, action: str, raw_mv: float, gross_lbs: float, cfg: _Cfg) -> None:
        if action == "tare":
            c = self.repo.get_latest_config()
            s = c.get("scale") or {}
            s["tare_offset_lbs"] = gross_lbs
            c["scale"] = s
            self.repo.save_config(c)
            log.info("Button TARE: offset=%.2f lb", gross_lbs)

        elif action == "zero":
            c = self.repo.get_latest_config()
            s = c.get("scale") or {}
            old_offset = s.get("zero_offset_mv")
            if old_offset is None:
                old_offset = s.get("zero_offset_signal", 0.0)
            old_offset = float(old_offset or 0.0)

            cal_points = self.repo.get_calibration_points(limit=200)
            lbs_per_mv = estimate_lbs_per_mv(cal_points)

            # ZERO updates signal baseline only. TARE remains an independent weight-domain offset.
            if lbs_per_mv is not None and abs(lbs_per_mv) > 1e-9:
                correction_signal_mv = float(gross_lbs) / float(lbs_per_mv)
                new_offset = old_offset + correction_signal_mv
                cal_zero_signal = raw_mv - new_offset
                drift = new_offset - old_offset
                zero_method = "weight_based"
            else:
                new_offset, cal_zero_signal = compute_zero_offset(raw_mv, cal_points)
                drift = new_offset - old_offset
                zero_method = "cal_zero_fallback"

            s["zero_offset_mv"] = new_offset
            s["zero_offset_signal"] = new_offset
            s["zero_offset_updated_utc"] = _utc_now()
            c["scale"] = s
            self.repo.save_config(c)
            cfg.zero_offset_mv = new_offset
            cfg.zero_offset_updated_utc = s["zero_offset_updated_utc"]
            log.info(
                "Button ZERO: drift=%.6f mV (old=%.6f, new=%.6f, raw=%.6f, cal_zero=%.6f, method=%s)",
                drift,
                old_offset,
                new_offset,
                raw_mv,
                cal_zero_signal,
                zero_method,
            )

        elif action == "print":
            net = gross_lbs - cfg.tare_offset_lbs
            self.repo.log_event(
                level="INFO",
                code="BUTTON_PRINT",
                message=f"Print: {net:.2f} lb",
                details={"net": net, "gross": gross_lbs, "signal": raw_mv},
            )
            log.info("Button PRINT: %.2f lb", net)
