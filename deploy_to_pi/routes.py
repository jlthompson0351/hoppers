from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, Response, current_app, redirect, render_template, request, url_for

from src.core.zeroing import compute_zero_offset, estimate_lbs_per_mv
from src.db.repo import AppRepository
from src.services.state import LiveState

bp = Blueprint("routes", __name__)

GAIN_CODE_LABELS = {
    0: "±24V",
    1: "±12V",
    2: "±6V",
    3: "±3V",
    4: "±1.5V",
    5: "±0.75V",
    6: "±0.37V",
    7: "±0.18V",
}

DAQ_ROLES = [
    "Not used",
    "Load Cell (active)",
    "Spare / Diagnostic",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@bp.get("/")
def dashboard() -> str:
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    snap = state.snapshot()
    cfg = repo.get_latest_config()
    display = cfg.get("display", {})
    ui = cfg.get("ui", {}) or {}
    poll_rate_ms = int(ui.get("poll_rate_ms", 500) or 500)
    poll_rate_ms = max(100, min(5000, poll_rate_ms))
    return render_template("dashboard.html", snap=snap, display=display, poll_rate_ms=poll_rate_ms, now=_utc_now())


@bp.get("/config")
def config_get() -> str:
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    return render_template("config.html", cfg_json=json.dumps(cfg, indent=2), now=_utc_now())


@bp.post("/config")
def config_post() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    raw = request.form.get("cfg_json", "").strip()
    try:
        cfg = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        repo.log_event(level="ERROR", code="CONFIG_JSON_INVALID", message=str(e), details={"raw": raw[:500]})
        return redirect(url_for("routes.config_get"))
    repo.save_config(cfg)
    return redirect(url_for("routes.config_get"))


@bp.get("/calibration")
def calibration_get() -> str:
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    points = repo.get_calibration_points()
    points_v = repo.get_plc_profile_points(output_mode="0_10V")
    points_ma = repo.get_plc_profile_points(output_mode="4_20mA")
    cfg = repo.get_latest_config()
    snap = state.snapshot()
    ui = cfg.get("ui", {}) or {}
    poll_rate_ms = int(ui.get("poll_rate_ms", 500) or 500)
    poll_rate_ms = max(100, min(5000, poll_rate_ms))
    return render_template(
        "calibration.html", 
        points=points, 
        points_v=points_v, 
        points_ma=points_ma, 
        cfg=cfg, 
        snap=snap, 
        poll_rate_ms=poll_rate_ms, 
        now=_utc_now()
    )


def _maintenance_enabled(repo: AppRepository) -> bool:
    # Context processor injects this for templates, but routes should enforce it too.
    import os

    env_on = os.environ.get("LCS_MAINTENANCE_UI", "").strip().lower() in ("1", "true", "yes", "on")
    cfg = repo.get_latest_config()
    cfg_on = bool((cfg.get("ui") or {}).get("maintenance_enabled", False))
    return bool(env_on or cfg_on)


@bp.get("/scale-settings")
def scale_settings_get() -> str:
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    if not _maintenance_enabled(repo):
        # Hide existence unless enabled.
        return "Not found", 404

    cfg = repo.get_latest_config()
    snap = state.snapshot()

    daq_cfg = cfg.get("daq24b8vin") or {}
    channels = list(daq_cfg.get("channels") or [])
    while len(channels) < 8:
        channels.append({"enabled": False, "role": "Not used", "gain_code": 7})
    channels = channels[:8]

    # Attach live readings if available
    live = {int(c.get("ch")): c for c in (snap.get("channels") or []) if isinstance(c, dict) and "ch" in c}
    rows = []
    for i in range(8):
        ch_cfg = channels[i] or {}
        live_row = live.get(i) or {}
        raw_mv = live_row.get("raw_mV", 0.0) or 0.0
        rows.append(
            {
                "idx": i,
                "ch_display": i + 1,
                "enabled": bool(ch_cfg.get("enabled", False)),
                "role": str(ch_cfg.get("role", "Not used")),
                "gain_code": int(ch_cfg.get("gain_code", 7)),
                "raw_v": float(raw_mv) / 1000.0,
                "polled": bool(live_row.get("polled", False)),
            }
        )

    return render_template(
        "scale_settings.html",
        now=_utc_now(),
        snap=snap,
        cfg=cfg,
        rows=rows,
        gain_labels=GAIN_CODE_LABELS,
        roles=DAQ_ROLES,
    )


@bp.post("/scale-settings")
def scale_settings_post() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    if not _maintenance_enabled(repo):
        return redirect(url_for("routes.dashboard"))

    cfg = repo.get_latest_config()
    snap = state.snapshot()
    action = (request.form.get("action") or "").strip()

    if action == "save_daq":
        daq_cfg = cfg.get("daq24b8vin") or {}
        daq_cfg["stack_level"] = int(request.form.get("daq_stack_level", daq_cfg.get("stack_level", 0)) or 0)
        chans = []
        for i in range(8):
            enabled = request.form.get(f"ch_enabled_{i}") == "on"
            role = request.form.get(f"ch_role_{i}", "Not used")
            # Smart default: if switching to Load Cell, default to gain 7 (smallest range, high sensitivity) if not set.
            # But here we just take what they picked. The UI JS can handle the 'smart default' UX.
            gain_code = int(request.form.get(f"ch_gain_{i}", "7") or 7)
            chans.append({"enabled": bool(enabled), "role": str(role), "gain_code": int(gain_code)})
        daq_cfg["channels"] = chans
        cfg["daq24b8vin"] = daq_cfg
        repo.save_config(cfg)

    elif action == "read_gain_codes":
        # Read current gain codes from the (simulated or real) board and store to config.
        svc = current_app.config.get("ACQ_SERVICE")
        hw = getattr(svc, "hw", None) if svc is not None else None
        if hw is None:
            repo.log_event(level="WARNING", code="GAIN_READ_NO_HW", message="No hardware handle available.", details={})
        else:
            daq_cfg = cfg.get("daq24b8vin") or {}
            chans = list(daq_cfg.get("channels") or [])
            while len(chans) < 8:
                chans.append({"enabled": False, "role": "Not used", "gain_code": 7})
            chans = chans[:8]
            try:
                for i in range(8):
                    chans[i]["gain_code"] = int(hw.daq.get_gain_code(i))
                daq_cfg["channels"] = chans
                cfg["daq24b8vin"] = daq_cfg
                repo.save_config(cfg)
            except Exception as e:  # noqa: BLE001
                repo.log_event(level="ERROR", code="GAIN_READ_FAILED", message=str(e), details={})

    elif action == "apply_gain_codes":
        svc = current_app.config.get("ACQ_SERVICE")
        hw = getattr(svc, "hw", None) if svc is not None else None
        if hw is None:
            repo.log_event(level="WARNING", code="GAIN_APPLY_NO_HW", message="No hardware handle available.", details={})
        else:
            daq_cfg = cfg.get("daq24b8vin") or {}
            chans = list(daq_cfg.get("channels") or [])
            while len(chans) < 8:
                chans.append({"enabled": False, "role": "Not used", "gain_code": 7})
            chans = chans[:8]
            try:
                for i in range(8):
                    hw.daq.set_gain_code(i, int((chans[i] or {}).get("gain_code", 7)))
                repo.log_event(level="INFO", code="GAIN_APPLY_OK", message="Applied DAQ gain codes to board.", details={})
            except Exception as e:  # noqa: BLE001
                repo.log_event(level="ERROR", code="GAIN_APPLY_FAILED", message=str(e), details={})

    elif action == "tare_zero":
        if not snap.get("stable", False):
            repo.log_event(level="WARNING", code="TARE_REJECTED_UNSTABLE", message="Tare rejected: unstable.", details={})
        else:
            scale = cfg.get("scale") or {}
            scale["tare_offset_lbs"] = float(snap.get("total_weight_lbs", 0.0) or 0.0)
            cfg["scale"] = scale
            repo.save_config(cfg)

    elif action == "tare_clear":
        scale = cfg.get("scale") or {}
        scale["tare_offset_lbs"] = 0.0
        cfg["scale"] = scale
        repo.save_config(cfg)

    elif action == "save_output":
        out = cfg.get("output") or {}
        out["mode"] = request.form.get("output_mode", out.get("mode", "0_10V"))
        # MegaIND analog channels are 1..4.
        ao_v = int(request.form.get("ao_channel_v", out.get("ao_channel_v", 1)) or 1)
        ao_ma = int(request.form.get("ao_channel_ma", out.get("ao_channel_ma", 1)) or 1)
        out["ao_channel_v"] = max(1, min(4, ao_v))
        out["ao_channel_ma"] = max(1, min(4, ao_ma))
        cfg["output"] = out
        repo.save_config(cfg)

    else:
        repo.log_event(level="WARNING", code="SCALE_SETTINGS_UNKNOWN_ACTION", message="Unknown action.", details={"action": action})

    return redirect(url_for("routes.scale_settings_get"))


@bp.post("/calibration/add")
def calibration_add() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    snap = state.snapshot()

    known_weight = float(request.form.get("known_weight_lbs", "0") or 0)
    if not snap.get("stable", False):
        repo.log_event(
            level="WARNING",
            code="CAL_POINT_REJECTED_UNSTABLE",
            message="Calibration point rejected: scale not stable.",
            details={"known_weight_lbs": known_weight},
        )
        return redirect(url_for("routes.calibration_get"))

    repo.add_calibration_point(
        known_weight_lbs=known_weight,
        signal=snap.get("signal_for_cal", 0.0),
    )
    return redirect(url_for("routes.calibration_get"))


@bp.get("/plc-profile")
def plc_profile_get() -> Response:
    # Redirect legacy page to new Hub
    return redirect(url_for("routes.calibration_get"))


@bp.post("/plc-profile/add")
def plc_profile_add() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    output_mode = request.form.get("output_mode", "0_10V").strip()
    analog_value = float(request.form.get("analog_value", "0") or 0)
    plc_displayed_lbs = float(request.form.get("plc_displayed_lbs", "0") or 0)
    repo.add_plc_profile_point(
        output_mode=output_mode,
        analog_value=analog_value,
        plc_displayed_lbs=plc_displayed_lbs,
    )
    return redirect(url_for("routes.plc_profile_get"))


@bp.get("/logs")
def logs_get() -> str:
    repo: AppRepository = current_app.config["REPO"]
    events = repo.get_recent_events(limit=200)
    return render_template("logs.html", events=events, now=_utc_now())


@bp.get("/settings")
def settings_get() -> str:
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    cfg = repo.get_latest_config()
    snap = state.snapshot()

    # Build channel rows for DAQ table
    daq_cfg = cfg.get("daq24b8vin") or {}
    channels = list(daq_cfg.get("channels") or [])
    while len(channels) < 8:
        channels.append({"enabled": False, "role": "Not used", "gain_code": 7})
    channels = channels[:8]

    live = {int(c.get("ch")): c for c in (snap.get("channels") or []) if isinstance(c, dict) and "ch" in c}
    rows = []
    for i in range(8):
        ch_cfg = channels[i] or {}
        live_row = live.get(i) or {}
        raw_mv = live_row.get("raw_mV", 0.0) or 0.0
        rows.append({
            "idx": i,
            "ch_display": i + 1,
            "enabled": bool(ch_cfg.get("enabled", False)),
            "role": str(ch_cfg.get("role", "Not used")),
            "gain_code": int(ch_cfg.get("gain_code", 7)),
            "raw_v": float(raw_mv) / 1000.0,
            "polled": bool(live_row.get("polled", False)),
        })

    return render_template(
        "settings.html",
        now=_utc_now(),
        snap=snap,
        cfg=cfg,
        rows=rows,
        gain_labels=GAIN_CODE_LABELS,
        roles=DAQ_ROLES,
    )


@bp.post("/settings")
def settings_post() -> Response:
    """Save all settings from the comprehensive settings page."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()

    # Helper to parse boolean from form
    def parse_bool(key: str, default: bool = False) -> bool:
        val = request.form.get(key, "0")
        return val in ("1", "on", "true", "yes")

    # Helper to parse optional float
    def parse_float_opt(key: str) -> Optional[float]:
        val = request.form.get(key, "").strip()
        if not val:
            return None
        try:
            return float(val)
        except ValueError:
            return None

    # Helper to parse float with default
    def parse_float(key: str, default: float) -> float:
        val = request.form.get(key, "").strip()
        if not val:
            return default
        try:
            return float(val)
        except ValueError:
            return default

    # Helper to parse int with default
    def parse_int(key: str, default: int) -> int:
        val = request.form.get(key, "").strip()
        if not val:
            return default
        try:
            return int(val)
        except ValueError:
            return default

    # === Quick Setup ===
    cfg.setdefault("range", {})
    cfg["range"]["min_lb"] = parse_float("range_min_lb", 0.0)
    cfg["range"]["max_lb"] = parse_float("range_max_lb", 300.0)

    cfg.setdefault("output", {})
    cfg["output"]["mode"] = request.form.get("output_mode", "0_10V")
    channel = parse_int("output_channel", 1)
    cfg["output"]["ao_channel_v"] = channel
    cfg["output"]["ao_channel_ma"] = channel
    safe = parse_float("safe_output", 0.0)
    if cfg["output"]["mode"] == "4_20mA":
        cfg["output"]["safe_ma"] = safe
    else:
        cfg["output"]["safe_v"] = safe

    cfg.setdefault("excitation", {})
    cfg["excitation"]["ai_channel"] = parse_int("excitation_ai_channel", 1)
    cfg["excitation"]["warn_v"] = parse_float("excitation_warn_v", 9.0)
    cfg["excitation"]["fault_v"] = parse_float("excitation_fault_v", 8.0)

    # === Signal Tuning ===
    cfg.setdefault("filter", {})
    cfg["filter"]["use_kalman"] = parse_bool("use_kalman", True)
    cfg["filter"]["kalman_process_noise"] = parse_float("kalman_process_noise", 1.0)
    cfg["filter"]["kalman_measurement_noise"] = parse_float("kalman_measurement_noise", 50.0)
    cfg["filter"]["alpha"] = parse_float("filter_alpha", 0.18)
    cfg["filter"]["stability_window"] = parse_int("stability_window", 25)
    cfg["filter"]["stability_stddev_lb"] = parse_float("stability_stddev_lb", 0.8)
    cfg["filter"]["stability_slope_lbs"] = parse_float("stability_slope_lbs", 0.8)
    cfg["filter"]["median_enabled"] = parse_bool("median_enabled", False)
    cfg["filter"]["median_window"] = parse_int("median_window", 5)
    cfg["filter"]["notch_enabled"] = parse_bool("notch_enabled", False)
    cfg["filter"]["notch_freq"] = parse_int("notch_freq", 60)

    # === Display ===
    cfg.setdefault("display", {})
    cfg["display"]["weight_decimals"] = parse_int("weight_decimals", 1)
    cfg["display"]["round_up_enabled"] = parse_bool("round_up_enabled", False)
    cfg["display"]["show_decimal_point"] = parse_bool("show_decimal_point", True)

    # === Zero & Scale ===
    cfg.setdefault("zero_tracking", {})
    cfg["zero_tracking"]["enabled"] = parse_bool("zero_tracking_enabled", False)
    cfg["zero_tracking"]["range_lb"] = parse_float("zero_tracking_range", 0.5)
    cfg["zero_tracking"]["deadband_lb"] = parse_float("zero_tracking_deadband", 0.1)
    cfg["zero_tracking"]["hold_s"] = parse_float("zero_tracking_hold_s", 6.0)
    cfg["zero_tracking"]["rate_lbs"] = parse_float("zero_tracking_rate", 0.1)
    cfg["zero_tracking"]["persist_interval_s"] = parse_float("zero_tracking_persist_interval_s", 1.0)

    cfg.setdefault("startup", {})
    cfg["startup"]["auto_zero"] = parse_bool("startup_auto_zero", False)
    cfg["startup"]["delay_s"] = parse_int("startup_delay_s", 5)
    cfg["startup"]["output_value"] = parse_float("startup_output", 0.0)
    cfg["startup"]["auto_arm"] = parse_bool("startup_auto_arm", False)

    # NOTE: ratiometric removed - always use raw mV

    cfg["output"]["test_mode"] = parse_bool("test_mode", False)
    cfg["output"]["test_value"] = parse_float("test_value", 0.0)
    cfg["output"]["calibration_active"] = parse_bool("calibration_active", False)
    cfg["output"]["nudge_value"] = parse_float("nudge_value", 0.0)
    
    # === Output Control ===
    cfg["output"]["deadband_enabled"] = parse_bool("deadband_enabled", True)
    cfg["output"]["deadband_lb"] = parse_float("deadband_lb", 0.5)
    cfg["output"]["ramp_enabled"] = parse_bool("ramp_enabled", False)
    cfg["output"]["ramp_rate_v"] = parse_float("ramp_rate_v", 5.0)
    cfg["output"]["ramp_rate_ma"] = parse_float("ramp_rate_ma", 8.0)

    # === Alarms & Limits ===
    cfg.setdefault("alarms", {})
    cfg["alarms"]["overload_lb"] = parse_float_opt("overload_threshold_lb")
    cfg["alarms"]["overload_action"] = request.form.get("overload_action", "alarm")
    cfg["alarms"]["allow_negative"] = parse_bool("allow_negative", False)
    cfg["alarms"]["underload_lb"] = parse_float("underload_threshold_lb", -5)
    cfg["alarms"]["high_lb"] = parse_float_opt("alarm_high_lb")
    cfg["alarms"]["low_lb"] = parse_float_opt("alarm_low_lb")
    cfg["alarms"]["rate_lbs"] = parse_float_opt("alarm_rate_lbs")

    cfg.setdefault("fault", {})
    cfg["fault"]["delay_s"] = parse_float("fault_delay_s", 2.0)
    cfg["fault"]["recovery"] = request.form.get("fault_recovery", "auto")

    # === DAQ Channels ===
    cfg.setdefault("daq24b8vin", {})
    cfg["daq24b8vin"]["stack_level"] = parse_int("daq_stack_level", 0)
    cfg["daq24b8vin"]["average_samples"] = parse_int("daq_average_samples", 2)
    channels = []
    for i in range(8):
        enabled = request.form.get(f"ch_enabled_{i}") == "on"
        role = request.form.get(f"ch_role_{i}", "Not used")
        gain_code = parse_int(f"ch_gain_{i}", 7)
        channels.append({"enabled": enabled, "role": role, "gain_code": gain_code})
    cfg["daq24b8vin"]["channels"] = channels

    # === Detection ===
    cfg.setdefault("dump_detection", {})
    cfg["dump_detection"]["drop_threshold_lb"] = parse_float("dump_drop_threshold_lb", 25.0)
    cfg["dump_detection"]["min_prev_stable_lb"] = parse_float("dump_min_prev_stable_lb", 10.0)

    cfg.setdefault("drift", {})
    cfg["drift"]["ratio_threshold"] = parse_float("drift_ratio_threshold", 0.12)
    cfg["drift"]["ema_alpha"] = parse_float("drift_ema_alpha", 0.02)
    cfg["drift"]["consecutive_required"] = parse_int("drift_consecutive", 20)

    # === Timing ===
    cfg.setdefault("timing", {})
    cfg["timing"]["loop_rate_hz"] = parse_int("loop_rate_hz", 20)
    cfg["timing"]["config_refresh_s"] = parse_float("config_refresh_s", 2.0)
    cfg["timing"]["i2c_retry_count"] = parse_int("i2c_retry_count", 3)
    cfg["timing"]["board_offline_s"] = parse_int("board_offline_s", 5)

    cfg.setdefault("ui", {})
    cfg["ui"]["poll_rate_ms"] = parse_int("ui_poll_rate_ms", 500)

    # === Logging ===
    cfg.setdefault("logging", {})
    cfg["logging"]["interval_s"] = parse_int("log_interval_s", 1)
    cfg["logging"]["retention_days"] = parse_int("log_retention_days", 30)
    cfg["logging"]["log_raw"] = parse_bool("log_raw", False)
    cfg["logging"]["log_weight"] = parse_bool("log_weight", True)
    cfg["logging"]["log_output"] = parse_bool("log_output", True)
    cfg["logging"]["event_only"] = parse_bool("log_event_only", False)

    # === Advanced ===
    cfg.setdefault("watchdog", {})
    cfg["watchdog"]["daq_enabled"] = parse_bool("daq_wdt_enabled", False)
    cfg["watchdog"]["daq_period_s"] = parse_int("daq_wdt_period_s", 120)
    cfg["watchdog"]["megaind_enabled"] = parse_bool("megaind_wdt_enabled", False)
    cfg["watchdog"]["megaind_period_s"] = parse_int("megaind_wdt_period_s", 120)

    cfg.setdefault("rs485", {})
    cfg["rs485"]["enabled"] = parse_bool("rs485_enabled", False)

    cfg.setdefault("onewire", {})
    cfg["onewire"]["enabled"] = parse_bool("onewire_enabled", False)

    cfg.setdefault("leds", {})
    cfg["leds"]["enabled"] = parse_bool("leds_enabled", False)

    # === MegaIND I/O (Maintenance / Extra Controls) ===
    # This is intentionally separate from the PLC Output logic:
    # - PLC Output uses cfg["output"] and is driven continuously by the acquisition loop.
    # - MegaIND I/O is meant for simple extra channel control + rules.
    cfg.setdefault("megaind", {})
    cfg["megaind"]["stack_level"] = max(0, min(7, parse_int("megaind_stack_level", int((cfg.get("megaind") or {}).get("stack_level", 0) or 0))))

    cfg.setdefault("megaind_io", {})
    cfg["megaind_io"]["armed"] = parse_bool("megaind_io_armed", True)
    cfg["megaind_io"]["allow_plc_channel"] = parse_bool("megaind_io_allow_plc_channel", False)
    cfg["megaind_io"]["safe_v"] = parse_float("megaind_io_safe_v", 0.0)
    
    # Parse role map
    role_map = {}
    for key in request.form:
        if key.startswith("role_map_"):
            pin = key.replace("role_map_", "")
            role = request.form.get(key)
            if role:
                role_map[pin] = role
    if role_map:
        cfg["megaind_io"]["role_map"] = role_map

    # Manual 0-10V outputs (channels 1..4)
    ao_v = []
    for ch in range(1, 5):
        enabled = parse_bool(f"mi_ao_v_enabled_{ch}", False)
        value_v = parse_float(f"mi_ao_v_value_{ch}", 0.0)
        ao_v.append({"enabled": bool(enabled), "value_v": float(value_v)})
    cfg["megaind_io"]["ao_v"] = ao_v

    # Simple rules (fixed slots 1..4)
    rules = []
    for i in range(1, 5):
        enabled = parse_bool(f"mi_rule_enabled_{i}", False)
        kind = (request.form.get(f"mi_rule_input_kind_{i}", "ai_v") or "ai_v").strip()
        in_ch = parse_int(f"mi_rule_input_ch_{i}", 1)
        condition = (request.form.get(f"mi_rule_condition_{i}", "gte") or "gte").strip()
        threshold = parse_float(f"mi_rule_threshold_{i}", 0.0)
        out_ch = parse_int(f"mi_rule_output_ch_{i}", 1)
        true_value_v = parse_float(f"mi_rule_true_value_{i}", 0.0)
        else_enabled = parse_bool(f"mi_rule_else_enabled_{i}", False)
        false_value_v = parse_float(f"mi_rule_false_value_{i}", 0.0)
        rules.append(
            {
                "enabled": bool(enabled),
                "input_kind": str(kind),
                "input_ch": int(in_ch),
                "condition": str(condition),
                "threshold": float(threshold),
                "output_ch": int(out_ch),
                "true_value_v": float(true_value_v),
                "else_enabled": bool(else_enabled),
                "false_value_v": float(false_value_v),
            }
        )
    cfg["megaind_io"]["rules"] = rules

    # === System ===
    # Note: hw_mode is no longer configurable - system always uses real hardware
    cfg.setdefault("i2c", {})
    cfg["i2c"]["bus"] = parse_int("i2c_bus", 1)
    cfg["ui"]["maintenance_enabled"] = parse_bool("maintenance_enabled", False)

    # Save config
    repo.save_config(cfg)
    repo.log_event(
        level="INFO",
        code="SETTINGS_SAVED",
        message="Settings saved from settings page.",
        details={},
    )

    return redirect(url_for("routes.settings_get"))


@bp.get("/export/events.json")
def export_events_json() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    events = repo.get_recent_events(limit=5000)
    return Response(json.dumps(events, indent=2), mimetype="application/json")


# ============================================================================
# API Endpoints
# ============================================================================

SNAPSHOT_SCHEMA_VERSION = 1


@bp.post("/api/zero")
def api_zero() -> Response:
    """Zero the scale - updates the calibration baseline to current signal = 0 lbs.
    
    This is different from tare:
    - ZERO: Adjusts the calibration baseline (signal offset) - fixes drift
    - TARE: Subtracts a weight offset (for containers, etc.)
    
    How it works:
    - Find the calibration zero point (what signal value = 0 lbs in calibration)
    - Calculate drift = current_raw_signal - calibration_zero_signal
    - Set zero_offset = drift
    - After applying: calibrated_signal = raw - drift = calibration_zero = 0 lbs
    """
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    snap = state.snapshot()

    if not snap.get("stable", False):
        repo.log_event(
            level="WARNING",
            code="ZERO_REJECTED_UNSTABLE",
            message="Zero rejected: scale not stable.",
            details={},
        )
        return Response(
            json.dumps({"success": False, "error": "Scale not stable"}),
            mimetype="application/json",
            status=400,
        )

    cfg = repo.get_latest_config()
    scale = cfg.get("scale") or {}
    
    # Use the same live signal path shown in UI/calibration endpoints.
    current_signal = float(
        snap.get("signal_for_cal", snap.get("total_signal", snap.get("raw_signal_mv", 0.0))) or 0.0
    )
    old_offset = scale.get("zero_offset_signal")
    if old_offset is None:
        old_offset = scale.get("zero_offset_mv", 0.0)
    old_offset = float(old_offset or 0.0)
    
    cal_points = repo.get_calibration_points(limit=200)

    current_gross_lbs = snap.get("filtered_weight_lbs")
    if current_gross_lbs is None:
        current_gross_lbs = float(snap.get("total_weight_lbs", 0.0) or 0.0) + float(
            snap.get("tare_offset_lbs", 0.0) or 0.0
        )
    current_gross_lbs = float(current_gross_lbs or 0.0)

    lbs_per_mv = snap.get("lbs_per_mv")
    if lbs_per_mv is None:
        lbs_per_mv = estimate_lbs_per_mv(cal_points)
    lbs_per_mv = float(lbs_per_mv or 0.0)

    if abs(lbs_per_mv) > 1e-9:
        correction_signal_mv = current_gross_lbs / lbs_per_mv
        new_offset = old_offset + correction_signal_mv
        cal_zero_signal = current_signal - new_offset
        drift = new_offset - old_offset
        zero_method = "weight_based"
    else:
        new_offset, cal_zero_signal = compute_zero_offset(current_signal, cal_points)
        drift = new_offset - old_offset
        zero_method = "cal_zero_fallback"
    updated_utc = _utc_now()
    scale["zero_offset_mv"] = new_offset
    scale["zero_offset_signal"] = new_offset
    scale["zero_offset_updated_utc"] = updated_utc
    
    cfg["scale"] = scale
    repo.save_config(cfg)
    state.set(
        zero_offset_mv=new_offset,
        zero_offset_signal=new_offset,
        zero_offset_updated_utc=updated_utc,
    )
    repo.log_event(
        level="INFO",
        code="SCALE_ZEROED",
        message=f"Scale zeroed: drift={drift:.6f}, offset updated from {old_offset:.6f} to {new_offset:.6f}",
        details={
            "old_zero_offset": old_offset,
            "new_zero_offset": new_offset,
            "current_signal": current_signal,
            "current_gross_lbs": current_gross_lbs,
            "lbs_per_mv": lbs_per_mv,
            "method": zero_method,
            "calibration_zero_signal": cal_zero_signal,
            "drift": drift,
        },
    )

    return Response(
        json.dumps({
            "success": True,
            "zero_offset_mv": new_offset,
            "zero_offset_signal": new_offset,
            "drift": drift,
            "method": zero_method,
            "current_gross_lbs": current_gross_lbs,
            "lbs_per_mv": lbs_per_mv,
            "message": "Calibration baseline updated"
        }),
        mimetype="application/json",
    )


@bp.post("/api/tare")
def api_tare() -> Response:
    """Tare the scale - set current weight as tare offset."""
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    snap = state.snapshot()

    if not snap.get("stable", False):
        repo.log_event(
            level="WARNING",
            code="TARE_REJECTED_UNSTABLE",
            message="Tare rejected: scale not stable.",
            details={},
        )
        return Response(
            json.dumps({"success": False, "error": "Scale not stable"}),
            mimetype="application/json",
            status=400,
        )

    cfg = repo.get_latest_config()
    scale = cfg.get("scale") or {}
    current_weight = float(snap.get("total_weight_lbs", 0.0) or 0.0)
    current_tare = float(scale.get("tare_offset_lbs", 0.0) or 0.0)
    
    # Add current displayed weight to tare
    scale["tare_offset_lbs"] = current_weight + current_tare
    cfg["scale"] = scale
    repo.save_config(cfg)
    repo.log_event(
        level="INFO",
        code="SCALE_TARED",
        message=f"Scale tared at {current_weight:.2f} lb.",
        details={"weight": current_weight, "new_tare": scale["tare_offset_lbs"]},
    )

    return Response(
        json.dumps({"success": True, "tare_offset_lbs": scale["tare_offset_lbs"]}),
        mimetype="application/json",
    )


@bp.post("/api/tare/clear")
def api_tare_clear() -> Response:
    """Clear tare offset - show gross weight."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    scale = cfg.get("scale") or {}
    old_tare = float(scale.get("tare_offset_lbs", 0.0) or 0.0)
    scale["tare_offset_lbs"] = 0.0
    cfg["scale"] = scale
    repo.save_config(cfg)
    repo.log_event(
        level="INFO",
        code="TARE_CLEARED",
        message=f"Tare cleared (was {old_tare:.2f} lb).",
        details={"old_tare": old_tare},
    )

    return Response(
        json.dumps({"success": True, "tare_offset_lbs": 0.0}),
        mimetype="application/json",
    )


@bp.post("/api/calibration/add")
def api_calibration_add() -> Response:
    """Add a calibration point via API."""
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    snap = state.snapshot()

    known_weight = float(request.form.get("known_weight_lbs", "0") or 0)
    
    if not snap.get("stable", False):
        repo.log_event(
            level="WARNING",
            code="CAL_POINT_REJECTED_UNSTABLE",
            message="Calibration point rejected: scale not stable.",
            details={"known_weight_lbs": known_weight},
        )
        return Response(
            json.dumps({"success": False, "error": "Scale not stable"}),
            mimetype="application/json",
            status=400,
        )

    signal = snap.get("signal_for_cal", 0.0)
    
    repo.add_calibration_point(
        known_weight_lbs=known_weight,
        signal=signal,
    )
    repo.log_event(
        level="INFO",
        code="CAL_POINT_ADDED",
        message=f"Calibration point added: {known_weight:.2f} lb at signal {signal:.6f}",
        details={"known_weight_lbs": known_weight, "signal": signal},
    )

    return Response(
        json.dumps({"success": True, "known_weight_lbs": known_weight, "signal": signal}),
        mimetype="application/json",
    )


@bp.post("/api/calibration/delete/<int:point_id>")
def api_calibration_delete(point_id: int) -> Response:
    """Delete a calibration point."""
    repo: AppRepository = current_app.config["REPO"]
    try:
        repo.delete_calibration_point(point_id)
        repo.log_event(
            level="INFO",
            code="CAL_POINT_DELETED",
            message=f"Calibration point {point_id} deleted.",
            details={"point_id": point_id},
        )
        return Response(
            json.dumps({"success": True}),
            mimetype="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"success": False, "error": str(e)}),
            mimetype="application/json",
            status=400,
        )


@bp.post("/api/calibration/clear")
def api_calibration_clear() -> Response:
    """Delete all calibration points."""
    repo: AppRepository = current_app.config["REPO"]
    try:
        repo.clear_calibration_points()
        repo.log_event(
            level="INFO",
            code="CAL_POINTS_CLEARED",
            message="All calibration points cleared.",
            details={},
        )
        return Response(
            json.dumps({"success": True}),
            mimetype="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"success": False, "error": str(e)}),
            mimetype="application/json",
            status=400,
        )


# ============================================================================
# PLC Output API Endpoints
# ============================================================================

@bp.post("/api/output/arm")
def api_output_arm() -> Response:
    """ARM or DISARM the analog outputs."""
    repo: AppRepository = current_app.config["REPO"]
    data = request.get_json() or {}
    armed = bool(data.get("armed", False))
    
    cfg = repo.get_latest_config()
    output = cfg.get("output") or {}
    old_armed = output.get("armed", False)
    output["armed"] = armed
    cfg["output"] = output
    repo.save_config(cfg)
    
    repo.log_event(
        level="WARNING" if armed else "INFO",
        code="OUTPUT_ARMED" if armed else "OUTPUT_DISARMED",
        message=f"Analog outputs {'ARMED' if armed else 'DISARMED'}.",
        details={"old_state": old_armed, "new_state": armed},
    )
    
    return Response(
        json.dumps({"success": True, "armed": armed}),
        mimetype="application/json",
    )


@bp.post("/api/output/config")
def api_output_config() -> Response:
    """Save output configuration."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    output = cfg.get("output") or {}
    range_cfg = cfg.get("range") or {}
    
    # Update output config
    output["mode"] = request.form.get("output_mode", output.get("mode", "0_10V"))
    channel = int(request.form.get("output_channel", "1") or 1)
    output["ao_channel_v"] = channel
    output["ao_channel_ma"] = channel
    
    safe_output = float(request.form.get("safe_output", "0") or 0)
    if output["mode"] == "4_20mA":
        output["safe_ma"] = safe_output
    else:
        output["safe_v"] = safe_output
    
    # Update range config
    range_cfg["min_lb"] = float(request.form.get("min_lb", "0") or 0)
    range_cfg["max_lb"] = float(request.form.get("max_lb", "300") or 300)
    
    cfg["output"] = output
    cfg["range"] = range_cfg
    repo.save_config(cfg)
    
    repo.log_event(
        level="INFO",
        code="OUTPUT_CONFIG_SAVED",
        message="Output configuration saved.",
        details={"mode": output["mode"], "channel": channel, "range": range_cfg},
    )
    
    return Response(
        json.dumps({"success": True}),
        mimetype="application/json",
    )


@bp.post("/api/output/test")
def api_output_test() -> Response:
    """Toggle test output mode - stays on until toggled off."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    output = cfg.get("output") or {}
    
    if not output.get("armed", False):
        return Response(
            json.dumps({"success": False, "error": "Outputs not armed"}),
            mimetype="application/json",
            status=400,
        )
    
    data = request.get_json() or {}
    action = data.get("action", "toggle")  # "start", "stop", or "toggle"
    value = float(data.get("value", 0))
    
    # Check current test mode state
    currently_testing = output.get("test_mode", False)
    
    if action == "start":
        new_state = True
    elif action == "stop":
        new_state = False
    else:  # toggle
        new_state = not currently_testing
    
    # Update config with test mode state
    output["test_mode"] = new_state
    if new_state:
        output["test_value"] = value
    cfg["output"] = output
    repo.save_config(cfg)
    
    mode = output.get("mode", "0_10V")
    
    if new_state:
        # Starting test mode - write the value now
        svc = current_app.config.get("ACQ_SERVICE")
        hw = getattr(svc, "hw", None) if svc is not None else None
        
        if hw is not None:
            try:
                if mode == "4_20mA":
                    channel = int(output.get("ao_channel_ma", 1))
                    value = max(4.0, min(20.0, value))
                    hw.megaind.write_analog_out_ma(channel, value)
                    units = "mA"
                else:
                    channel = int(output.get("ao_channel_v", 1))
                    value = max(0.0, min(10.0, value))
                    hw.megaind.write_analog_out_v(channel, value)
                    units = "V"
                
                repo.log_event(
                    level="WARNING",
                    code="OUTPUT_TEST_START",
                    message=f"Test output STARTED: {value:.3f} {units} on channel {channel}",
                    details={"value": value, "mode": mode, "channel": channel},
                )
            except Exception as e:
                repo.log_event(
                    level="ERROR",
                    code="OUTPUT_TEST_FAILED",
                    message=f"Test output failed: {e}",
                    details={"value": value, "mode": mode, "error": str(e)},
                )
                return Response(
                    json.dumps({"success": False, "error": str(e)}),
                    mimetype="application/json",
                    status=500,
                )
    else:
        # Stopping test mode
        repo.log_event(
            level="INFO",
            code="OUTPUT_TEST_STOP",
            message="Test output STOPPED - returning to weight-based output.",
            details={},
        )
    
    return Response(
        json.dumps({"success": True, "test_mode": new_state, "value": value}),
        mimetype="application/json",
    )


@bp.post("/api/output/nudge")
def api_output_nudge() -> Response:
    """Nudge the analog output value during calibration."""
    repo: AppRepository = current_app.config["REPO"]
    data = request.get_json() or {}
    
    value = float(data.get("value", 0.0))
    active = bool(data.get("active", True))
    mode = data.get("mode")
    channel = data.get("channel")
    
    cfg = repo.get_latest_config()
    output = cfg.get("output") or {}
    output["calibration_active"] = active
    output["nudge_value"] = value
    
    if mode:
        output["mode"] = mode
    if channel:
        ch_int = int(channel)
        output["ao_channel_v"] = ch_int
        output["ao_channel_ma"] = ch_int
        
    cfg["output"] = output
    repo.save_config(cfg)
    
    return Response(
        json.dumps({"success": True, "value": value, "active": active}),
        mimetype="application/json",
    )


@bp.get("/api/io/conflicts")
def api_io_conflicts() -> Response:
    """Check for I/O channel conflicts."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    
    out = cfg.get("output", {})
    mode = out.get("mode", "0_10V")
    plc_ch = int(out.get("ao_channel_ma", 1) if mode == "4_20mA" else out.get("ao_channel_v", 1))
    
    mio = cfg.get("megaind_io", {})
    rules = mio.get("rules", [])
    ao_v = mio.get("ao_v", [])
    
    conflicts = []
    
    # Check Manual AO vs PLC
    for i, item in enumerate(ao_v):
        ch = i + 1
        if bool(item.get("enabled", False)) and ch == plc_ch and mode == "0_10V":
            conflicts.append({
                "pin": f"AO{ch}",
                "reason": "Used by both PLC Weight and Manual Extra Output"
            })
            
    # Check Rules vs PLC
    for i, rule in enumerate(rules):
        if not bool(rule.get("enabled", False)):
            continue
        out_ch = int(rule.get("output_ch", 1))
        if out_ch == plc_ch and mode == "0_10V":
            conflicts.append({
                "pin": f"AO{out_ch}",
                "reason": f"Used by both PLC Weight and Logic Rule #{i+1}"
            })
            
    return Response(
        json.dumps({"success": True, "conflicts": conflicts}),
        mimetype="application/json"
    )


@bp.post("/api/output/calibrate")
def api_output_calibrate() -> Response:
    """Capture a calibration point for analog output.
    
    Calls the megaind CLI to perform two-point calibration.
    Calibration types:
    - uoutcal: 0-10V output calibration
    - ioutcal: 4-20mA output calibration
    """
    import platform
    import subprocess
    
    repo: AppRepository = current_app.config["REPO"]
    data = request.get_json() or {}
    
    cal_type = data.get("type", "uoutcal")
    channel = int(data.get("channel", 1))
    value = float(data.get("value", 0))
    point = int(data.get("point", 1))
    
    # Get MegaIND stack level from config
    cfg = repo.get_latest_config()
    megaind_cfg = cfg.get("megaind") or {}
    stack_level = int(megaind_cfg.get("stack_level", 0))
    
    # Only run CLI on Linux
    if platform.system().lower() != "linux":
        repo.log_event(
            level="WARNING",
            code="OUTPUT_CAL_SKIPPED",
            message=f"MegaIND calibration requires Linux. Point {point} logged but not applied.",
            details={"type": cal_type, "channel": channel, "value": value, "point": point},
        )
        return Response(
            json.dumps({"success": True, "point": point, "warning": "CLI not available on this platform"}),
            mimetype="application/json",
        )
    
    # Call megaind CLI
    try:
        cmd = ["megaind", str(stack_level), cal_type, str(channel), str(value)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10.0,
            check=True,
        )
        repo.log_event(
            level="INFO",
            code="OUTPUT_CAL_POINT",
            message=f"Calibration point {point} captured: {cal_type} ch{channel} = {value}",
            details={
                "type": cal_type,
                "channel": channel,
                "value": value,
                "point": point,
                "stdout": result.stdout,
            },
        )
        return Response(
            json.dumps({"success": True, "point": point}),
            mimetype="application/json",
        )
    except subprocess.CalledProcessError as e:
        repo.log_event(
            level="ERROR",
            code="OUTPUT_CAL_FAILED",
            message=f"Calibration failed: {e.stderr or e}",
            details={"type": cal_type, "channel": channel, "value": value, "error": str(e)},
        )
        return Response(
            json.dumps({"success": False, "error": e.stderr or str(e)}),
            mimetype="application/json",
            status=500,
        )
    except FileNotFoundError:
        repo.log_event(
            level="ERROR",
            code="OUTPUT_CAL_CLI_MISSING",
            message="megaind CLI not found. Install Sequent megaind-rpi package.",
            details={"type": cal_type, "channel": channel},
        )
        return Response(
            json.dumps({"success": False, "error": "megaind CLI not installed"}),
            mimetype="application/json",
            status=500,
        )
    except Exception as e:
        repo.log_event(
            level="ERROR",
            code="OUTPUT_CAL_ERROR",
            message=f"Calibration error: {e}",
            details={"type": cal_type, "channel": channel, "error": str(e)},
        )
        return Response(
            json.dumps({"success": False, "error": str(e)}),
            mimetype="application/json",
            status=500,
        )


@bp.post("/api/output/calibrate/reset")
def api_output_calibrate_reset() -> Response:
    """Reset output calibration to factory.
    
    Calls the megaind CLI to reset calibration.
    Reset types:
    - uoutcalrst: 0-10V output calibration reset
    - ioutcalrst: 4-20mA output calibration reset
    """
    import platform
    import subprocess
    
    repo: AppRepository = current_app.config["REPO"]
    data = request.get_json() or {}
    
    cal_type = data.get("type", "uoutcalrst")
    channel = int(data.get("channel", 1))
    
    # Get MegaIND stack level from config
    cfg = repo.get_latest_config()
    megaind_cfg = cfg.get("megaind") or {}
    stack_level = int(megaind_cfg.get("stack_level", 0))
    
    # Only run CLI on Linux
    if platform.system().lower() != "linux":
        repo.log_event(
            level="WARNING",
            code="OUTPUT_CAL_RESET_SKIPPED",
            message=f"MegaIND calibration reset requires Linux. Logged but not applied.",
            details={"type": cal_type, "channel": channel},
        )
        return Response(
            json.dumps({"success": True, "warning": "CLI not available on this platform"}),
            mimetype="application/json",
        )
    
    # Call megaind CLI
    try:
        cmd = ["megaind", str(stack_level), cal_type, str(channel)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10.0,
            check=True,
        )
        repo.log_event(
            level="INFO",
            code="OUTPUT_CAL_RESET",
            message=f"Calibration reset: {cal_type} ch{channel}",
            details={
                "type": cal_type,
                "channel": channel,
                "stdout": result.stdout,
            },
        )
        return Response(
            json.dumps({"success": True}),
            mimetype="application/json",
        )
    except subprocess.CalledProcessError as e:
        repo.log_event(
            level="ERROR",
            code="OUTPUT_CAL_RESET_FAILED",
            message=f"Calibration reset failed: {e.stderr or e}",
            details={"type": cal_type, "channel": channel, "error": str(e)},
        )
        return Response(
            json.dumps({"success": False, "error": e.stderr or str(e)}),
            mimetype="application/json",
            status=500,
        )
    except FileNotFoundError:
        repo.log_event(
            level="ERROR",
            code="OUTPUT_CAL_CLI_MISSING",
            message="megaind CLI not found. Install Sequent megaind-rpi package.",
            details={"type": cal_type, "channel": channel},
        )
        return Response(
            json.dumps({"success": False, "error": "megaind CLI not installed"}),
            mimetype="application/json",
            status=500,
        )
    except Exception as e:
        repo.log_event(
            level="ERROR",
            code="OUTPUT_CAL_RESET_ERROR",
            message=f"Calibration reset error: {e}",
            details={"type": cal_type, "channel": channel, "error": str(e)},
        )
        return Response(
            json.dumps({"success": False, "error": str(e)}),
            mimetype="application/json",
            status=500,
        )


@bp.post("/api/plc-profile/delete/<int:point_id>")
def api_plc_profile_delete(point_id: int) -> Response:
    """Delete a PLC profile point."""
    repo: AppRepository = current_app.config["REPO"]
    try:
        repo.delete_plc_profile_point(point_id)
        repo.log_event(
            level="INFO",
            code="PLC_PROFILE_POINT_DELETED",
            message=f"PLC profile point {point_id} deleted.",
            details={"point_id": point_id},
        )
        return Response(
            json.dumps({"success": True}),
            mimetype="application/json",
        )
    except Exception as e:
        return Response(
            json.dumps({"success": False, "error": str(e)}),
            mimetype="application/json",
            status=400,
        )


@bp.post("/api/output/maintenance")
def api_output_maintenance() -> Response:
    """Update maintenance settings from the Hub."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    output = cfg.get("output") or {}
    
    ramp_rate = float(request.form.get("ramp_rate", "5.0") or 5.0)
    ramp_enabled = request.form.get("ramp_enabled") == "on"
    safe_val = float(request.form.get("safe_output", "0.0") or 0.0)
    mode = output.get("mode", "0_10V")
    
    output["ramp_enabled"] = ramp_enabled
    if mode == "4_20mA":
        output["ramp_rate_ma"] = ramp_rate
        output["safe_ma"] = safe_val
    else:
        output["ramp_rate_v"] = ramp_rate
        output["safe_v"] = safe_val
        
    cfg["output"] = output
    repo.save_config(cfg)
    
    repo.log_event(
        level="INFO",
        code="MAINTENANCE_SAVED",
        message="Maintenance tools settings updated.",
        details={"ramp_enabled": ramp_enabled, "ramp_rate": ramp_rate, "safe_val": safe_val}
    )
    
    return Response(json.dumps({"success": True}), mimetype="application/json")


@bp.get("/api/snapshot")
def api_snapshot() -> Response:
    """Return a unified JSON snapshot for dashboard polling.

    Schema:
    {
        "schema_version": 1,
        "timestamp": "...",
        "system": { ... },
        "boards": { ... },
        "excitation": { ... },
        "weight": { ... },
        "channels": [ ... ],
        "plcOutput": { ... },
        "events": [ ... ]
    }
    """
    state: LiveState = current_app.config["LIVE_STATE"]
    repo: AppRepository = current_app.config["REPO"]
    snap = state.snapshot()

    # Get production data
    production_totals = repo.get_production_totals(["day", "week", "month"])
    dump_count_today = repo.get_dump_count("day")
    last_dump = repo.get_last_dump()
    latest_cfg = repo.get_latest_config()
    out_cfg = latest_cfg.get("output", {}) if isinstance(latest_cfg, dict) else {}
    scale_cfg = latest_cfg.get("scale", {}) if isinstance(latest_cfg, dict) else {}
    zero_tracking_cfg = latest_cfg.get("zero_tracking", {}) if isinstance(latest_cfg, dict) else {}

    zero_offset_mv = float(
        snap.get(
            "zero_offset_mv",
            snap.get(
                "zero_offset_signal",
                scale_cfg.get("zero_offset_mv", scale_cfg.get("zero_offset_signal", 0.0)),
            ),
        )
        or 0.0
    )
    lbs_per_mv = float(snap.get("lbs_per_mv") or 0.0)
    zero_offset_lbs = zero_offset_mv * lbs_per_mv if abs(lbs_per_mv) > 1e-9 else 0.0
    zero_offset_updated_utc = snap.get("zero_offset_updated_utc") or scale_cfg.get("zero_offset_updated_utc")

    zero_tracking_enabled = bool(
        snap.get("zero_tracking_enabled", zero_tracking_cfg.get("enabled", False))
    )
    zero_tracking_active = bool(snap.get("zero_tracking_active", False))
    zero_tracking_locked = bool(snap.get("zero_tracking_locked", (not zero_tracking_active)))
    if not zero_tracking_enabled:
        zero_tracking_locked = True
    zero_tracking_reason = snap.get("zero_tracking_reason")
    if not zero_tracking_reason:
        if not zero_tracking_enabled:
            zero_tracking_reason = "disabled"
        elif zero_tracking_active:
            zero_tracking_reason = "tracking"
        else:
            zero_tracking_reason = "locked"

    # Build structured response
    result = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "timestamp": _utc_now(),
        "system": {
            "io_live": bool(snap.get("io_live", False)),
            "daq_online": bool(snap.get("daq_online", False)),
            "megaind_online": bool(snap.get("megaind_online", False)),
            "loop_hz": float(snap.get("loop_hz") or 0.0),
            "last_update_utc": snap.get("last_update_utc"),
            "fault": bool(snap.get("fault", False)),
            "fault_reason": snap.get("fault_reason"),
            "stable": bool(snap.get("stable", False)),
            "i2c_bus": snap.get("i2c_bus"),
        },
        "boards": {
            "io_live": bool(snap.get("io_live", False)),
            "daq_online": bool(snap.get("daq_online", False)),
            "megaind_online": bool(snap.get("megaind_online", False)),
            "daq_error": snap.get("daq_error"),
            "megaind_error": snap.get("megaind_error"),
            "online_count": int(snap.get("boards_online_count") or 0),
            "expected_count": int(snap.get("boards_expected_count") or 2),
            "online": snap.get("boards_online") or {},
            "expected": snap.get("boards_expected") or {},
            "detected": snap.get("boards_detected") or [],
            "last_daq_comm_utc": snap.get("last_daq_comm_utc"),
            "last_megaind_comm_utc": snap.get("last_megaind_comm_utc"),
        },
        "megaindIO": {
            "ai_v": snap.get("megaind_ai_v") or {},
            "di": snap.get("megaind_di") or {},
            "ao_v_cmd": snap.get("megaind_ao_v_cmd") or {},
        },
        "excitation": {
            "voltage_v": float(snap.get("excitation_v") or 0.0),
            "status": snap.get("excitation_status", "UNKNOWN"),
            "ratiometric": False,  # Always raw mV now
        },
        "weight": {
            "total_lbs": float(snap.get("total_weight_lbs") or 0.0),
            "raw_lbs": float(snap.get("raw_weight_lbs") or 0.0),
            "stable": bool(snap.get("stable", False)),
            "tare_offset_lbs": float(snap.get("tare_offset_lbs") or 0.0),
            "zero_offset_signal": zero_offset_mv,
            "zero_offset_mv": zero_offset_mv,
            "zero_offset_lbs": float(zero_offset_lbs),
            "zero_offset_updated_utc": zero_offset_updated_utc,
            "zero_tracking_enabled": zero_tracking_enabled,
            "zero_tracking_active": zero_tracking_active,
            "zero_tracking_locked": zero_tracking_locked,
            "zero_tracking_reason": str(zero_tracking_reason),
            "zero_tracking_hold_elapsed_s": float(snap.get("zero_tracking_hold_elapsed_s") or 0.0),
            "raw_signal_mv": float(
                snap.get("total_signal", snap.get("raw_signal_mv", snap.get("signal_for_cal", 0.0))) or 0.0
            ),
            "signal_for_cal": float(snap.get("signal_for_cal") or 0.0),
            "cal_points_used": int(snap.get("cal_points_used") or 0),
        },
        "channels": _build_channels_list(snap),
        "plcOutput": {
            "mode": snap.get("output_mode", "0_10V"),
            "command": float(snap.get("output_command") or 0.0),
            "units": snap.get("output_units", "V"),
            "armed": bool(snap.get("output_armed", out_cfg.get("armed", False))),
            "test_mode": bool(out_cfg.get("test_mode", False)),
            "test_value": float(out_cfg.get("test_value", 0)),
            "calibration_active": bool(out_cfg.get("calibration_active", False)),
            "nudge_value": float(out_cfg.get("nudge_value", 0.0)),
        },
        "production": {
            "totals": production_totals,
            "dump_count_today": dump_count_today,
            "last_dump": last_dump,
            "avg_dump_lbs": (
                production_totals.get("day", 0.0) / dump_count_today
                if dump_count_today > 0 else 0.0
            ),
        },
        "events": repo.get_recent_events(limit=5),
    }

    return Response(
        json.dumps(result),
        mimetype="application/json",
        headers={"Cache-Control": "no-cache"},
    )


def _build_channels_list(snap: dict) -> list:
    """Build channels list with status indicators."""
    channels = snap.get("channels") or []
    result = []
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        # Determine status based on channel state
        enabled = ch.get("enabled", False)
        polled = ch.get("polled", False)

        if not enabled:
            status = "Disabled"
        elif not polled:
            status = "Not polled"
        else:
            # Could check for drift/fault here if available
            raw_mv = float(ch.get("raw_mV") or 0.0)
            if abs(raw_mv) > 20000:  # Clipping/saturation check
                status = "FAULT"
            else:
                status = "OK"

        result.append({
            "ch": ch.get("ch"),
            "enabled": enabled,
            "polled": polled,
            "raw_mV": float(ch.get("raw_mV") or 0.0),
            "filtered": float(ch.get("filtered") or 0.0),
            "ratio": float(ch.get("ratio") or 0.0),
            "status": status,
        })
    return result


