from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.core.drift import DriftDetector
from src.core.dump_detection import DumpDetector
from src.core.filtering import IIRLowPass, KalmanFilter, MedianFilter, NotchFilter, StabilityDetector
from src.core.post_dump_rezero import PostDumpRezeroConfig, PostDumpRezeroController
from src.core.plc_profile import PlcProfileCurve
from src.core.zero_tracking import ZeroTracker, ZeroTrackingConfig
from src.core.zeroing import map_signal_to_weight
from src.db.repo import AppRepository
from src.hw.interfaces import HardwareBundle
from src.services.output_writer import OutputCommand, OutputWriter
from src.services.state import LiveState

log = logging.getLogger(__name__)

# Hardware retry interval when offline
HW_RETRY_INTERVAL_S = 5.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_div(n: float, d: float, default: float = 0.0) -> float:
    if d == 0.0:
        return default
    return n / d


@dataclass
class _RuntimeConfig:
    # polled_channels: channels that are actively read from the DAQ
    # loadcell_channels: subset used for weight math, stability, drift, alarms
    polled_channels: List[int]
    loadcell_channels: List[int]
    gain_codes: List[int]
    daq_average_samples: int
    # NOTE: ratiometric removed - always use raw mV
    alpha: float  # IIR filter alpha (legacy, kept for fallback)
    # Kalman filter parameters (preferred over IIR for zero-lag filtering)
    use_kalman: bool
    kalman_process_noise: float  # Q: how much weight changes between readings
    kalman_measurement_noise: float  # R: how noisy ADC readings are
    stability_window: int
    stability_stddev_lb: float
    stability_slope_lbs: float
    median_enabled: bool
    median_window: int
    notch_enabled: bool
    notch_freq: int
    min_lb: float
    max_lb: float
    output_mode: str
    ao_channel_v: int
    ao_channel_ma: int
    safe_v: float
    safe_ma: float
    deadband_enabled: bool
    deadband_lb: float
    ramp_enabled: bool
    ramp_rate_v: float
    ramp_rate_ma: float
    dump_drop_threshold: float
    dump_min_prev_stable: float
    drift_ratio_threshold: float
    drift_ema_alpha: float
    drift_consecutive: int
    tare_offset_lbs: float
    zero_offset_signal: float
    zero_tracking_enabled: bool
    zero_tracking_range_lb: float
    zero_tracking_deadband_lb: float
    zero_tracking_hold_s: float
    zero_tracking_rate_lbs: float
    zero_tracking_persist_interval_s: float
    post_dump_rezero_enabled: bool
    post_dump_rezero_min_delay_s: float
    post_dump_rezero_window_s: float
    post_dump_rezero_empty_threshold_lb: float
    post_dump_rezero_max_correction_lb: float
    loop_rate_hz: float
    config_refresh_s: float
    log_interval_s: float
    log_retention_days: int
    log_raw: bool
    log_weight: bool
    log_output: bool
    log_event_only: bool
    # Output control
    armed: bool
    test_mode: bool
    test_value: float
    calibration_active: bool
    nudge_value: float
    # MegaIND I/O (maintenance / extra controls)
    megaind_io: Dict[str, Any]
    round_up_enabled: bool


