"""Acquisition loop for summing-board scale transmitter.

Reads one DAQ channel, applies Kalman filtering and linear scaling,
writes proportional 0-10V (or 4-20mA) to MegaIND for PLC.
"""
from __future__ import annotations

from collections import deque
import logging
import math
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.core.filtering import KalmanFilter, StabilityDetector
from src.core.post_dump_rezero import PostDumpRezeroConfig, PostDumpRezeroController
from src.core.plc_profile import PlcProfileCurve
from src.core.throughput_cycle import ThroughputCycleConfig, ThroughputCycleDetector, ThroughputCycleEvent
from src.core.zero_tracking import ZeroTracker, ZeroTrackingConfig
from src.core.zeroing import (
    calibration_model_from_points,
    calibration_zero_signal,
    compute_zero_offset,
    estimate_lbs_per_mv,
    map_signal_to_weight,
)
from src.db.repo import AppRepository
from src.hw.interfaces import HardwareBundle
from src.services.output_writer import OutputCommand, OutputWriter
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
    zero_offset_lbs: float
    zero_offset_updated_utc: Optional[str]
    tare_offset_lbs: float
    zero_target_lb: float
    zero_tracking_enabled: bool
    zero_tracking_range_lb: float
    zero_tracking_deadband_lb: float
    zero_tracking_hold_s: float
    zero_tracking_rate_lbs: float
    zero_tracking_persist_interval_s: float
    zero_tracking_negative_hold_s: float
    zero_tracking_startup_lockout_s: float
    zero_tracking_max_correction_lb: float
    post_dump_rezero_enabled: bool
    post_dump_rezero_min_delay_s: float
    post_dump_rezero_window_s: float
    post_dump_rezero_empty_threshold_lb: float
    post_dump_rezero_max_correction_lb: float
    startup_delay_s: float
    startup_output_value: float
    startup_auto_arm: bool
    startup_auto_zero: bool
    startup_require_manual_zero_before_auto_zero: bool
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
    loop_hz: float
    config_refresh_s: float
    kalman_q: float
    kalman_r: float
    stability_window: int
    stability_stddev_lb: float
    stability_slope_lbs: float
    opto_actions: Dict[int, str]
    allow_opto_tare: bool
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
    range_max_lb: float
    round_up_enabled: bool
    job_control_enabled: bool
    job_control_mode: str
    job_control_trigger_mode: str
    job_control_trigger_signal_value: float
    job_control_low_signal_value: float
    job_control_pretrigger_lb: float
    # (no empty_reset_lb / empty_confirm_s — output is pure threshold, no timers)


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
        self._default_line_id = str(os.environ.get("LCS_LINE_ID", "default_line") or "default_line").strip() or "default_line"
        self._default_machine_id = str(os.environ.get("LCS_MACHINE_ID", "default_machine") or "default_machine").strip() or "default_machine"

        # Signal processing
        self._kalman: Optional[KalmanFilter] = None
        self._stability: Optional[StabilityDetector] = None
        self._writer = OutputWriter()
        self._zero_tracker = ZeroTracker()
        self._post_dump_rezero = PostDumpRezeroController(event_sink=self.repo.log_event)
        self._throughput_detector = ThroughputCycleDetector()
        self._last_filtered_for_zero: Optional[float] = None
        self._zero_tracking_active = False
        self._zero_tracking_locked = True
        self._zero_tracking_reason = "disabled"
        self._zero_tracking_hold_elapsed_s = 0.0
        self._zero_tracking_spike_slope_lbs = 0.0
        self._post_dump_rezero_active = False
        self._post_dump_rezero_state = "idle"
        self._post_dump_rezero_reason = "idle"
        self._post_dump_rezero_dump_age_s = 0.0
        self._post_dump_rezero_time_to_stable_s: Optional[float] = None
        self._post_dump_rezero_time_to_empty_s: Optional[float] = None
        self._post_dump_rezero_time_to_fill_resume_s: Optional[float] = None
        self._post_dump_rezero_last_apply_utc: Optional[str] = None
        self._last_zero_tracking_reason: Optional[str] = None
        self._startup_zero_done = False  # One-shot auto-zero at end of startup
        self._cal_was_valid = False       # Track calibration validity for Kalman reset
        self._pending_zero_tracking_delta_lbs = 0.0
        self._last_zero_tracking_persist_utc: Optional[str] = None
        self._manual_zero_seen_since_boot = False
        self._auto_zero_gate_lock = threading.Lock()

        # Opto button debounce
        self._opto_last: Dict[int, bool] = {}
        self._opto_count: Dict[int, int] = {}
        self._last_blocked_tare_log_s = -1e9

        # Loop stats
        self._loop_count = 0

        # Job-target webhook runtime state (thread-safe).
        # Simple: just hold the current set_weight; comparison happens every loop tick.
        self._job_lock = threading.Lock()
        self._job_set_weight: float = 0.0   # 0.0 means no active job
        self._job_meta: Optional[dict] = None  # last webhook metadata for status/log
        self._job_state_seq: int = 0
        self._job_seen_event_ids: set[str] = set()
        self._job_event_id_order: deque[str] = deque()
        self._job_event_id_limit = 1000
        self._restore_persisted_job_control_state()

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: Optional[float] = None) -> None:
        self._thread.join(timeout=timeout)

    # ── Job-target webhook control ────────────────────────────────

    @staticmethod
    def _coerce_non_negative_weight(value: Any) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return 0.0
        if (not math.isfinite(parsed)) or parsed < 0.0:
            return 0.0
        return parsed

    @staticmethod
    def _normalize_weight_unit(value: Any) -> str:
        unit = str(value or "lb").strip().lower()
        alias_map = {
            "lb": "lb",
            "lbs": "lb",
            "pound": "lb",
            "pounds": "lb",
            "kg": "kg",
            "g": "g",
            "oz": "oz",
        }
        return alias_map.get(unit, "lb")

    def _normalize_scope_ids(self, line_id: Optional[str], machine_id: Optional[str]) -> tuple[str, str]:
        line_clean = str(line_id or self._default_line_id or "default_line").strip() or "default_line"
        machine_clean = str(machine_id or self._default_machine_id or "default_machine").strip() or "default_machine"
        return line_clean, machine_clean

    def _restore_persisted_job_control_state(self) -> None:
        restored_weight = 0.0
        restored_meta: Optional[dict[str, Any]] = None
        restored_seq = 0

        current_row = self.repo.get_set_weight_current(
            line_id=self._default_line_id,
            machine_id=self._default_machine_id,
        )
        if current_row is None:
            current_row = self.repo.get_latest_set_weight_current()

        if current_row is not None:
            restored_weight = self._coerce_non_negative_weight(current_row.set_weight_lbs)
            restored_seq = max(0, int(current_row.state_seq))
            if restored_weight > 0.0:
                restored_meta = {
                    "job_id": current_row.job_id,
                    "step_id": current_row.step_id,
                    "event_id": current_row.source_event_id,
                    "target_weight_lb": restored_weight,
                    "target_weight": current_row.set_weight_value,
                    "unit": current_row.set_weight_unit,
                    "line_id": current_row.line_id,
                    "machine_id": current_row.machine_id,
                    "product_id": current_row.product_id,
                    "operator_id": current_row.operator_id,
                    "source": current_row.source,
                    "erp_timestamp_utc": current_row.erp_timestamp_utc,
                    "received_utc": current_row.received_at_utc,
                }
            else:
                restored_meta = None
        else:
            cfg = self.repo.get_latest_config()
            job_cfg = cfg.get("job_control", {}) if isinstance(cfg, dict) else {}
            restored_weight = self._coerce_non_negative_weight(job_cfg.get("set_weight", 0.0))
            restored_meta_raw = job_cfg.get("meta")
            restored_meta = dict(restored_meta_raw) if isinstance(restored_meta_raw, dict) else None
            try:
                restored_seq = int(job_cfg.get("state_seq", 0) or 0)
            except (TypeError, ValueError):
                restored_seq = 0
            restored_seq = max(0, restored_seq)

        with self._job_lock:
            self._job_set_weight = restored_weight
            self._job_meta = restored_meta
            self._job_state_seq = restored_seq

        # Seed snapshot fields before the first acquisition loop tick.
        self.state.set(
            job_set_weight=restored_weight,
            job_active=restored_weight > 0.0,
            job_meta=(dict(restored_meta) if restored_meta else None),
        )

    def _persist_job_control_state(
        self,
        *,
        set_weight: float,
        meta: Optional[dict[str, Any]],
        state_seq: int,
        updated_utc: Optional[str] = None,
    ) -> None:
        persisted_weight = self._coerce_non_negative_weight(set_weight)
        persisted_meta = dict(meta) if isinstance(meta, dict) else None
        persisted_seq = max(0, int(state_seq))
        persisted_updated_utc = str(updated_utc or _utc_now())

        def _mutate(section: dict[str, Any], _cfg: dict[str, Any]) -> None:
            try:
                existing_seq = int(section.get("state_seq", 0) or 0)
            except (TypeError, ValueError):
                existing_seq = 0
            if persisted_seq < existing_seq:
                return
            section["state_seq"] = persisted_seq
            section["set_weight"] = persisted_weight
            section["active"] = persisted_weight > 0.0
            section["meta"] = persisted_meta
            section["updated_utc"] = persisted_updated_utc

        self.repo.update_config_section("job_control", _mutate)

    def get_job_control_status(self, pretrigger_lb: float = 0.0) -> dict[str, Any]:
        with self._job_lock:
            set_weight = self._job_set_weight
            meta = dict(self._job_meta) if self._job_meta else None
        return {
            "set_weight": set_weight,
            "active": set_weight > 0.0,
            "meta": meta,
        }

    def ingest_job_webhook(
        self,
        *,
        job_id: str,
        target_weight_lb: float,
        step_id: Optional[str] = None,
        event_id: Optional[str] = None,
        source: str = "webhook",
        pretrigger_lb: float = 0.0,
        line_id: Optional[str] = None,
        machine_id: Optional[str] = None,
        set_weight_value: Optional[float] = None,
        set_weight_unit: Optional[str] = None,
        erp_timestamp_utc: Optional[str] = None,
        product_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        job_id_clean = str(job_id or "").strip()
        if not job_id_clean:
            raise ValueError("job_id is required")
        target_lb = float(target_weight_lb)
        if (not math.isfinite(target_lb)) or target_lb < 0.0:
            raise ValueError("target_weight_lb must be a finite number >= 0")
        step_id_clean = str(step_id).strip() if step_id not in (None, "") else None
        event_id_clean = str(event_id).strip() if event_id not in (None, "") else None
        source_clean = str(source or "webhook").strip() or "webhook"
        line_id_clean, machine_id_clean = self._normalize_scope_ids(line_id, machine_id)
        unit_clean = self._normalize_weight_unit(set_weight_unit)
        if set_weight_value is None:
            set_weight_input = target_lb
        else:
            set_weight_input = float(set_weight_value)
        now_utc = _utc_now()
        payload_meta: dict[str, Any] = dict(payload) if isinstance(payload, dict) else {}
        next_meta: dict[str, Any]

        with self._job_lock:
            requested_state_seq = self._job_state_seq + 1
            next_meta = {
                "job_id": job_id_clean,
                "step_id": step_id_clean,
                "event_id": event_id_clean,
                "target_weight_lb": target_lb,
                "target_weight": set_weight_input,
                "unit": unit_clean,
                "line_id": line_id_clean,
                "machine_id": machine_id_clean,
                "product_id": (str(product_id).strip() if product_id not in (None, "") else None),
                "operator_id": (str(operator_id).strip() if operator_id not in (None, "") else None),
                "erp_timestamp_utc": (str(erp_timestamp_utc).strip() if erp_timestamp_utc not in (None, "") else None),
                "received_utc": now_utc,
                "source": source_clean,
            }

            receipt_result = self.repo.record_set_weight_receipt(
                line_id=line_id_clean,
                machine_id=machine_id_clean,
                set_weight_value=set_weight_input,
                set_weight_unit=unit_clean,
                set_weight_lbs=target_lb,
                source=source_clean,
                state_seq=requested_state_seq,
                received_at_utc=now_utc,
                source_event_id=event_id_clean,
                erp_timestamp_utc=erp_timestamp_utc,
                product_id=product_id,
                operator_id=operator_id,
                job_id=job_id_clean,
                step_id=step_id_clean,
                metadata=payload_meta,
            )

            if receipt_result.applied_to_current:
                self._job_set_weight = float(receipt_result.current_set_weight_lbs)
                self._job_meta = dict(next_meta)
                self._job_state_seq = int(receipt_result.state_seq)
                if event_id_clean:
                    self._remember_job_event_id(event_id_clean)

        if receipt_result.applied_to_current:
            try:
                self._persist_job_control_state(
                    set_weight=target_lb,
                    meta=next_meta,
                    state_seq=receipt_result.state_seq,
                    updated_utc=now_utc,
                )
            except Exception as e:  # noqa: BLE001
                self.repo.log_event(
                    level="WARNING",
                    code="JOB_CONTROL_LEGACY_PERSIST_FAILED",
                    message="Legacy config persistence failed after durable set-weight write.",
                    details={"error": str(e)[:500]},
                )

        self.repo.log_event(
            level="INFO",
            code="JOB_WEBHOOK_RECEIVED",
            message="Job webhook received — set weight updated.",
            details={
                "job_id": job_id_clean,
                "target_weight_lb": target_lb,
                "step_id": step_id_clean,
                "event_id": event_id_clean,
                "line_id": line_id_clean,
                "machine_id": machine_id_clean,
                "unit": unit_clean,
                "duplicate_event": bool(receipt_result.duplicate_event),
                "applied_to_current": bool(receipt_result.applied_to_current),
            },
        )
        return {
            "accepted": True,
            "duplicate": bool(receipt_result.duplicate_event),
            "action": "activated" if receipt_result.applied_to_current else "ignored_duplicate",
            "status": self.get_job_control_status(),
        }

    def _remember_job_event_id(self, event_id: str) -> None:
        """Track recent idempotency keys in-memory to ignore retries safely."""
        if not event_id:
            return
        if event_id in self._job_seen_event_ids:
            return
        self._job_seen_event_ids.add(event_id)
        self._job_event_id_order.append(event_id)
        while len(self._job_event_id_order) > self._job_event_id_limit:
            evicted = self._job_event_id_order.popleft()
            self._job_seen_event_ids.discard(evicted)

    def clear_job_control(self, reason: str = "manual_clear", pretrigger_lb: float = 0.0) -> dict[str, Any]:
        reason_text = str(reason or "manual_clear")
        had_weight = False
        receipt_state_seq = 0
        cleared_meta = {
            "reason": reason_text,
            "line_id": self._default_line_id,
            "machine_id": self._default_machine_id,
        }
        with self._job_lock:
            had_weight = self._job_set_weight > 0.0
            requested_state_seq = self._job_state_seq + 1
            receipt_result = self.repo.record_set_weight_receipt(
                line_id=self._default_line_id,
                machine_id=self._default_machine_id,
                set_weight_value=0.0,
                set_weight_unit="lb",
                set_weight_lbs=0.0,
                source=f"clear_job_control:{reason_text}",
                state_seq=requested_state_seq,
                received_at_utc=_utc_now(),
                metadata=cleared_meta,
            )
            self._job_set_weight = float(receipt_result.current_set_weight_lbs)
            self._job_meta = None
            self._job_state_seq = int(receipt_result.state_seq)
            receipt_state_seq = int(receipt_result.state_seq)
        try:
            self._persist_job_control_state(
                set_weight=0.0,
                meta=None,
                state_seq=receipt_state_seq,
                updated_utc=_utc_now(),
            )
        except Exception as e:  # noqa: BLE001
            self.repo.log_event(
                level="WARNING",
                code="JOB_CONTROL_LEGACY_PERSIST_FAILED",
                message="Legacy config persistence failed while clearing set weight.",
                details={"error": str(e)[:500]},
            )
        self.repo.log_event(
            level="INFO",
            code="JOB_CONTROL_CLEARED",
            message="Job control cleared — set weight reset to 0.",
            details={"reason": reason_text, "had_weight": had_weight},
        )
        return {"cleared": had_weight, "status": self.get_job_control_status()}

    @staticmethod
    def _clamp_output_value(value: float, output_mode: str) -> float:
        if output_mode == "4_20mA":
            return max(4.0, min(20.0, float(value)))
        return max(0.0, min(10.0, float(value)))

    # ── Config ────────────────────────────────────────────────────

    def _is_auto_zero_armed(self, cfg: _Cfg) -> bool:
        if not cfg.startup_require_manual_zero_before_auto_zero:
            return True
        with self._auto_zero_gate_lock:
            return self._manual_zero_seen_since_boot

    def mark_manual_zero_seen(self, source: str = "manual_zero") -> None:
        with self._auto_zero_gate_lock:
            already_armed = self._manual_zero_seen_since_boot
            self._manual_zero_seen_since_boot = True
            # Operator confirmed empty hopper; skip one-shot startup auto-zero.
            self._startup_zero_done = True
            self._pending_zero_tracking_delta_lbs = 0.0
        if not already_armed:
            self.repo.log_event(
                level="INFO",
                code="AUTO_ZERO_ARMED_AFTER_MANUAL_ZERO",
                message="Automatic zero logic armed after manual ZERO.",
                details={"source": str(source)},
            )

    def _load_cfg(self) -> _Cfg:
        c = self.repo.get_latest_config()
        daq = c.get("daq") or c.get("daq24b8vin") or {}
        scale = c.get("scale") or {}
        zero_tracking = c.get("zero_tracking") or {}
        startup = c.get("startup") or {}
        out = c.get("output") or {}
        filt = c.get("filter") or {}
        timing = c.get("timing") or {}
        throughput = c.get("throughput") or {}
        job_control = c.get("job_control") or {}
        range_cfg = c.get("range") or {}
        display = c.get("display") or {}

        # Zero offset: mV is canonical (applied in signal domain), lbs is derived for compatibility
        zero_offset_mv_raw = scale.get("zero_offset_mv", scale.get("zero_offset_signal", 0.0))
        zero_offset_lbs_raw = scale.get("zero_offset_lbs", 0.0)

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
        job_control_mode = str(job_control.get("mode", "legacy_weight_mapping") or "legacy_weight_mapping")
        if job_control_mode not in ("legacy_weight_mapping", "target_signal_mode"):
            job_control_mode = "legacy_weight_mapping"
        job_control_trigger_mode = str(job_control.get("trigger_mode", "exact") or "exact").strip().lower()
        if job_control_trigger_mode not in ("exact", "early"):
            job_control_trigger_mode = "exact"
        job_control_enabled = bool(
            job_control.get("enabled", job_control_mode == "target_signal_mode")
        )
        if not job_control_enabled:
            job_control_mode = "legacy_weight_mapping"
        trigger_signal_default = 12.0 if output_mode == "4_20mA" else 1.0
        low_signal_default = 4.0 if output_mode == "4_20mA" else 0.0
        raw_trigger_signal_value = job_control.get("trigger_signal_value", trigger_signal_default)
        raw_low_signal_value = job_control.get("low_signal_value", low_signal_default)
        job_trigger_signal_value = (
            trigger_signal_default
            if raw_trigger_signal_value is None
            else float(raw_trigger_signal_value)
        )
        job_low_signal_value = (
            low_signal_default if raw_low_signal_value is None else float(raw_low_signal_value)
        )
        if output_mode == "4_20mA":
            job_trigger_signal_value = max(4.0, min(20.0, job_trigger_signal_value))
            job_low_signal_value = max(4.0, min(20.0, job_low_signal_value))
        else:
            job_trigger_signal_value = max(0.0, min(10.0, job_trigger_signal_value))
            job_low_signal_value = max(0.0, min(10.0, job_low_signal_value))
        ao_default = int(out.get("ao_channel", out.get("ao_channel_v", 1)) or 1)
        ao_channel_v = max(1, min(4, int(out.get("ao_channel_v", ao_default) or ao_default)))
        ao_channel_ma = max(1, min(4, int(out.get("ao_channel_ma", ao_default) or ao_default)))
        stability_stddev_lb = float(
            filt.get("stability_stddev_lb", filt.get("stability_threshold", 1.5)) or 1.5
        )
        stability_slope_lbs = float(
            filt.get("stability_slope_lbs", stability_stddev_lb * 2.0) or (stability_stddev_lb * 2.0)
        )

        return _Cfg(
            channel=channel,
            enabled_channels=enabled_channels,
            gain_code=gain_code,
            avg_samples=max(1, int(daq.get("average_samples", 2) or 2)),
            zero_offset_mv=float(zero_offset_mv_raw or 0.0),
            zero_offset_lbs=float(zero_offset_lbs_raw or 0.0),
            zero_offset_updated_utc=scale.get("zero_offset_updated_utc"),
            tare_offset_lbs=float(scale.get("tare_offset_lbs", 0.0) or 0.0),
            zero_target_lb=float(scale.get("zero_target_lb", 0.0) or 0.0),
            zero_tracking_enabled=bool(zero_tracking.get("enabled", False)),
            zero_tracking_range_lb=max(0.0, float(zero_tracking.get("range_lb", 0.5) or 0.5)),
            zero_tracking_deadband_lb=max(0.0, float(zero_tracking.get("deadband_lb", 0.1) or 0.1)),
            zero_tracking_hold_s=max(0.0, float(zero_tracking.get("hold_s", 6.0) or 6.0)),
            zero_tracking_rate_lbs=max(0.0, float(zero_tracking.get("rate_lbs", 0.1) or 0.1)),
            zero_tracking_persist_interval_s=max(
                0.2, float(zero_tracking.get("persist_interval_s", 1.0) or 1.0)
            ),
            zero_tracking_negative_hold_s=max(
                0.0, float(zero_tracking.get("negative_hold_s", 1.0) or 1.0)
            ),
            zero_tracking_startup_lockout_s=max(
                0.0, float(zero_tracking.get("startup_lockout_s", 120.0) or 120.0)
            ),
            zero_tracking_max_correction_lb=max(
                1.0, float(zero_tracking.get("max_correction_lb", 20.0) or 20.0)
            ),
            post_dump_rezero_enabled=bool(zero_tracking.get("post_dump_enabled", True)),
            post_dump_rezero_min_delay_s=max(
                0.0, float(zero_tracking.get("post_dump_min_delay_s", 5.0) or 5.0)
            ),
            post_dump_rezero_window_s=max(
                0.0, float(zero_tracking.get("post_dump_window_s", 10.0) or 10.0)
            ),
            post_dump_rezero_empty_threshold_lb=max(
                0.0, float(zero_tracking.get("post_dump_empty_threshold_lb", 4.0) or 4.0)
            ),
            post_dump_rezero_max_correction_lb=max(
                0.0, float(zero_tracking.get("post_dump_max_correction_lb", 8.0) or 8.0)
            ),
            startup_delay_s=max(0.0, float(startup.get("delay_s", 0.0) or 0.0)),
            startup_output_value=float(startup.get("output_value", 0.0) or 0.0),
            startup_auto_arm=bool(startup.get("auto_arm", False)),
            startup_auto_zero=bool(startup.get("auto_zero", False)),
            startup_require_manual_zero_before_auto_zero=bool(
                startup.get("require_manual_zero_before_auto_zero", True)
            ),
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
            allow_opto_tare=bool(scale.get("allow_opto_tare", False)),
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
            range_max_lb=max(
                1.0,
                float(range_cfg.get("max_lb", 300.0) or 300.0),
            ),
            round_up_enabled=bool(display.get("round_up_enabled", False)),
            job_control_enabled=job_control_enabled,
            job_control_mode=job_control_mode,
            job_control_trigger_mode=job_control_trigger_mode,
            job_control_trigger_signal_value=job_trigger_signal_value,
            job_control_low_signal_value=job_low_signal_value,
            job_control_pretrigger_lb=max(
                0.0,
                float(job_control.get("pretrigger_lb", 0.0) or 0.0),
            ),
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

    def _persist_throughput_cycle_event(
        self,
        *,
        throughput_evt: ThroughputCycleEvent,
        cfg: _Cfg,
        event_ts: str,
        throughput_full_lbs: float,
        throughput_empty_lbs: float,
        raw_mv: float,
        adjusted_signal_mv: float,
        filtered_lbs: float,
        target_relative_lbs: float,
        throughput_full_min_relative_lb: float,
    ) -> bool:
        max_allowed_lbs = max(1.0, float(cfg.range_max_lb or 300.0))
        processed_lbs = float(throughput_evt.processed_lbs)

        if processed_lbs > max_allowed_lbs:
            self.repo.log_event(
                level="WARNING",
                code="THROUGHPUT_CYCLE_REJECTED_MAX_WEIGHT",
                message=(
                    f"Throughput cycle rejected: {processed_lbs:.2f} lb exceeds "
                    f"max {max_allowed_lbs:.2f} lb."
                ),
                details={
                    "timestamp_utc": event_ts,
                    "processed_lbs": processed_lbs,
                    "full_lbs": float(throughput_full_lbs),
                    "empty_lbs": float(throughput_empty_lbs),
                    "duration_ms": int(throughput_evt.duration_ms),
                    "confidence": float(throughput_evt.confidence),
                    "max_allowed_lbs": float(max_allowed_lbs),
                    "raw_signal_mv": float(raw_mv),
                    "adjusted_signal_mv": float(adjusted_signal_mv),
                    "zero_offset_mv": float(cfg.zero_offset_mv),
                    "zero_offset_lbs": float(cfg.zero_offset_lbs),
                    "filtered_lbs": float(filtered_lbs),
                    "target_relative_lbs": float(target_relative_lbs),
                    "zero_target_lb": float(cfg.zero_target_lb),
                    "full_min_relative_lb": float(throughput_full_min_relative_lb),
                    "range_max_lb": float(cfg.range_max_lb),
                },
            )
            return False

        self.repo.add_throughput_event(
            timestamp_utc=event_ts,
            processed_lbs=processed_lbs,
            full_lbs=throughput_full_lbs,
            empty_lbs=throughput_empty_lbs,
            duration_ms=throughput_evt.duration_ms,
            confidence=throughput_evt.confidence,
            device_id=cfg.throughput_device_id,
            hopper_id=cfg.throughput_hopper_id,
        )
        # Keep legacy production totals in sync for existing dashboards.
        self.repo.record_dump_and_increment_totals(
            prev_stable_lbs=throughput_full_lbs,
            new_stable_lbs=throughput_empty_lbs,
            processed_lbs=processed_lbs,
        )
        self.repo.log_event(
            level="INFO",
            code="THROUGHPUT_CYCLE_COMPLETE",
            message=(
                f"Throughput cycle complete: {processed_lbs:.2f} lb processed."
            ),
            details={
                "timestamp_utc": event_ts,
                "processed_lbs": processed_lbs,
                "full_lbs": throughput_full_lbs,
                "empty_lbs": throughput_empty_lbs,
                "duration_ms": throughput_evt.duration_ms,
                "confidence": throughput_evt.confidence,
                "device_id": cfg.throughput_device_id,
                "hopper_id": cfg.throughput_hopper_id,
                "zero_target_lb": float(cfg.zero_target_lb),
                "full_min_relative_lb": throughput_full_min_relative_lb,
                "range_max_lb": float(cfg.range_max_lb),
            },
        )
        return True

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

                    # Preserve unpersisted auto-zero delta across config refreshes.
                    # If an external actor updated zero after our last persist (manual ZERO/API),
                    # drop pending delta so manual changes are never overwritten.
                    if (
                        abs(self._pending_zero_tracking_delta_lbs) > 1e-12
                        and self._cfg.zero_offset_updated_utc != self._last_zero_tracking_persist_utc
                    ):
                        self._pending_zero_tracking_delta_lbs = 0.0
                    if abs(self._pending_zero_tracking_delta_lbs) > 1e-12:
                        # Convert pending lbs delta to mV and apply to both fields
                        lbs_per_mv_for_pending = estimate_lbs_per_mv(self.repo.get_calibration_points())
                        pending_delta_mv = (
                            (self._pending_zero_tracking_delta_lbs / lbs_per_mv_for_pending)
                            if (lbs_per_mv_for_pending is not None and abs(lbs_per_mv_for_pending) > 1e-9)
                            else 0.0
                        )
                        self._cfg.zero_offset_mv += pending_delta_mv
                        self._cfg.zero_offset_lbs += self._pending_zero_tracking_delta_lbs

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

                # 1b. STARTUP CHECK (used by zero tracker and output logic)
                startup_active = (t - self._start_t) < cfg.startup_delay_s

                # 2. CALIBRATION DATA
                # Calibration is independent of zero offset changes.
                # CalibrationPointRow has .signal (mV) and .known_weight_lbs
                cal_points = self.repo.get_calibration_points()
                cal_model = calibration_model_from_points(cal_points)
                lbs_per_mv: Optional[float] = None

                # 3. ZERO: Apply canonical mV offset in signal domain.
                # Migration compatibility: if canonical mV is missing but an older lbs offset
                # exists, derive mV using current calibration slope estimate.
                effective_zero_offset_mv = float(cfg.zero_offset_mv)
                if abs(effective_zero_offset_mv) <= 1e-12 and abs(cfg.zero_offset_lbs) > 1e-12:
                    lbs_per_mv_for_migration = estimate_lbs_per_mv(cal_points)
                    if lbs_per_mv_for_migration is not None and abs(lbs_per_mv_for_migration) > 1e-9:
                        effective_zero_offset_mv = cfg.zero_offset_lbs / lbs_per_mv_for_migration
                adjusted_signal_mv = raw_mv - effective_zero_offset_mv

                mapped_weight_lbs, lbs_per_mv = map_signal_to_weight(adjusted_signal_mv, cal_points)
                cal_valid = mapped_weight_lbs is not None
                if cal_valid:
                    weight_lbs = float(mapped_weight_lbs)
                    # Reset Kalman filter when calibration first becomes valid.
                    # This prevents the filter from carrying garbage values from
                    # the uncalibrated startup period (raw_mv * 100 = ~588 lbs).
                    if not self._cal_was_valid:
                        self._cal_was_valid = True
                        self._kalman = KalmanFilter(
                            process_noise=cfg.kalman_q, measurement_noise=cfg.kalman_r, initial_value=weight_lbs,
                        )
                        log.info("Kalman filter reset to %.2f lb (calibration became valid)", weight_lbs)
                else:
                    # No cal: raw mV as rough weight (uncalibrated).
                    # Zero tracking MUST NOT run on this -- it's arbitrary.
                    weight_lbs = adjusted_signal_mv * 100.0

                # 4. FILTER
                filtered_lbs = self._kalman.update(weight_lbs)

                # 5. TARE (weight domain)
                # Zero was already applied in signal domain (step 2).
                # Tare is applied in weight domain for container weight subtraction.
                net_lbs = filtered_lbs - cfg.tare_offset_lbs
                # Control logic must operate around the configured zero target.
                # Example: with zero_target_lb=3.0, "empty" should mean ~3.0 lb.
                target_relative_lbs = filtered_lbs - cfg.zero_target_lb

                # 6. STABILITY
                is_stable = self._stability.update(filtered_lbs, dt)

                # 6b. Motion/spike guard used by zero tracker for explicit lock reason.
                spike_slope_lbs = 0.0
                spike_detected = False
                if self._last_filtered_for_zero is not None:
                    spike_slope_lbs = abs((filtered_lbs - self._last_filtered_for_zero) / dt)
                    spike_detected = spike_slope_lbs > max(2.0, cfg.stability_slope_lbs * 2.0)
                self._last_filtered_for_zero = filtered_lbs
                self._zero_tracking_spike_slope_lbs = spike_slope_lbs

                # 6c. THROUGHPUT CYCLE DETECTION (fill -> dump -> empty)
                if cfg.throughput_enabled:
                    # Throughput detector now runs on target-relative weight.
                    # Keep full_min behavior aligned with the original absolute threshold.
                    throughput_full_min_relative_lb = max(
                        0.5, float(cfg.throughput_full_min_lb - cfg.zero_target_lb)
                    )
                    throughput_cfg = ThroughputCycleConfig(
                        empty_threshold_lb=cfg.throughput_empty_threshold_lb,
                        rise_trigger_lb=cfg.throughput_rise_trigger_lb,
                        full_min_lb=throughput_full_min_relative_lb,
                        dump_drop_lb=cfg.throughput_dump_drop_lb,
                        full_stability_s=cfg.throughput_full_stability_s,
                        empty_confirm_s=cfg.throughput_empty_confirm_s,
                        min_processed_lb=cfg.throughput_min_processed_lb,
                        max_cycle_s=cfg.throughput_max_cycle_s,
                    )
                    throughput_evt = self._throughput_detector.update(
                        now_s=t,
                        gross_lbs=target_relative_lbs,
                        is_stable=is_stable,
                        cfg=throughput_cfg,
                    )
                    if throughput_evt is not None:
                        throughput_full_lbs = float(throughput_evt.full_lbs + cfg.zero_target_lb)
                        throughput_empty_lbs = float(throughput_evt.empty_lbs + cfg.zero_target_lb)
                        # Arm post-dump re-zero on each completed dump/cycle event.
                        # This is the industrial-style “one-shot” correction layer.
                        if cfg.zero_tracking_enabled and cfg.post_dump_rezero_enabled:
                            self._post_dump_rezero.trigger(now_s=t)
                        event_ts = _utc_now()
                        try:
                            self._persist_throughput_cycle_event(
                                throughput_evt=throughput_evt,
                                cfg=cfg,
                                event_ts=event_ts,
                                throughput_full_lbs=throughput_full_lbs,
                                throughput_empty_lbs=throughput_empty_lbs,
                                raw_mv=raw_mv,
                                adjusted_signal_mv=adjusted_signal_mv,
                                filtered_lbs=filtered_lbs,
                                target_relative_lbs=target_relative_lbs,
                                throughput_full_min_relative_lb=throughput_full_min_relative_lb,
                            )
                        except Exception as event_err:  # noqa: BLE001
                            log.warning("Failed to persist throughput event: %s", event_err)
                else:
                    self._throughput_detector.reset()

                # 6d. ZERO TRACKING (automatic drift compensation when unloaded + stable)
                # Block zero tracking during startup AND when calibration isn't valid.
                # Prevents ADC garbage or uncalibrated fallback from triggering corrections.
                auto_zero_armed = self._is_auto_zero_armed(cfg)
                manual_zero_gate_blocked = (
                    cfg.startup_require_manual_zero_before_auto_zero and (not auto_zero_armed)
                )

                # --- Post-dump re-zero (industrial layer 2: event-driven, one-shot) ---
                auto_zero_common_enabled = (
                    self._daq_online
                    and (not startup_active)
                    and cal_valid
                    and (not manual_zero_gate_blocked)
                    and abs(cfg.tare_offset_lbs) <= 1e-6
                )
                post_dump_cfg = PostDumpRezeroConfig(
                    enabled=(
                        auto_zero_common_enabled
                        and cfg.zero_tracking_enabled
                        and cfg.post_dump_rezero_enabled
                    ),
                    min_delay_s=cfg.post_dump_rezero_min_delay_s,
                    window_s=cfg.post_dump_rezero_window_s,
                    empty_threshold_lb=cfg.post_dump_rezero_empty_threshold_lb,
                    max_correction_lb=cfg.post_dump_rezero_max_correction_lb,
                )
                post_dump_step = self._post_dump_rezero.update(
                    now_s=t,
                    raw_mv=raw_mv,
                    gross_lbs=target_relative_lbs,
                    is_stable=is_stable,
                    current_zero_offset_mv=cfg.zero_offset_mv,
                    cal_points=cal_points,
                    cfg=post_dump_cfg,
                )
                self._post_dump_rezero_active = post_dump_step.active
                self._post_dump_rezero_state = str(post_dump_step.state)
                self._post_dump_rezero_reason = str(post_dump_step.reason)
                self._post_dump_rezero_dump_age_s = float(post_dump_step.dump_age_s)
                self._post_dump_rezero_time_to_stable_s = post_dump_step.time_to_stable_s
                self._post_dump_rezero_time_to_empty_s = post_dump_step.time_to_empty_s
                self._post_dump_rezero_time_to_fill_resume_s = post_dump_step.time_to_fill_resume_s

                if (
                    post_dump_step.should_apply
                    and post_dump_step.new_zero_offset_mv is not None
                    and post_dump_step.new_zero_offset_lbs is not None
                ):
                    updated_utc = _utc_now()
                    try:
                        def _apply_post_dump_rezero(scale: dict, _: dict) -> None:
                            scale["zero_offset_mv"] = float(post_dump_step.new_zero_offset_mv)
                            scale["zero_offset_signal"] = float(post_dump_step.new_zero_offset_mv)
                            scale["zero_offset_lbs"] = float(post_dump_step.new_zero_offset_lbs)
                            scale["zero_offset_updated_utc"] = updated_utc

                        self.repo.update_config_section("scale", _apply_post_dump_rezero)

                        cfg.zero_offset_mv = float(post_dump_step.new_zero_offset_mv)
                        cfg.zero_offset_lbs = float(post_dump_step.new_zero_offset_lbs)
                        cfg.zero_offset_updated_utc = updated_utc
                        self._post_dump_rezero_last_apply_utc = updated_utc

                        # Clear any pending AZT deltas so stale adjustments can never be
                        # re-applied after a one-shot re-zero capture.
                        self._pending_zero_tracking_delta_lbs = 0.0
                        self._last_zero_tracking_persist_utc = updated_utc
                        self._zero_tracker.reset()

                        self.repo.log_event(
                            level="INFO",
                            code="POST_DUMP_REZERO_APPLIED",
                            message="Post-dump re-zero applied (one-shot capture).",
                            details={
                                "updated_utc": updated_utc,
                                "dump_age_s": float(post_dump_step.dump_age_s),
                                "gross_lbs": float(filtered_lbs),
                                "target_relative_lbs": float(target_relative_lbs),
                                "zero_target_lb": float(cfg.zero_target_lb),
                                "new_zero_offset_mv": float(post_dump_step.new_zero_offset_mv),
                                "new_zero_offset_lbs": float(post_dump_step.new_zero_offset_lbs),
                                "delta_offset_lbs": float(post_dump_step.delta_offset_lbs or 0.0),
                                "time_to_stable_s": post_dump_step.time_to_stable_s,
                                "time_to_empty_s": post_dump_step.time_to_empty_s,
                                "time_to_fill_resume_s": post_dump_step.time_to_fill_resume_s,
                            },
                        )

                        # Best-effort immediate recalculation so UI/output reflect the new
                        # offset without waiting for the next loop iteration.
                        adjusted_signal_mv = raw_mv - cfg.zero_offset_mv
                        recalc_weight_lbs, recalc_lbs_per_mv = map_signal_to_weight(adjusted_signal_mv, cal_points)
                        if recalc_weight_lbs is not None:
                            weight_lbs = float(recalc_weight_lbs)
                            if recalc_lbs_per_mv is not None:
                                lbs_per_mv = float(recalc_lbs_per_mv)
                            filtered_lbs = float(recalc_weight_lbs)
                            self._kalman.reset(filtered_lbs)
                            net_lbs = filtered_lbs - cfg.tare_offset_lbs
                            target_relative_lbs = filtered_lbs - cfg.zero_target_lb
                    except Exception as rez_err:  # noqa: BLE001
                        log.warning("Post-dump re-zero persistence failed: %s", rez_err)
                        self.repo.log_event(
                            level="WARNING",
                            code="POST_DUMP_REZERO_PERSIST_FAILED",
                            message="Post-dump re-zero persistence failed.",
                            details={"error": str(rez_err)[:500]},
                        )

                target_relative_lbs = filtered_lbs - cfg.zero_target_lb
                tracker_cfg = ZeroTrackingConfig(
                    enabled=(
                        self._daq_online
                        and cfg.zero_tracking_enabled
                        and (not startup_active)
                        and (not cfg.calibration_active)
                        and cal_valid
                        and (not manual_zero_gate_blocked)
                    ),
                    range_lb=cfg.zero_tracking_range_lb,
                    deadband_lb=cfg.zero_tracking_deadband_lb,
                    hold_s=cfg.zero_tracking_hold_s,
                    rate_lbs=cfg.zero_tracking_rate_lbs,
                    persist_interval_s=min(
                        cfg.zero_tracking_persist_interval_s,
                        max(0.2, cfg.config_refresh_s),
                    ),
                    negative_hold_s=cfg.zero_tracking_negative_hold_s,
                    startup_lockout_s=cfg.zero_tracking_startup_lockout_s,
                    max_correction_lb=cfg.zero_tracking_max_correction_lb,
                )
                tracking_step = self._zero_tracker.step(
                    now_s=t,
                    dt_s=dt,
                    display_lbs=target_relative_lbs,
                    tare_offset_lbs=cfg.tare_offset_lbs,
                    is_stable=is_stable,
                    current_zero_offset_lbs=cfg.zero_offset_lbs,
                    cfg=tracker_cfg,
                    spike_detected=spike_detected,
                )

                if abs(tracking_step.zero_offset_delta_lbs) > 1e-12:
                    # Convert lbs delta to mV delta before accumulating
                    delta_lbs = tracking_step.zero_offset_delta_lbs
                    delta_mv = (delta_lbs / lbs_per_mv) if (lbs_per_mv is not None and abs(lbs_per_mv) > 1e-9) else 0.0
                    cfg.zero_offset_mv += delta_mv
                    cfg.zero_offset_lbs += delta_lbs
                    self._pending_zero_tracking_delta_lbs += delta_lbs
                self._zero_tracking_active = tracking_step.active
                self._zero_tracking_locked = tracking_step.locked
                self._zero_tracking_reason = tracking_step.reason
                if (
                    manual_zero_gate_blocked
                    and (not startup_active)
                    and cal_valid
                    and cfg.zero_tracking_enabled
                ):
                    self._zero_tracking_reason = "manual_zero_required"
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
                            "target_relative_lbs": target_relative_lbs,
                            "zero_target_lb": float(cfg.zero_target_lb),
                            "tare_offset_lbs": cfg.tare_offset_lbs,
                            "range_lb": cfg.zero_tracking_range_lb,
                            "deadband_lb": cfg.zero_tracking_deadband_lb,
                            "spike_slope_lbs": spike_slope_lbs,
                        },
                    )

                if tracking_step.should_persist and abs(self._pending_zero_tracking_delta_lbs) > 1e-12:
                    pending_delta_lbs = float(self._pending_zero_tracking_delta_lbs)
                    pending_delta_mv = (pending_delta_lbs / lbs_per_mv) if (lbs_per_mv is not None and abs(lbs_per_mv) > 1e-9) else 0.0
                    updated_utc = _utc_now()
                    persisted: dict[str, float] = {}
                    try:
                        def _apply_zero_delta(scale: dict, _: dict) -> None:
                            old_mv = float(scale.get("zero_offset_mv", 0.0) or 0.0)
                            old_lbs = float(scale.get("zero_offset_lbs", 0.0) or 0.0)
                            new_mv = old_mv + pending_delta_mv
                            new_lbs = old_lbs + pending_delta_lbs
                            scale["zero_offset_mv"] = new_mv
                            scale["zero_offset_signal"] = new_mv
                            scale["zero_offset_lbs"] = new_lbs
                            scale["zero_offset_updated_utc"] = updated_utc
                            persisted["old_mv"] = old_mv
                            persisted["old_lbs"] = old_lbs
                            persisted["new_mv"] = new_mv
                            persisted["new_lbs"] = new_lbs

                        self.repo.update_config_section("scale", _apply_zero_delta)
                        cfg.zero_offset_mv = float(persisted.get("new_mv", cfg.zero_offset_mv))
                        cfg.zero_offset_lbs = float(persisted.get("new_lbs", cfg.zero_offset_lbs))
                        cfg.zero_offset_updated_utc = updated_utc
                        self._pending_zero_tracking_delta_lbs = 0.0
                        self._last_zero_tracking_persist_utc = updated_utc

                        self.repo.log_event(
                            level="INFO",
                            code="ZERO_TRACKING_APPLIED",
                            message=(
                                f"Auto zero tracking adjusted by "
                                f"{pending_delta_lbs:.3f} lb ({pending_delta_mv:.6f} mV)."
                            ),
                            details={
                                "raw_signal_mv": raw_mv,
                                "adjusted_signal_mv": adjusted_signal_mv,
                                "filtered_lbs": filtered_lbs,
                                "weight_correction_lbs": pending_delta_lbs,
                                "signal_correction_mv": pending_delta_mv,
                                "old_zero_offset_mv": float(persisted.get("old_mv", 0.0)),
                                "old_zero_offset_lbs": float(persisted.get("old_lbs", 0.0)),
                                "new_zero_offset_mv": cfg.zero_offset_mv,
                                "new_zero_offset_lbs": cfg.zero_offset_lbs,
                                "stable": is_stable,
                                "spike_slope_lbs": spike_slope_lbs,
                                "reason": tracking_step.reason,
                                "hold_elapsed_s": round(tracking_step.hold_elapsed_s, 3),
                            },
                        )
                    except Exception as persist_err:  # noqa: BLE001
                        log.warning("Failed to persist zero-tracking offset: %s", persist_err)

                # 6e. Smart Zero Clear (legacy) removed.
                # Industrial two-layer design uses:
                #   - micro-range AZT (continuous), and
                #   - post-dump re-zero (event-driven, gated).

                # 7. OUTPUT
                is_ma_mode = (cfg.output_mode == "4_20mA")
                units = "mA" if is_ma_mode else "V"
                startup_value = cfg.startup_output_value
                if is_ma_mode:
                    startup_value = max(4.0, min(20.0, float(startup_value)))
                else:
                    startup_value = max(0.0, min(10.0, float(startup_value)))
                # startup_active already computed above (step 1b)
                effective_armed = bool(cfg.armed or (cfg.startup_auto_arm and not startup_active))

                # One-shot auto-zero at end of startup (if enabled in settings).
                # Fires exactly once when startup_active transitions from True to False.
                if not startup_active and not self._startup_zero_done:
                    if manual_zero_gate_blocked:
                        # Hold startup auto-zero until the operator confirms empty hopper with manual ZERO.
                        pass
                    else:
                        self._startup_zero_done = True
                        if cfg.startup_auto_zero and cal_valid:
                            zero_target_lb = float(cfg.zero_target_lb)
                            slope_near_zero = estimate_lbs_per_mv(cal_points)
                            if slope_near_zero is not None and abs(slope_near_zero) > 1e-9:
                                drift_mv, _ = compute_zero_offset(raw_mv, cal_points, zero_target_lb=zero_target_lb)
                                drift_lbs = drift_mv * slope_near_zero
                                # Safety guard: if the drift exceeds the zero tracking
                                # range, the hopper likely has material in it.  Do NOT
                                # zero out real weight -- only correct small drift.
                                max_drift_lb = cfg.zero_tracking_range_lb
                                if abs(drift_lbs) > max_drift_lb:
                                    log.warning(
                                        "Startup auto-zero SKIPPED: drift %.2f lb exceeds "
                                        "range %.1f lb (hopper may be loaded)",
                                        drift_lbs, max_drift_lb,
                                    )
                                else:
                                    updated_utc = _utc_now()
                                    try:
                                        def _set_startup_zero(scale: dict, _: dict) -> None:
                                            scale["zero_offset_mv"] = float(drift_mv)
                                            scale["zero_offset_signal"] = float(drift_mv)
                                            scale["zero_offset_lbs"] = float(drift_lbs)
                                            scale["zero_offset_updated_utc"] = updated_utc

                                        self.repo.update_config_section("scale", _set_startup_zero)
                                    except Exception as startup_zero_err:  # noqa: BLE001
                                        log.warning("Startup auto-zero persistence failed: %s", startup_zero_err)
                                    cfg.zero_offset_mv = drift_mv
                                    cfg.zero_offset_lbs = drift_lbs
                                    cfg.zero_offset_updated_utc = updated_utc
                                    self._pending_zero_tracking_delta_lbs = 0.0
                                    self._last_zero_tracking_persist_utc = updated_utc
                                    # Recalculate with new offset (already applied in signal domain, so just update net)
                                    adjusted_signal_mv = raw_mv - cfg.zero_offset_mv
                                    mapped_weight_lbs, _ = map_signal_to_weight(adjusted_signal_mv, cal_points)
                                    if mapped_weight_lbs is not None:
                                        filtered_lbs = self._kalman.update(mapped_weight_lbs)
                                        net_lbs = filtered_lbs - cfg.tare_offset_lbs
                                    log.info(
                                        "Startup auto-zero applied: drift_mv=%.6f, slope=%.3f, offset=%.3f lb",
                                        drift_mv, slope_near_zero, cfg.zero_offset_lbs,
                                    )
                            else:
                                log.warning("Startup auto-zero skipped: calibration slope unavailable")

                output_fault = (not self._daq_online)
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
                output_mapping_mode = "profile" if plc_curve is not None else "linear"

                if startup_active:
                    out_cmd = self._writer.compute(
                        weight_lb=net_lbs,
                        output_mode=cfg.output_mode,
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
                    use_target_signal_mode = (
                        cfg.job_control_enabled and cfg.job_control_mode == "target_signal_mode"
                    )
                    if use_target_signal_mode:
                        # Simple threshold: scale_weight >= set_weight → trigger signal, else → low.
                        pretrigger_lb = (
                            cfg.job_control_pretrigger_lb
                            if cfg.job_control_trigger_mode == "early"
                            else 0.0
                        )
                        with self._job_lock:
                            set_weight = self._job_set_weight
                        threshold = max(0.0, set_weight - pretrigger_lb) if set_weight > 0.0 else 0.0
                        if set_weight > 0.0 and net_lbs >= threshold:
                            raw_signal_value = cfg.job_control_trigger_signal_value
                        else:
                            raw_signal_value = cfg.job_control_low_signal_value
                        clamped_signal = self._clamp_output_value(raw_signal_value, cfg.output_mode)
                        out_cmd = OutputCommand(value=clamped_signal, units=units)
                        self._writer.prime_output(out_cmd.value, units)
                        output_mapping_mode = "target_signal"
                    else:
                        out_cmd = self._writer.compute(
                            weight_lb=net_lbs,
                            output_mode=cfg.output_mode,
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

                job_status = self.get_job_control_status()

                # 8. WRITE to MegaIND
                if self._megaind_online:
                    try:
                        if cfg.output_mode == "4_20mA":
                            self.hw.megaind.write_analog_out_ma(cfg.ao_channel_ma, out_cmd.value)
                        else:
                            self.hw.megaind.write_analog_out_v(cfg.ao_channel_v, out_cmd.value)
                    except Exception:
                        self._megaind_online = False

                # 9. POLL opto buttons
                if self._megaind_online:
                    self._poll_buttons(cfg, raw_mv, weight_lbs)

                # 10. UPDATE state for UI
                self._loop_count += 1
                
                # --- High-Res Logging for PLC Lag Diagnosis ---
                # Log every loop iteration (20 Hz) to trends_total for detailed analysis.
                # This captures: timestamp, current weight, stability, output mode, and output command.
                # Only log if current time is after Monday 6:00 AM (2026-02-23 06:00:00 UTC-5)
                # Hardcoded start time: 1771844400 (Monday Feb 23 2026 06:00:00 EST)
                if self._loop_count % 1 == 0 and time.time() >= 1771844400:  # Log every sample (20Hz) after Monday 6am
                    try:
                        self.repo.add_total_sample(
                            total_lbs=net_lbs,
                            stable=is_stable,
                            output_mode=cfg.output_mode,
                            output_cmd=out_cmd.value,
                        )
                    except Exception as log_err:
                        # Don't crash loop on logging failure
                        pass
                # ----------------------------------------------

                io_live = self._daq_online and self._megaind_online
                fault_state = (not self._daq_online) or (not self._megaind_online)
                fault_reason: Optional[str] = None
                if not self._daq_online:
                    fault_reason = "DAQ offline"
                elif not self._megaind_online:
                    fault_reason = "MegaIND offline"
                # Round-up is presentation-only; keep control path unrounded.
                display_filtered_lbs = (
                    math.ceil(filtered_lbs) if (cfg.round_up_enabled and filtered_lbs > 0.0) else filtered_lbs
                )
                display_net_lbs = display_filtered_lbs - cfg.tare_offset_lbs
                output_profile_active = bool(
                    (plc_curve is not None) and (output_mapping_mode == "profile")
                )
                output_profile_points = int(len(plc_points) if output_mapping_mode != "target_signal" else 0)
                self.state.set(
                    # Raw data
                    raw_signal_mv=raw_mv,
                    total_signal=raw_mv,        # Legacy key for routes
                    signal_for_cal=raw_mv,      # Used by calibration endpoints (RAW, no zero adj)
                    # Weight
                    raw_weight_lbs=weight_lbs,
                    total_weight_lbs=display_net_lbs,
                    filtered_weight_lbs=filtered_lbs,
                    zeroed_weight_lbs=filtered_lbs,  # Already zeroed (zero applied in signal domain)
                    lbs_per_mv=(float(lbs_per_mv) if lbs_per_mv is not None else 0.0),
                    tare_offset_lbs=cfg.tare_offset_lbs,
                    zero_target_lb=cfg.zero_target_lb,
                    zero_offset_lbs=cfg.zero_offset_lbs,
                    zero_offset_mv=cfg.zero_offset_mv,
                    zero_offset_signal=cfg.zero_offset_mv,
                    zero_offset_updated_utc=cfg.zero_offset_updated_utc,
                    zero_tracking_enabled=cfg.zero_tracking_enabled,
                    zero_tracking_active=self._zero_tracking_active,
                    zero_tracking_locked=self._zero_tracking_locked,
                    zero_tracking_reason=self._zero_tracking_reason,
                    zero_tracking_hold_elapsed_s=self._zero_tracking_hold_elapsed_s,
                    zero_tracking_spike_slope_lbs=self._zero_tracking_spike_slope_lbs,
                    post_dump_rezero_enabled=bool(cfg.post_dump_rezero_enabled),
                    post_dump_rezero_active=self._post_dump_rezero_active,
                    post_dump_rezero_state=self._post_dump_rezero_state,
                    post_dump_rezero_reason=self._post_dump_rezero_reason,
                    post_dump_rezero_dump_age_s=self._post_dump_rezero_dump_age_s,
                    post_dump_rezero_time_to_stable_s=self._post_dump_rezero_time_to_stable_s,
                    post_dump_rezero_time_to_empty_s=self._post_dump_rezero_time_to_empty_s,
                    post_dump_rezero_time_to_fill_resume_s=self._post_dump_rezero_time_to_fill_resume_s,
                    post_dump_rezero_last_apply_utc=self._post_dump_rezero_last_apply_utc,
                    auto_zero_armed=auto_zero_armed,
                    startup_require_manual_zero_before_auto_zero=(
                        cfg.startup_require_manual_zero_before_auto_zero
                    ),
                    # Output
                    output_command=out_cmd.value,
                    output_units=out_cmd.units,
                    output_mode=cfg.output_mode,
                    output_armed=effective_armed,
                    output_test_mode=cfg.test_mode,
                    output_test_value=cfg.test_value,
                    output_calibration_active=cfg.calibration_active,
                    output_nudge_value=cfg.nudge_value,
                    output_mapping_mode=output_mapping_mode,
                    output_profile_active=output_profile_active,
                    output_profile_points=output_profile_points,
                    ao_channel_v=cfg.ao_channel_v,
                    ao_channel_ma=cfg.ao_channel_ma,
                    # Job-target mode / webhook state
                    job_control_enabled=cfg.job_control_enabled,
                    job_control_mode=cfg.job_control_mode,
                    job_control_trigger_mode=cfg.job_control_trigger_mode,
                    job_control_pretrigger_lb=(
                        cfg.job_control_pretrigger_lb
                        if cfg.job_control_trigger_mode == "early"
                        else 0.0
                    ),
                    job_set_weight=float(job_status.get("set_weight", 0.0)),
                    job_active=bool(job_status.get("active", False)),
                    job_meta=job_status.get("meta"),
                    # Hardware status
                    io_live=io_live,
                    daq_online=self._daq_online,
                    megaind_online=self._megaind_online,
                    # Stability / fault
                    stable=is_stable,
                    fault=fault_state,
                    fault_reason=fault_reason,
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

        # Best-effort flush of any pending zero-tracking delta on graceful stop.
        if self._cfg is not None and abs(self._pending_zero_tracking_delta_lbs) > 1e-12:
            cal_points = self.repo.get_calibration_points()
            lbs_per_mv_stop = estimate_lbs_per_mv(cal_points)
            if lbs_per_mv_stop is not None and abs(lbs_per_mv_stop) > 1e-9:
                pending_delta_lbs = float(self._pending_zero_tracking_delta_lbs)
                pending_delta_mv = pending_delta_lbs / lbs_per_mv_stop
                updated_utc = _utc_now()
                try:
                    persisted: dict[str, float] = {}

                    def _apply_stop_flush(scale: dict, _: dict) -> None:
                        old_mv = float(scale.get("zero_offset_mv", 0.0) or 0.0)
                        old_lbs = float(scale.get("zero_offset_lbs", 0.0) or 0.0)
                        new_mv = old_mv + pending_delta_mv
                        new_lbs = old_lbs + pending_delta_lbs
                        scale["zero_offset_mv"] = new_mv
                        scale["zero_offset_signal"] = new_mv
                        scale["zero_offset_lbs"] = new_lbs
                        scale["zero_offset_updated_utc"] = updated_utc
                        persisted["new_mv"] = new_mv
                        persisted["new_lbs"] = new_lbs

                    self.repo.update_config_section("scale", _apply_stop_flush)
                    self._cfg.zero_offset_mv = float(persisted.get("new_mv", self._cfg.zero_offset_mv))
                    self._cfg.zero_offset_lbs = float(persisted.get("new_lbs", self._cfg.zero_offset_lbs))
                    self._cfg.zero_offset_updated_utc = updated_utc
                    self._pending_zero_tracking_delta_lbs = 0.0
                    self._last_zero_tracking_persist_utc = updated_utc
                    log.info(
                        "Flushed pending zero-tracking delta on stop: %.3f lb (%.6f mV)",
                        pending_delta_lbs,
                        pending_delta_mv,
                    )
                except Exception as stop_flush_err:  # noqa: BLE001
                    log.warning("Failed to flush pending zero-tracking offset on stop: %s", stop_flush_err)

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
            if not cfg.allow_opto_tare:
                now = time.monotonic()
                if (now - self._last_blocked_tare_log_s) >= 30.0:
                    self._last_blocked_tare_log_s = now
                    self.repo.log_event(
                        level="WARNING",
                        code="OPTO_TARE_BLOCKED",
                        message="Ignored opto TARE trigger because allow_opto_tare is disabled.",
                        details={"gross_lbs": float(gross_lbs)},
                    )
                return
            updated_utc = _utc_now()
            try:
                def _set_tare(scale: dict, _: dict) -> None:
                    scale["tare_offset_lbs"] = float(gross_lbs)
                    scale["last_tare_utc"] = updated_utc

                self.repo.update_config_section("scale", _set_tare)
            except Exception as tare_err:  # noqa: BLE001
                log.warning("Button TARE persistence failed: %s", tare_err)
                return
            cfg.tare_offset_lbs = float(gross_lbs)
            self.repo.log_event(
                level="INFO",
                code="BUTTON_TARE_APPLIED",
                message=f"Opto button TARE applied at {gross_lbs:.2f} lb.",
                details={"gross_lbs": float(gross_lbs)},
            )
            log.info("Button TARE: offset=%.2f lb", gross_lbs)

        elif action == "zero":
            cal_points = self.repo.get_calibration_points()
            slope_near_zero = estimate_lbs_per_mv(cal_points)
            if slope_near_zero is None or abs(slope_near_zero) <= 1e-9:
                log.warning("Button ZERO ignored: calibration slope unavailable")
                return

            c_for_zero = self.repo.get_latest_config()
            zero_target_lb = float((c_for_zero.get("scale") or {}).get("zero_target_lb", 0.0) or 0.0)
            new_offset_mv, _ = compute_zero_offset(raw_mv, cal_points, zero_target_lb=zero_target_lb)
            new_offset_lbs = new_offset_mv * slope_near_zero

            c = self.repo.get_latest_config()
            s = c.get("scale") or {}
            old_offset_lbs = float(s.get("zero_offset_lbs", 0.0) or 0.0)
            old_offset_mv = float(s.get("zero_offset_mv", 0.0) or 0.0)
            updated_utc = _utc_now()
            try:
                def _set_zero(scale: dict, _: dict) -> None:
                    scale["zero_offset_mv"] = float(new_offset_mv)
                    scale["zero_offset_signal"] = float(new_offset_mv)
                    scale["zero_offset_lbs"] = float(new_offset_lbs)
                    scale["zero_offset_updated_utc"] = updated_utc

                self.repo.update_config_section("scale", _set_zero)
            except Exception as zero_err:  # noqa: BLE001
                log.warning("Button ZERO persistence failed: %s", zero_err)
                return
            cfg.zero_offset_mv = new_offset_mv
            cfg.zero_offset_lbs = new_offset_lbs
            cfg.zero_offset_updated_utc = updated_utc
            self._pending_zero_tracking_delta_lbs = 0.0
            self._last_zero_tracking_persist_utc = updated_utc
            drift_mv = new_offset_mv - old_offset_mv
            self.mark_manual_zero_seen(source="opto_button_zero")
            log.info(
                "Button ZERO: drift_mv=%.6f, slope=%.3f, offset_mv=%.6f, offset_lbs=%.3f (old_lbs=%.3f)",
                drift_mv, slope_near_zero, new_offset_mv, new_offset_lbs, old_offset_lbs,
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