class AcquisitionService:
    """Background acquisition loop with hardware retry support.
    
    If hardware is offline at startup, the service will keep retrying to connect.
    While offline, outputs remain in safe state and the UI shows "I/O OFFLINE".
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

        self._last_cfg_load = 0.0
        self._cfg: Optional[_RuntimeConfig] = None
        
        # Hardware status tracking
        self._last_hw_retry = 0.0
        self._io_live = hw is not None
        self._daq_online = hw is not None
        self._megaind_online = hw is not None

        # Algorithm blocks (initialized after cfg load)
        self._filter_iir = IIRLowPass(alpha=0.18)
        self._filter_kalman = KalmanFilter(process_noise=1.0, measurement_noise=50.0)
        self._median = MedianFilter(window=5)
        self._notch = NotchFilter(f0_hz=60.0, fs_hz=20.0, q=30.0)
        self._stable = StabilityDetector()
        self._dump = DumpDetector()
        self._drift = DriftDetector()
        self._writer = OutputWriter()
        self._zero_tracker = ZeroTracker()
        self._post_dump_rezero = PostDumpRezeroController(event_sink=self.repo.log_event)
        self._pending_zero_tracking_delta_mv = 0.0
        self._zero_tracking_active = False
        self._zero_tracking_locked = True
        self._zero_tracking_reason = "disabled"
        self._zero_tracking_hold_elapsed_s = 0.0
        self._post_dump_rezero_active = False
        self._post_dump_rezero_state = "idle"
        self._post_dump_rezero_reason = "idle"
        self._post_dump_rezero_dump_age_s = 0.0
        self._post_dump_rezero_last_apply_utc: Optional[str] = None

        self._trend_last = 0.0
        self._maintenance_last = 0.0
        self._last_gain_codes: Optional[List[int]] = None
        # Track last values written by MegaIND I/O (to avoid spamming I2C)
        self._megaind_extra_last_ao_v: Dict[int, float] = {}

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: Optional[float] = None) -> None:
        self._thread.join(timeout=timeout)

    def _try_reinit_hardware(self) -> bool:
        """Attempt to reinitialize hardware. Returns True if successful."""
        from src.hw.factory import create_hardware_bundle
        
        cfg = self.repo.get_latest_config()
        result = create_hardware_bundle(cfg)
        
        self._daq_online = result.daq_online
        self._megaind_online = result.megaind_online
        self._io_live = result.ok
        
        # Update state
        self.state.set(
            io_live=result.ok,
            daq_online=result.daq_online,
            megaind_online=result.megaind_online,
            daq_error=result.daq_error,
            megaind_error=result.megaind_error,
        )
        
        if result.ok:
            self.hw = result.bundle
            log.info("Hardware reinitialized successfully - I/O is LIVE")
            self.repo.log_event(
                level="INFO",
                code="HW_RECONNECTED",
                message="Hardware reconnected - I/O is now LIVE",
                details={},
            )
            # Clear fault if it was due to hardware being offline
            self.state.set(fault=False, fault_reason=None)
            return True
        else:
            reason_parts = []
            if not result.daq_online:
                reason_parts.append(f"DAQ offline: {result.daq_error or 'unknown'}")
            if not result.megaind_online:
                reason_parts.append(f"MegaIND offline: {result.megaind_error or 'unknown'}")
            fault_reason = "; ".join(reason_parts) or "Hardware offline"
            self.state.set(fault=True, fault_reason=fault_reason)
            return False

    def _load_cfg(self) -> _RuntimeConfig:
        cfg = self.repo.get_latest_config()

        daq_cfg = cfg.get("daq24b8vin") or {}
        channels = list(daq_cfg.get("channels") or [])
        while len(channels) < 8:
            channels.append({"enabled": False, "role": "Not used", "gain_code": 7})
        channels = channels[:8]

        gain_codes = [int(((ch or {}).get("gain_code", 7)) or 7) for ch in channels]

        polled_channels = [i for i, ch in enumerate(channels) if bool((ch or {}).get("enabled", False))]
        loadcell_channels = [
            i
            for i, ch in enumerate(channels)
            if bool((ch or {}).get("enabled", False)) and "Load Cell" in str((ch or {}).get("role", ""))
        ]

        flt = cfg.get("filter") or {}
        rng = cfg.get("range") or {}
        out = cfg.get("output") or {}
        dump = cfg.get("dump_detection") or {}
        drift = cfg.get("drift") or {}
        scale = cfg.get("scale") or {}
        timing = cfg.get("timing") or {}
        logging_cfg = cfg.get("logging") or {}
        megaind_io = cfg.get("megaind_io") or {}

        return _RuntimeConfig(
            polled_channels=[int(c) for c in polled_channels],
            loadcell_channels=[int(c) for c in loadcell_channels],
            gain_codes=[int(gc) for gc in gain_codes],
            daq_average_samples=max(1, min(50, int(daq_cfg.get("average_samples", 2) or 2))),
            # NOTE: ratiometric removed - always use raw mV
            alpha=float(flt.get("alpha", 0.18)),
            # Kalman filter settings (preferred, defaults to enabled)
            use_kalman=bool(flt.get("use_kalman", True)),
            kalman_process_noise=float(flt.get("kalman_process_noise", 1.0)),
            kalman_measurement_noise=float(flt.get("kalman_measurement_noise", 50.0)),
            stability_window=int(flt.get("stability_window", 25)),
            stability_stddev_lb=float(flt.get("stability_stddev_lb", 1.5)),
            stability_slope_lbs=float(flt.get("stability_slope_lbs", 3.0)),
            median_enabled=bool(flt.get("median_enabled", False)),
            median_window=int(flt.get("median_window", 5)),
            notch_enabled=bool(flt.get("notch_enabled", False)),
            notch_freq=int(flt.get("notch_freq", 60)),
            min_lb=float(rng.get("min_lb", 0.0)),
            max_lb=float(rng.get("max_lb", 300.0)),
            output_mode=str(out.get("mode", "0_10V")),
            ao_channel_v=int(out.get("ao_channel_v", 1)),
            ao_channel_ma=int(out.get("ao_channel_ma", 1)),
            safe_v=float(out.get("safe_v", 0.0)),
            safe_ma=float(out.get("safe_ma", 4.0)),
            deadband_enabled=bool(out.get("deadband_enabled", False)),
            deadband_lb=float(out.get("deadband_lb", 0.5) or 0.5),
            ramp_enabled=bool(out.get("ramp_enabled", False)),
            ramp_rate_v=float(out.get("ramp_rate_v", 5.0) or 5.0),
            ramp_rate_ma=float(out.get("ramp_rate_ma", 8.0) or 8.0),
            dump_drop_threshold=float(dump.get("drop_threshold_lb", 25.0)),
            dump_min_prev_stable=float(dump.get("min_prev_stable_lb", 10.0)),
            drift_ratio_threshold=float(drift.get("ratio_threshold", 0.12)),
            drift_ema_alpha=float(drift.get("ema_alpha", 0.02)),
            drift_consecutive=int(drift.get("consecutive_required", 20)),
            tare_offset_lbs=float(scale.get("tare_offset_lbs", 0.0) or 0.0),
            zero_offset_signal=float(
                scale.get("zero_offset_mv", scale.get("zero_offset_signal", 0.0)) or 0.0
            ),
            zero_tracking_enabled=bool(cfg.get("zero_tracking", {}).get("enabled", False)),
            zero_tracking_range_lb=float(cfg.get("zero_tracking", {}).get("range_lb", 0.05)),
            zero_tracking_deadband_lb=max(
                0.0, float(cfg.get("zero_tracking", {}).get("deadband_lb", 0.02) or 0.02)
            ),
            zero_tracking_hold_s=max(
                0.0, float(cfg.get("zero_tracking", {}).get("hold_s", 1.0) or 1.0)
            ),
            zero_tracking_rate_lbs=float(cfg.get("zero_tracking", {}).get("rate_lbs", 0.05)),
            zero_tracking_persist_interval_s=max(
                0.2, float(cfg.get("zero_tracking", {}).get("persist_interval_s", 1.0) or 1.0)
            ),
            post_dump_rezero_enabled=bool(cfg.get("zero_tracking", {}).get("post_dump_enabled", True)),
            post_dump_rezero_min_delay_s=max(
                0.0, float(cfg.get("zero_tracking", {}).get("post_dump_min_delay_s", 5.0) or 5.0)
            ),
            post_dump_rezero_window_s=max(
                0.0, float(cfg.get("zero_tracking", {}).get("post_dump_window_s", 10.0) or 10.0)
            ),
            post_dump_rezero_empty_threshold_lb=max(
                0.0, float(cfg.get("zero_tracking", {}).get("post_dump_empty_threshold_lb", 4.0) or 4.0)
            ),
            post_dump_rezero_max_correction_lb=max(
                0.0, float(cfg.get("zero_tracking", {}).get("post_dump_max_correction_lb", 8.0) or 8.0)
            ),
            loop_rate_hz=float(timing.get("loop_rate_hz", 20) or 20.0),
            config_refresh_s=float(timing.get("config_refresh_s", 2.0) or 2.0),
            log_interval_s=float(logging_cfg.get("interval_s", 1) or 1.0),
            log_retention_days=int(logging_cfg.get("retention_days", 30) or 30),
            log_raw=bool(logging_cfg.get("log_raw", False)),
            log_weight=bool(logging_cfg.get("log_weight", True)),
            log_output=bool(logging_cfg.get("log_output", True)),
            log_event_only=bool(logging_cfg.get("event_only", False)),
            # Output control
            armed=bool(out.get("armed", False)),
            test_mode=bool(out.get("test_mode", False)),
            test_value=float(out.get("test_value", 0.0) or 0.0),
            calibration_active=bool(out.get("calibration_active", False)),
            nudge_value=float(out.get("nudge_value", 0.0) or 0.0),
            megaind_io=dict(megaind_io),
            round_up_enabled=bool((cfg.get("display") or {}).get("round_up_enabled", False)),
        )

    @staticmethod
    def _eval_simple_condition(*, kind: str, value: float, condition: str, threshold: float) -> bool:
        """Evaluate a simple condition for MegaIND I/O rules."""
        c = str(condition or "gte").lower().strip()
        if kind == "di":
            # Digital inputs are treated as 0.0/1.0; support common aliases.
            if c in ("on", "true", "high"):
                return value >= 0.5
            if c in ("off", "false", "low"):
                return value < 0.5
        if c in ("gte", ">="):
            return value >= threshold
        if c in ("lte", "<="):
            return value <= threshold
        if c in ("gt", ">"):
            return value > threshold
        if c in ("lt", "<"):
            return value < threshold
        if c in ("eq", "=="):
            return abs(value - threshold) <= 1e-9
        if c in ("neq", "!=", "<>"):
            return abs(value - threshold) > 1e-9
        return value >= threshold

    def _run_offline_cycle(self, t: float) -> None:
        """Run a cycle when hardware is offline. Tries to reconnect periodically."""
        # Try to reconnect periodically
        if (t - self._last_hw_retry) >= HW_RETRY_INTERVAL_S:
            self._last_hw_retry = t
            log.info("Attempting to reconnect hardware...")
            self._try_reinit_hardware()
        
        # Update state to show offline status
        self.state.set(
            io_live=False,
            daq_online=self._daq_online,
            megaind_online=self._megaind_online,
            fault=True,
            fault_reason="I/O offline - waiting for hardware",
        )

    def _run(self) -> None:
        last_t = time.monotonic()
        loop_count = 0
        loop_t0 = last_t
        prev_fault: Optional[bool] = None
        prev_stable: Optional[bool] = None

        while not self._stop.is_set():
            t = time.monotonic()
            dt = max(1e-6, t - last_t)
            last_t = t

            # If hardware is offline, run the offline cycle and skip normal processing
            if self.hw is None:
                self._run_offline_cycle(t)
                time.sleep(1.0)  # Slower loop when offline
                continue

            try:
                # Periodically reload config from DB (allows UI edits).
                refresh_s = float(self._cfg.config_refresh_s) if self._cfg is not None else 2.0
                if self._cfg is None or (t - self._last_cfg_load) > refresh_s:
                    self._cfg = self._load_cfg()
                    self._last_cfg_load = t

                    # IMPORTANT: Do NOT reset filter state on config reload.
                    self._filter_iir.alpha = float(self._cfg.alpha)
                    self._filter_kalman.Q = float(self._cfg.kalman_process_noise)
                    self._filter_kalman.R = float(self._cfg.kalman_measurement_noise)

                    # DAQ averaging: apply live if driver supports it.
                    try:
                        avg = max(1, min(50, int(self._cfg.daq_average_samples)))
                        if hasattr(self.hw.daq, "average_samples"):
                            setattr(self.hw.daq, "average_samples", avg)
                    except Exception:  # noqa: BLE001
                        pass

                    # DAQ gain codes: apply to hardware only when they change.
                    try:
                        desired = [int(x) for x in (self._cfg.gain_codes or [])]
                        if len(desired) == 8 and self._last_gain_codes != desired:
                            for ch, code in enumerate(desired):
                                c = int(code)
                                if 0 <= c <= 7:
                                    self.hw.daq.set_gain_code(ch, c)
                            self._last_gain_codes = list(desired)
                            self.repo.log_event(
                                level="INFO",
                                code="DAQ_GAIN_APPLIED",
                                message="Applied DAQ gain codes from config.",
                                details={"gain_codes": desired},
                            )
                    except Exception as e:  # noqa: BLE001
                        self.repo.log_event(level="ERROR", code="DAQ_GAIN_APPLY_FAILED", message=str(e), details={})

                    # Median filter window (spike rejection)
                    try:
                        mw = max(1, int(self._cfg.median_window))
                        if getattr(self._median, "window", None) != mw:
                            self._median = MedianFilter(window=mw)
                    except Exception:  # noqa: BLE001
                        pass

                    # Notch filter configuration (auto-disables if Nyquist not met)
                    try:
                        fs_hz = max(1.0, float(self._cfg.loop_rate_hz))
                        f0 = max(0.1, float(self._cfg.notch_freq))
                        if float(getattr(self._notch, "fs_hz", 0.0)) != fs_hz or float(getattr(self._notch, "f0_hz", 0.0)) != f0:
                            self._notch.configure(f0_hz=f0, fs_hz=fs_hz)
                            self._notch.reset()
                    except Exception:  # noqa: BLE001
                        pass

                    # Update stability detector thresholds WITHOUT resetting buffer
                    self._stable.stddev_threshold = float(self._cfg.stability_stddev_lb)
                    self._stable.slope_threshold = float(self._cfg.stability_slope_lbs)
                    if self._stable.window != int(self._cfg.stability_window):
                        self._stable = StabilityDetector(
                            window=self._cfg.stability_window,
                            stddev_threshold=self._cfg.stability_stddev_lb,
                            slope_threshold=self._cfg.stability_slope_lbs,
                        )
                    self._dump = DumpDetector(
                        drop_threshold_lbs=self._cfg.dump_drop_threshold,
                        min_prev_stable_lbs=self._cfg.dump_min_prev_stable,
                    )
                    self._drift = DriftDetector(
                        ratio_threshold=self._cfg.drift_ratio_threshold,
                        ema_alpha=self._cfg.drift_ema_alpha,
                        consecutive_required=self._cfg.drift_consecutive,
                    )
                    # Update output writer parameters without resetting state.
                    self._writer.min_lb = float(self._cfg.min_lb)
                    self._writer.max_lb = float(self._cfg.max_lb)
                    self._writer.deadband_enabled = bool(self._cfg.deadband_enabled)
                    self._writer.deadband_lb = float(self._cfg.deadband_lb)
                    self._writer.ramp_enabled = bool(self._cfg.ramp_enabled)
                    self._writer.ramp_rate_v = float(self._cfg.ramp_rate_v)
                    self._writer.ramp_rate_ma = float(self._cfg.ramp_rate_ma)

                cfg = self._cfg
                assert cfg is not None

                # MegaIND extra I/O polling (safe read-only)
                megaind_ai_v: Dict[int, float] = {}
                megaind_di: Dict[int, bool] = {}
                if self._megaind_online:
                    try:
                        for ch in (1, 2, 3, 4):
                            try:
                                megaind_ai_v[ch] = float(self.hw.megaind.read_analog_in_v(ch))
                            except Exception:  # noqa: BLE001
                                megaind_ai_v[ch] = float("nan")
                            try:
                                megaind_di[ch] = bool(self.hw.megaind.read_digital_in(ch))
                            except Exception:  # noqa: BLE001
                                megaind_di[ch] = False
                    except Exception as e:  # noqa: BLE001
                        log.warning("Failed to poll MegaIND extra I/O: %s", e)
                self.state.set(megaind_ai_v=megaind_ai_v, megaind_di=megaind_di)

                # NOTE: Ratiometric removed - always use raw mV
                fault = False
                fault_reason = None

                # Read DAQ channels
                per_ch: List[dict] = []
                signals: Dict[int, float] = {}
                total_signal = 0.0
                daq_read_ok = True
                for ch in range(8):
                    polled = ch in cfg.polled_channels
                    is_loadcell = ch in cfg.loadcell_channels
                    if polled:
                        try:
                            raw_mv = float(self.hw.daq.read_differential_mv(ch))
                            self.state.set(last_daq_comm_utc=_utc_now())
                            self._daq_online = True
                        except Exception as e:
                            log.warning("Failed to read DAQ channel %d: %s", ch, e)
                            raw_mv = 0.0
                            daq_read_ok = False
                            self._daq_online = False
                    else:
                        raw_mv = 0.0
                    # Always use raw mV (ratiometric removed)
                    sig = raw_mv
                    signals[ch] = sig if is_loadcell else 0.0
                    if is_loadcell:
                        total_signal += sig
                    per_ch.append(
                        {"ch": ch, "enabled": is_loadcell, "polled": polled, "raw_mV": raw_mv, "filtered": sig}
                    )

                # Update I/O live status
                self._io_live = self._daq_online and self._megaind_online
                self.state.set(
                    io_live=self._io_live,
                    daq_online=self._daq_online,
                    megaind_online=self._megaind_online,
                )

                # Apply zero offset
                calibrated_signal = float(total_signal) - float(cfg.zero_offset_signal)

                # Calibration mapping (all points use raw mV now)
                cal_points = self.repo.get_calibration_points(limit=200)
                local_lbs_per_signal: Optional[float] = None
                if len(cal_points) >= 2:
                    mapped_weight, local_lbs_per_signal = map_signal_to_weight(
                        float(calibrated_signal), cal_points
                    )
                    if mapped_weight is None:
                        raw_weight = 0.0
                        cal_points_used = len(cal_points)
                        fault = True
                        fault_reason = "Calibration mapping unavailable for current signal"
                    else:
                        raw_weight = float(mapped_weight)
                        cal_points_used = len(cal_points)
                else:
                    # NOT CALIBRATED: Force fault and zero output
                    raw_weight = 0.0
                    cal_points_used = len(cal_points)
                    fault = True
                    fault_reason = f"Scale not calibrated (need 2+ points, have {len(cal_points)})"

                # Optional pre-filters
                pre_weight = float(raw_weight)
                if cfg.median_enabled:
                    pre_weight = self._median.update(pre_weight)
                if cfg.notch_enabled:
                    pre_weight = self._notch.update(pre_weight)

                # Apply filter
                if cfg.use_kalman:
                    filt_weight = self._filter_kalman.update(pre_weight)
                else:
                    filt_weight = self._filter_iir.update(pre_weight)
                stable = bool(self._stable.update(filt_weight, dt_s=dt))

                # Round UP (ceiling) if enabled
                if cfg.round_up_enabled and filt_weight > 0:
                    filt_weight = math.ceil(filt_weight)

                # Apply software tare (weight domain)
                gross_lbs = float(filt_weight)
                net_lbs = gross_lbs - float(cfg.tare_offset_lbs)
                filt_weight = float(net_lbs)

                cal_valid = (
                    (not fault)
                    and len(cal_points) >= 2
                    and cal_points_used >= 2
                    and local_lbs_per_signal is not None
                    and abs(float(local_lbs_per_signal)) > 1e-9
                )

                # Post-dump re-zero (industrial layer 2: event-driven, one-shot capture)
                post_dump_cfg = PostDumpRezeroConfig(
                    enabled=(
                        cfg.zero_tracking_enabled
                        and cfg.post_dump_rezero_enabled
                        and cal_valid
                        and abs(cfg.tare_offset_lbs) <= 1e-6
                    ),
                    min_delay_s=cfg.post_dump_rezero_min_delay_s,
                    window_s=cfg.post_dump_rezero_window_s,
                    empty_threshold_lb=cfg.post_dump_rezero_empty_threshold_lb,
                    max_correction_lb=cfg.post_dump_rezero_max_correction_lb,
                )
                post_dump_step = self._post_dump_rezero.update(
                    now_s=t,
                    raw_mv=float(total_signal),
                    gross_lbs=float(gross_lbs),
                    is_stable=stable,
                    current_zero_offset_mv=float(cfg.zero_offset_signal),
                    cal_points=cal_points,
                    cfg=post_dump_cfg,
                )
                self._post_dump_rezero_active = bool(post_dump_step.active)
                self._post_dump_rezero_state = str(post_dump_step.state)
                self._post_dump_rezero_reason = str(post_dump_step.reason)
                self._post_dump_rezero_dump_age_s = float(post_dump_step.dump_age_s)

                if post_dump_step.should_apply and post_dump_step.new_zero_offset_mv is not None:
                    updated_utc = _utc_now()
                    new_offset_mv = float(post_dump_step.new_zero_offset_mv)
                    try:
                        def _set_post_dump_zero(scale: dict, _: dict) -> None:
                            scale["zero_offset_mv"] = new_offset_mv
                            scale["zero_offset_signal"] = new_offset_mv
                            scale["zero_offset_updated_utc"] = updated_utc

                        self.repo.update_config_section("scale", _set_post_dump_zero)
                        cfg.zero_offset_signal = new_offset_mv
                        self._pending_zero_tracking_delta_mv = 0.0
                        self._zero_tracker.reset()
                        self._post_dump_rezero_last_apply_utc = updated_utc
                        if cfg.use_kalman:
                            self._filter_kalman.reset(0.0)
                        self.repo.log_event(
                            level="INFO",
                            code="POST_DUMP_REZERO_APPLIED",
                            message="Post-dump re-zero applied (one-shot capture).",
                            details={
                                "updated_utc": updated_utc,
                                "dump_age_s": float(post_dump_step.dump_age_s),
                                "gross_lbs": float(gross_lbs),
                                "new_zero_offset_mv": new_offset_mv,
                            },
                        )
                    except Exception as rez_err:  # noqa: BLE001
                        log.warning("Post-dump re-zero persistence failed: %s", rez_err)
                        self.repo.log_event(
                            level="WARNING",
                            code="POST_DUMP_REZERO_PERSIST_FAILED",
                            message="Post-dump re-zero persistence failed.",
                            details={"error": str(rez_err)[:500]},
                        )

                # Continuous AZT (industrial layer 1: micro-range, stable-only, rate-limited)
                tracker_cfg = ZeroTrackingConfig(
                    enabled=(
                        cfg.zero_tracking_enabled
                        and cal_valid
                        and abs(cfg.tare_offset_lbs) <= 1e-6
                    ),
                    range_lb=float(cfg.zero_tracking_range_lb),
                    deadband_lb=float(cfg.zero_tracking_deadband_lb),
                    hold_s=float(cfg.zero_tracking_hold_s),
                    rate_lbs=float(cfg.zero_tracking_rate_lbs),
                    persist_interval_s=float(cfg.zero_tracking_persist_interval_s),
                )
                tracking_step = self._zero_tracker.step(
                    now_s=t,
                    dt_s=dt,
                    display_lbs=float(gross_lbs),
                    tare_offset_lbs=float(cfg.tare_offset_lbs),
                    is_stable=stable,
                    current_zero_offset_lbs=0.0,
                    cfg=tracker_cfg,
                    spike_detected=False,
                )
                self._zero_tracking_active = bool(tracking_step.active)
                self._zero_tracking_locked = bool(tracking_step.locked)
                self._zero_tracking_reason = str(tracking_step.reason)
                self._zero_tracking_hold_elapsed_s = float(tracking_step.hold_elapsed_s)

                if abs(float(tracking_step.zero_offset_delta_lbs)) > 1e-12 and cal_valid:
                    lb_per_signal = float(local_lbs_per_signal)
                    delta_mv = float(tracking_step.zero_offset_delta_lbs) / lb_per_signal
                    cfg.zero_offset_signal = float(cfg.zero_offset_signal) + float(delta_mv)
                    self._pending_zero_tracking_delta_mv += float(delta_mv)

                if tracking_step.should_persist and abs(self._pending_zero_tracking_delta_mv) > 1e-12:
                    pending_delta_mv = float(self._pending_zero_tracking_delta_mv)
                    updated_utc = _utc_now()
                    try:
                        def _apply_azt_delta(scale: dict, _: dict) -> None:
                            old_mv = float(scale.get("zero_offset_mv", scale.get("zero_offset_signal", 0.0)) or 0.0)
                            new_mv = old_mv + pending_delta_mv
                            scale["zero_offset_mv"] = new_mv
                            scale["zero_offset_signal"] = new_mv
                            scale["zero_offset_updated_utc"] = updated_utc

                        self.repo.update_config_section("scale", _apply_azt_delta)
                        cfg.zero_offset_signal = float(cfg.zero_offset_signal)
                        self._pending_zero_tracking_delta_mv = 0.0
                    except Exception as persist_err:  # noqa: BLE001
                        log.warning("Failed to persist AZT delta: %s", persist_err)

                # Channel ratios for drift diagnostics
                denom = sum(abs(signals[ch]) for ch in cfg.loadcell_channels) or 1e-9
                ratios = {ch: abs(signals[ch]) / denom for ch in cfg.loadcell_channels}
                for r in per_ch:
                    ch = r["ch"]
                    r["ratio"] = float(ratios.get(ch, 0.0))

                drift_status = self._drift.update(ratios=ratios, stable=stable)
                if drift_status.warnings:
                    self.repo.log_event(
                        level="WARNING",
                        code="DRIFT_WARNING",
                        message="Load cell ratio drift detected.",
                        details={"warnings": drift_status.warnings},
                    )

                dump_evt = self._dump.update(weight_lbs=filt_weight, stable=stable)
                if dump_evt is not None:
                    if cfg.zero_tracking_enabled and cfg.post_dump_rezero_enabled:
                        self._post_dump_rezero.trigger(now_s=t)
                    self.repo.log_event(
                        level="INFO",
                        code="DUMP_DETECTED",
                        message="Dump detected; production total increment candidate.",
                        details={
                            "prev_stable_lbs": dump_evt.prev_stable_lbs,
                            "new_stable_lbs": dump_evt.new_stable_lbs,
                            "processed_lbs": dump_evt.processed_lbs,
                        },
                    )
                    self.repo.record_dump_and_increment_totals(
                        prev_stable_lbs=dump_evt.prev_stable_lbs,
                        new_stable_lbs=dump_evt.new_stable_lbs,
                        processed_lbs=dump_evt.processed_lbs,
                    )

                # PLC profile curve
                points = self.repo.get_plc_profile_points(output_mode=cfg.output_mode, limit=500)
                plc_curve = None
                if len(points) >= 2:
                    plc_curve = PlcProfileCurve(
                        output_mode=cfg.output_mode,
                        points=[(p.plc_displayed_lbs, p.analog_value) for p in points[::-1]],
                    )

                # Output command selection (safety first):
                # - If I/O NOT live -> force safe output
                # - If NOT armed -> force safe output
                # - If fault -> force safe output
                units = "mA" if cfg.output_mode == "4_20mA" else "V"
                safe_value = float(cfg.safe_ma) if units == "mA" else float(cfg.safe_v)

                # Force safe output if I/O is not live
                io_fault = not self._io_live
                
                if cfg.calibration_active:
                    # Manually nudged value during calibration - BYPASSES ARM REQUIREMENT
                    cmd = OutputCommand(value=float(cfg.nudge_value), units=units)
                    self._writer.seed_output_state(output_mode=cfg.output_mode, value=cmd.value, units=cmd.units)
                elif io_fault or (not cfg.armed) or fault:
                    cmd = OutputCommand(value=safe_value, units=units)
                    self._writer.seed_output_state(output_mode=cfg.output_mode, value=cmd.value, units=cmd.units)
                elif cfg.test_mode:
                    cmd = OutputCommand(value=float(cfg.test_value), units=units)
                    cmd = self._writer.apply_output_controls(cmd, output_mode=cfg.output_mode, dt_s=dt)
                else:
                    cmd = self._writer.compute(
                        weight_lb=filt_weight,
                        output_mode=cfg.output_mode,
                        plc_profile=plc_curve,
                        fault=False,
                        safe_v=cfg.safe_v,
                        safe_ma=cfg.safe_ma,
                        dt_s=dt,
                    )

                # Write output (only if MegaIND is online)
                if self._megaind_online:
                    try:
                        if cfg.output_mode == "4_20mA":
                            self.hw.megaind.write_analog_out_ma(cfg.ao_channel_ma, float(cmd.value))
                        else:
                            self.hw.megaind.write_analog_out_v(cfg.ao_channel_v, float(cmd.value))
                        self.state.set(last_megaind_comm_utc=_utc_now())
                    except Exception as e:
                        log.warning("Failed to write output: %s", e)
                        self._megaind_online = False

                # MegaIND maintenance I/O: optional extra voltage outputs + simple rules.
                # IMPORTANT: by default we DO NOT touch the PLC output channel to avoid fighting the main loop.
                mio = cfg.megaind_io or {}
                mio_armed = bool(mio.get("armed", False))
                mio_allow_plc = bool(mio.get("allow_plc_channel", False))
                mio_safe_v = float(mio.get("safe_v", 0.0) or 0.0)

                desired_ao_v: Dict[int, float] = {}
                ao_v_cfg = list(mio.get("ao_v") or [])
                while len(ao_v_cfg) < 4:
                    ao_v_cfg.append({})
                for ch in (1, 2, 3, 4):
                    item = ao_v_cfg[ch - 1] or {}
                    if bool(item.get("enabled", False)):
                        desired_ao_v[ch] = float(item.get("value_v", 0.0) or 0.0)

                # Apply simple rules (if armed). Rules can override manual values.
                rules = list(mio.get("rules") or [])
                if mio_armed and rules:
                    for rule in rules:
                        if not isinstance(rule, dict) or not bool(rule.get("enabled", False)):
                            continue
                        kind = str(rule.get("input_kind", "ai_v")).strip().lower()
                        in_ch = int(rule.get("input_ch", 1) or 1)
                        out_ch = int(rule.get("output_ch", 1) or 1)
                        if not (1 <= in_ch <= 4 and 1 <= out_ch <= 4):
                            continue

                        if kind == "di":
                            v = 1.0 if bool(megaind_di.get(in_ch, False)) else 0.0
                            thr = float(rule.get("threshold", 0.5) or 0.5)
                        else:
                            v = float(megaind_ai_v.get(in_ch, 0.0) or 0.0)
                            thr = float(rule.get("threshold", 0.0) or 0.0)

                        cond = str(rule.get("condition", "gte"))
                        ok = self._eval_simple_condition(kind=kind, value=v, condition=cond, threshold=thr)
                        if ok:
                            desired_ao_v[out_ch] = float(rule.get("true_value_v", 0.0) or 0.0)
                        else:
                            if bool(rule.get("else_enabled", False)):
                                desired_ao_v[out_ch] = float(rule.get("false_value_v", 0.0) or 0.0)

                # Enforce safety interlock
                if not mio_armed:
                    # If disarmed, force configured channels to safe value (only those we would have controlled).
                    desired_ao_v = {ch: mio_safe_v for ch in desired_ao_v.keys()}

                # Apply to hardware (if online)
                if self._megaind_online and desired_ao_v:
                    for ch, value_v in desired_ao_v.items():
                        # Skip PLC channel unless explicitly allowed.
                        if (not mio_allow_plc) and int(ch) == int(cfg.ao_channel_v):
                            continue
                        prev = self._megaind_extra_last_ao_v.get(int(ch))
                        if prev is not None and abs(float(prev) - float(value_v)) < 0.005:
                            continue
                        try:
                            self.hw.megaind.write_analog_out_v(int(ch), float(value_v))
                            self._megaind_extra_last_ao_v[int(ch)] = float(value_v)
                            self.state.set(last_megaind_comm_utc=_utc_now())
                        except Exception as e:  # noqa: BLE001
                            log.warning("Failed to write MegaIND extra AO ch%d: %s", ch, e)
                            self._megaind_online = False
                            break

                # Expose commanded values to UI
                self.state.set(megaind_ao_v_cmd=dict(self._megaind_extra_last_ao_v))

                # Update UI snapshot
                loop_count += 1
                loop_hz = loop_count / max(1e-6, (t - loop_t0))
                # Fault reason priority: I/O > Calibration > Other
                final_fault = fault or io_fault
                final_fault_reason = None
                if io_fault:
                    final_fault_reason = "I/O offline"
                elif fault and fault_reason:
                    final_fault_reason = fault_reason
                
                self.state.set(
                    total_weight_lbs=float(filt_weight),
                    raw_weight_lbs=float(raw_weight),
                    stable=stable,
                    fault=final_fault,
                    fault_reason=final_fault_reason,
                    ratiometric=False,  # Always raw mV now
                    signal_for_cal=float(total_signal),
                    total_signal=float(total_signal),
                    calibrated_signal=float(calibrated_signal),
                    cal_points_used=int(cal_points_used),
                    output_mode=cfg.output_mode,
                    output_command=float(cmd.value),
                    output_units=cmd.units,
                    enabled_channels=list(cfg.loadcell_channels),
                    polled_channels=list(cfg.polled_channels),
                    channels=per_ch,
                    loop_hz=float(loop_hz),
                    tare_offset_lbs=float(cfg.tare_offset_lbs),
                    zero_offset_mv=float(cfg.zero_offset_signal),
                    zero_offset_signal=float(cfg.zero_offset_signal),
                    zero_tracking_enabled=bool(cfg.zero_tracking_enabled),
                    zero_tracking_active=bool(self._zero_tracking_active),
                    zero_tracking_locked=bool(self._zero_tracking_locked),
                    zero_tracking_reason=str(self._zero_tracking_reason),
                    zero_tracking_hold_elapsed_s=float(self._zero_tracking_hold_elapsed_s),
                    post_dump_rezero_enabled=bool(cfg.post_dump_rezero_enabled),
                    post_dump_rezero_active=bool(self._post_dump_rezero_active),
                    post_dump_rezero_state=str(self._post_dump_rezero_state),
                    post_dump_rezero_reason=str(self._post_dump_rezero_reason),
                    post_dump_rezero_dump_age_s=float(self._post_dump_rezero_dump_age_s),
                    post_dump_rezero_last_apply_utc=self._post_dump_rezero_last_apply_utc,
                    io_live=self._io_live,
                    daq_online=self._daq_online,
                    megaind_online=self._megaind_online,
                )

                # Trend logging
                log_interval_s = max(0.2, float(cfg.log_interval_s))
                fault_changed = (prev_fault is not None) and (bool(fault) != bool(prev_fault))
                stable_changed = (prev_stable is not None) and (bool(stable) != bool(prev_stable))
                event_happened = bool(
                    fault_changed
                    or stable_changed
                    or (dump_evt is not None)
                    or bool(getattr(drift_status, "warnings", None))
                )
                prev_fault = bool(fault)
                prev_stable = bool(stable)

                do_log = False
                if cfg.log_event_only:
                    do_log = event_happened
                else:
                    do_log = (t - self._trend_last) >= log_interval_s

                if do_log:
                    self._trend_last = t
                    if cfg.log_raw:
                        for r in per_ch:
                            if bool(r.get("polled", False)):
                                self.repo.add_channel_sample(
                                    channel=int(r.get("ch", 0)),
                                    enabled=bool(r.get("enabled", False)),
                                    raw_mv=float(r.get("raw_mV", 0.0) or 0.0),
                                    filtered=float(r.get("filtered", 0.0) or 0.0),
                                )
                    if cfg.log_weight or cfg.log_output:
                        self.repo.add_total_sample(
                            total_lbs=float(filt_weight),
                            stable=stable,
                            output_mode=cfg.output_mode,
                            output_cmd=float(cmd.value),
                        )

                # Periodic DB maintenance
                if (t - self._maintenance_last) >= 3600.0:
                    self._maintenance_last = t
                    self.repo.cleanup_trends(retention_days=int(cfg.log_retention_days))

            except Exception as e:  # noqa: BLE001
                log.exception("Acquisition loop error: %s", e)
                try:
                    self.repo.log_event(level="ERROR", code="ACQ_LOOP_ERROR", message=str(e), details={})
                except Exception:  # noqa: BLE001
                    pass
                # Attempt to force safe output
                try:
                    cfg = self._cfg or self._load_cfg()
                    if self.hw is not None and self._megaind_online:
                        if cfg.output_mode == "4_20mA":
                            self.hw.megaind.write_analog_out_ma(cfg.ao_channel_ma, cfg.safe_ma)
                        else:
                            self.hw.megaind.write_analog_out_v(cfg.ao_channel_v, cfg.safe_v)
                except Exception:  # noqa: BLE001
                    pass
                self.state.set(fault=True)

            # Loop rate control
            try:
                cfg = self._cfg
                target_hz = float(cfg.loop_rate_hz) if cfg is not None else 20.0
            except Exception:  # noqa: BLE001
                target_hz = 20.0
            target_hz = max(1.0, min(500.0, target_hz))
            target_period_s = 1.0 / target_hz
            elapsed_s = time.monotonic() - t
            sleep_s = max(0.0, target_period_s - elapsed_s)
            time.sleep(sleep_s)
