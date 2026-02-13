from __future__ import annotations

import json
import platform
import subprocess
import csv
import io
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, Response, current_app, redirect, render_template, request, url_for

from src.core.zeroing import (
    calibration_model_from_points,
    compute_zero_offset,
    estimate_lbs_per_mv,
    select_active_calibration_points,
)
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


def _site_timezone(repo: AppRepository) -> tuple[Any, str]:
    cfg = repo.get_latest_config()
    ui_cfg = cfg.get("ui") if isinstance(cfg, dict) else {}
    tz_name = str((ui_cfg or {}).get("timezone", "UTC") or "UTC").strip() or "UTC"
    try:
        return ZoneInfo(tz_name), tz_name
    except ZoneInfoNotFoundError:
        return timezone.utc, "UTC"


def _parse_iso_or_date(value: str, default_tz: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            d = date.fromisoformat(raw)
            return datetime(d.year, d.month, d.day, tzinfo=default_tz)
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=default_tz)
        return dt
    except ValueError:
        return None


def _to_utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _bucket_start_local(ts_local: datetime, bucket: str) -> datetime:
    if bucket == "daily":
        return datetime(ts_local.year, ts_local.month, ts_local.day, tzinfo=ts_local.tzinfo)
    if bucket == "weekly":
        start_date = ts_local.date() - timedelta(days=ts_local.weekday())
        return datetime(start_date.year, start_date.month, start_date.day, tzinfo=ts_local.tzinfo)
    if bucket == "monthly":
        return datetime(ts_local.year, ts_local.month, 1, tzinfo=ts_local.tzinfo)
    if bucket == "yearly":
        return datetime(ts_local.year, 1, 1, tzinfo=ts_local.tzinfo)
    raise ValueError(f"Unsupported bucket: {bucket}")


def _parse_utc_range_from_query(
    *,
    start_raw: str,
    end_raw: str,
    default_tz: Any,
) -> tuple[Optional[str], Optional[str]]:
    start_dt = _parse_iso_or_date(start_raw, default_tz) if start_raw else None
    end_dt = _parse_iso_or_date(end_raw, default_tz) if end_raw else None
    if start_raw and start_dt is None:
        raise ValueError("Invalid start value. Use ISO-8601 datetime or YYYY-MM-DD.")
    if end_raw and end_dt is None:
        raise ValueError("Invalid end value. Use ISO-8601 datetime or YYYY-MM-DD.")
    if start_dt is not None and end_dt is not None and end_dt <= start_dt:
        raise ValueError("end must be after start.")
    return (
        _to_utc_iso(start_dt) if start_dt is not None else None,
        _to_utc_iso(end_dt) if end_dt is not None else None,
    )


def _run_shell_command(cmd: list[str], timeout_s: float = 8.0) -> tuple[bool, str]:
    """Run command and return success + combined output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except Exception as e:  # noqa: BLE001
        return False, str(e)

    out_parts = []
    if result.stdout and result.stdout.strip():
        out_parts.append(result.stdout.strip())
    if result.stderr and result.stderr.strip():
        out_parts.append(result.stderr.strip())
    output = "\n".join(out_parts)

    if result.returncode == 0:
        return True, output
    return False, output or f"exit_code={result.returncode}"


def _launch_hdmi_on_pi() -> tuple[bool, str]:
    """Start or restart kiosk fullscreen mode on local Raspberry Pi."""
    if platform.system().lower() != "linux":
        return False, "HDMI auto-launch only supported on Linux/Pi host."

    commands = [
        [
            "sudo",
            "-n",
            "-u",
            "pi",
            "env",
            "XDG_RUNTIME_DIR=/run/user/1000",
            "systemctl",
            "--user",
            "restart",
            "kiosk.service",
        ],
        [
            "sudo",
            "-n",
            "-u",
            "pi",
            "env",
            "XDG_RUNTIME_DIR=/run/user/1000",
            "systemctl",
            "--user",
            "start",
            "kiosk.service",
        ],
        [
            "sudo",
            "-n",
            "-u",
            "pi",
            "bash",
            "-lc",
            "export DISPLAY=:0; export KIOSK_URL=http://localhost:8080/hdmi; nohup /home/pi/kiosk.sh >/tmp/scale-hdmi-launch.log 2>&1 &",
        ],
    ]

    errors: list[str] = []
    for cmd in commands:
        ok, output = _run_shell_command(cmd, timeout_s=10.0)
        if ok:
            return True, output or "HDMI launch command sent."
        if output:
            errors.append(output)

    error_text = "; ".join(errors) if errors else "Unknown launch failure."
    return False, error_text[:1200]


def _force_relaunch_hdmi_on_pi() -> tuple[bool, str]:
    """Force-stop kiosk/chromium and relaunch HDMI mode."""
    if platform.system().lower() != "linux":
        return False, "HDMI force relaunch only supported on Linux/Pi host."

    primary_cmd = [
        "sudo",
        "-n",
        "-u",
        "pi",
        "bash",
        "-lc",
        (
            "export XDG_RUNTIME_DIR=/run/user/1000; "
            "export DISPLAY=:0; "
            "systemctl --user stop kiosk.service || true; "
            "pkill -f '/home/pi/kiosk.sh' || true; "
            "pkill -f '/usr/lib/chromium/chromium' || true; "
            "sleep 0.5; "
            "systemctl --user start kiosk.service; "
            "systemctl --user is-active kiosk.service"
        ),
    ]
    ok, output = _run_shell_command(primary_cmd, timeout_s=15.0)
    if ok:
        check_cmd = [
            "sudo",
            "-n",
            "-u",
            "pi",
            "bash",
            "-lc",
            (
                "export XDG_RUNTIME_DIR=/run/user/1000; "
                "if systemctl --user is-active kiosk.service >/dev/null 2>&1; then "
                "echo service_active; "
                "elif pgrep -f 'chromium.*localhost:8080/hdmi' >/dev/null 2>&1; then "
                "echo chromium_active; "
                "else "
                "exit 1; "
                "fi"
            ),
        ]
        ok_check, check_output = _run_shell_command(check_cmd, timeout_s=6.0)
        if ok_check:
            detail = "\n".join(x for x in [output, check_output] if x)
            return True, detail or "HDMI force relaunch complete."

    fallback_cmd = [
        "sudo",
        "-n",
        "-u",
        "pi",
        "bash",
        "-lc",
        (
            "export DISPLAY=:0; "
            "export KIOSK_URL=http://localhost:8080/hdmi; "
            "nohup /home/pi/kiosk.sh >/tmp/scale-hdmi-force-launch.log 2>&1 &"
        ),
    ]
    ok2, output2 = _run_shell_command(fallback_cmd, timeout_s=8.0)
    if ok2:
        verify_cmd = [
            "sudo",
            "-n",
            "-u",
            "pi",
            "bash",
            "-lc",
            "pgrep -f 'chromium.*localhost:8080/hdmi' >/dev/null 2>&1 && echo chromium_active",
        ]
        ok_verify, verify_output = _run_shell_command(verify_cmd, timeout_s=6.0)
        if ok_verify:
            detail = "\n".join(x for x in [output2, verify_output] if x)
            return True, detail or "HDMI fallback launch command sent."

    combined = "; ".join(x for x in [output, output2] if x)
    return False, (combined or "Unknown force relaunch failure.")[:1200]


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


@bp.get("/hdmi")
def hdmi() -> str:
    """HDMI-optimized operator page (800x480) for kiosk launch."""
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    snap = state.snapshot()
    cfg = repo.get_latest_config()
    display = cfg.get("display", {}) or {}
    ui = cfg.get("ui", {}) or {}
    poll_rate_ms = int(ui.get("poll_rate_ms", 500) or 500)
    poll_rate_ms = max(100, min(5000, poll_rate_ms))
    return render_template("hdmi.html", snap=snap, display=display, poll_rate_ms=poll_rate_ms)


@bp.get("/kiosk")
def kiosk() -> str:
    """Touch-optimized kiosk page for on-site display (e.g. Elecrow 5\" 800x480)."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    return render_template("kiosk.html", config=cfg)


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


def _is_truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _active_point_for_weight(points: list, known_weight_lbs: float, eps_lb: float = 1e-6):
    target = float(known_weight_lbs)
    for point in select_active_calibration_points(points):
        if abs(float(point.known_weight_lbs) - target) <= float(eps_lb):
            return point
    return None


def _reset_zero_offset(repo: AppRepository, state: Optional[LiveState], reason: str) -> None:
    """Reset zero offset to 0 when calibration model changes.

    Calibration captures raw signal, so any existing zero offset computed
    against a previous calibration model would corrupt the new mapping.
    """
    cfg = repo.get_latest_config()
    scale = cfg.get("scale") or {}
    old_offset = float(scale.get("zero_offset_mv") or scale.get("zero_offset_signal") or 0.0)
    if abs(old_offset) < 1e-12:
        return  # Already zero, nothing to do.

    updated_utc = _utc_now()
    scale["zero_offset_mv"] = 0.0
    scale["zero_offset_signal"] = 0.0
    scale["zero_offset_updated_utc"] = updated_utc
    cfg["scale"] = scale
    repo.save_config(cfg)

    if state is not None:
        state.set(
            zero_offset_mv=0.0,
            zero_offset_signal=0.0,
            zero_offset_updated_utc=updated_utc,
        )

    repo.log_event(
        level="INFO",
        code="ZERO_OFFSET_RESET",
        message=f"Zero offset reset from {old_offset:.6f} mV to 0.0 ({reason}).",
        details={
            "old_zero_offset_mv": old_offset,
            "new_zero_offset_mv": 0.0,
            "reason": reason,
        },
    )


def _apply_calibration_capture(
    repo: AppRepository,
    snap: dict,
    known_weight_lbs: float,
    requested_mode: str,
    confirm_average: bool,
    state: Optional[LiveState] = None,
) -> dict:
    known_weight_lbs = float(known_weight_lbs)
    requested_mode = str(requested_mode or "overwrite").strip().lower()
    if requested_mode not in ("overwrite", "average"):
        requested_mode = "overwrite"

    captured_signal_mv = float(snap.get("signal_for_cal", 0.0) or 0.0)
    existing_points = repo.get_calibration_points(limit=500)
    previous_active_point = _active_point_for_weight(existing_points, known_weight_lbs)
    previous_active_signal_mv = (
        float(previous_active_point.signal) if previous_active_point is not None else None
    )

    applied_mode = "overwrite"
    applied_signal_mv = captured_signal_mv
    if requested_mode == "average" and confirm_average and previous_active_signal_mv is not None:
        # Average mode is opt-in and requires explicit operator confirmation.
        applied_mode = "average"
        applied_signal_mv = (previous_active_signal_mv + captured_signal_mv) / 2.0

    point_id = repo.add_calibration_point(known_weight_lbs=known_weight_lbs, signal=applied_signal_mv)
    updated_points = repo.get_calibration_points(limit=500)
    model = calibration_model_from_points(updated_points)

    # Calibration model changed — any existing zero offset was computed against
    # the old model and would corrupt weight readings with the new one.
    _reset_zero_offset(repo, state, reason="calibration_point_added")

    repo.log_event(
        level="INFO",
        code="CALIBRATION_APPLIED",
        message=(
            f"Calibration capture applied ({applied_mode}) at {known_weight_lbs:.2f} lb."
        ),
        details={
            "point_id": point_id,
            "known_weight_lbs": known_weight_lbs,
            "requested_mode": requested_mode,
            "applied_mode": applied_mode,
            "captured_signal_mv": captured_signal_mv,
            "applied_signal_mv": applied_signal_mv,
            "previous_active_signal_mv": previous_active_signal_mv,
            "calibration_method": model.method,
            "slope_lbs_per_mv": model.slope_lbs_per_mv,
            "intercept_lbs": model.intercept_lbs,
            "active_points_count": model.active_points_count,
            "total_points_count": model.total_points_count,
            "last_calibration_utc": model.last_calibration_utc,
            "stable": bool(snap.get("stable", False)),
            "zero_tracking_active": bool(snap.get("zero_tracking_active", False)),
        },
    )

    return {
        "success": True,
        "point_id": point_id,
        "known_weight_lbs": known_weight_lbs,
        "requested_mode": requested_mode,
        "applied_mode": applied_mode,
        "captured_signal_mv": captured_signal_mv,
        "signal": applied_signal_mv,  # Backward-compatible key.
        "applied_signal_mv": applied_signal_mv,
        "previous_active_signal_mv": previous_active_signal_mv,
        "replaced": previous_active_signal_mv is not None,
        "averaged": applied_mode == "average",
        "calibration_method": model.method,
        "slope_lbs_per_mv": model.slope_lbs_per_mv,
        "intercept_lbs": model.intercept_lbs,
        "active_points_count": model.active_points_count,
        "total_points_count": model.total_points_count,
        "last_calibration_utc": model.last_calibration_utc,
    }


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


def _fit_linear_range_from_profile(points: list, output_mode: str) -> tuple[float, float]:
    """Estimate linear range min/max from saved PLC profile points."""
    if len(points) < 2:
        raise ValueError("Need at least two profile points to fit range.")

    xs = [float(p.analog_value) for p in points]
    ys = [float(p.plc_displayed_lbs) for p in points]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)

    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom <= 1e-12:
        raise ValueError("Profile analog values do not span enough range.")

    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    intercept = y_mean - slope * x_mean

    if str(output_mode) == "4_20mA":
        min_lb = intercept + slope * 4.0
        max_lb = intercept + slope * 20.0
    else:
        min_lb = intercept + slope * 0.0
        max_lb = intercept + slope * 10.0

    if abs(max_lb - min_lb) <= 1e-9:
        raise ValueError("Fitted range collapsed; verify profile points.")
    if max_lb < min_lb:
        min_lb, max_lb = max_lb, min_lb
    return float(min_lb), float(max_lb)


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
        out["ao_channel"] = out["ao_channel_ma"] if out.get("mode") == "4_20mA" else out["ao_channel_v"]
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

    requested_mode = request.form.get("mode", "overwrite")
    confirm_average = _is_truthy(request.form.get("confirm_average"))
    _apply_calibration_capture(
        repo=repo,
        snap=snap,
        known_weight_lbs=known_weight,
        requested_mode=requested_mode,
        confirm_average=confirm_average,
        state=state,
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

    # Build channel rows for DAQ table -- read all 8 channels live from hardware
    daq_cfg = cfg.get("daq") or cfg.get("daq24b8vin") or {}
    active_channel = int(daq_cfg.get("channel", 7))
    active_gain = int(daq_cfg.get("gain_code", 6))
    enabled_channels = list(daq_cfg.get("enabled_channels") or [True] * 8)
    while len(enabled_channels) < 8:
        enabled_channels.append(True)
    enabled_channels = enabled_channels[:8]

    # Try to read live voltages from hardware
    svc = current_app.config.get("ACQ_SERVICE")
    hw = getattr(svc, "hw", None) if svc else None
    rows = []
    for i in range(8):
        raw_mv = 0.0
        gain = 0
        if hw is not None and enabled_channels[i]:
            try:
                raw_mv = float(hw.daq.read_differential_mv(i))
                gain = int(hw.daq.get_gain_code(i))
            except Exception:
                pass
        rows.append({
            "idx": i,
            "ch_display": i + 1,
            "enabled": bool(enabled_channels[i]),
            "active": (i == active_channel),
            "gain_code": gain if hw else active_gain,
            "raw_mv": raw_mv,
            "raw_v": raw_mv / 1000.0,
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
        raw = request.form.get(key)
        if raw is None:
            return bool(default)
        return str(raw).strip().lower() in ("1", "on", "true", "yes")

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
    channel = max(1, min(4, parse_int("output_channel", 1)))
    cfg["output"]["ao_channel_v"] = channel
    cfg["output"]["ao_channel_ma"] = channel
    cfg["output"]["ao_channel"] = channel
    safe = parse_float("safe_output", 0.0)
    if cfg["output"]["mode"] == "4_20mA":
        cfg["output"]["safe_ma"] = safe
    else:
        cfg["output"]["safe_v"] = safe

    cfg.setdefault("excitation", {})
    cfg["excitation"]["enabled"] = parse_bool("excitation_enabled", True)
    cfg["excitation"]["ai_channel"] = parse_int("excitation_ai_channel", 1)
    cfg["excitation"]["warn_v"] = parse_float("excitation_warn_v", 9.0)
    cfg["excitation"]["fault_v"] = parse_float("excitation_fault_v", 8.0)

    # === Signal Tuning ===
    cfg.setdefault("filter", {})
    cfg["filter"]["use_kalman"] = parse_bool("use_kalman", True)
    kalman_q = parse_float("kalman_process_noise", 1.0)
    kalman_r = parse_float("kalman_measurement_noise", 50.0)
    stability_std = parse_float("stability_stddev_lb", 0.8)
    stability_slope = parse_float("stability_slope_lbs", 0.8)
    cfg["filter"]["kalman_process_noise"] = kalman_q
    cfg["filter"]["kalman_measurement_noise"] = kalman_r
    # Legacy aliases retained so old runtime readers still work.
    cfg["filter"]["kalman_q"] = kalman_q
    cfg["filter"]["kalman_r"] = kalman_r
    cfg["filter"]["alpha"] = parse_float("filter_alpha", 0.18)
    cfg["filter"]["stability_window"] = parse_int("stability_window", 25)
    cfg["filter"]["stability_stddev_lb"] = stability_std
    cfg["filter"]["stability_slope_lbs"] = stability_slope
    cfg["filter"]["stability_threshold"] = stability_std
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

    # === DAQ Configuration ===
    cfg.setdefault("daq", {})
    cfg["daq"]["stack_level"] = parse_int("daq_stack_level", cfg.get("daq", {}).get("stack_level", 0))
    cfg["daq"]["average_samples"] = parse_int("daq_average_samples", 2)
    cfg["daq"]["sample_rate"] = parse_int("daq_sample_rate", 0)

    # Channel enable toggles
    enabled_channels = []
    for i in range(8):
        enabled_channels.append(parse_bool(f"ch_enabled_{i}", False))

    # Active channel radio / hidden field
    active_channel = parse_int("active_channel", 7)
    active_channel = max(0, min(7, active_channel))

    # Ensure active channel is enabled
    if not enabled_channels[active_channel]:
        enabled_channels[active_channel] = True

    cfg["daq"]["enabled_channels"] = enabled_channels
    cfg["daq"]["channel"] = active_channel
    cfg["daq"]["gain_code"] = parse_int("active_gain", 6)

    # === Opto Actions ===
    cfg.setdefault("opto_actions", {})
    for i in range(1, 5):
        action = request.form.get(f"opto_action_{i}", "none")
        cfg["opto_actions"][str(i)] = action

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
    cfg["ui"]["timezone"] = str(
        request.form.get("ui_timezone", cfg["ui"].get("timezone", "UTC")) or "UTC"
    ).strip() or "UTC"

    # === Logging ===
    cfg.setdefault("logging", {})
    cfg["logging"]["interval_s"] = parse_int("log_interval_s", 1)
    cfg["logging"]["retention_days"] = parse_int("log_retention_days", 30)
    cfg["logging"]["log_raw"] = parse_bool("log_raw", False)
    cfg["logging"]["log_weight"] = parse_bool("log_weight", True)
    cfg["logging"]["log_output"] = parse_bool("log_output", True)
    cfg["logging"]["event_only"] = parse_bool("log_event_only", False)

    # === Advanced (Watchdog removed) ===

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
# Throughput Endpoints
# ============================================================================


@bp.get("/throughput/events")
def throughput_events() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    site_tz, _site_tz_name = _site_timezone(repo)

    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    try:
        start_utc, end_utc = _parse_utc_range_from_query(
            start_raw=start_raw,
            end_raw=end_raw,
            default_tz=site_tz,
        )
    except ValueError as e:
        return Response(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status=400,
        )

    device_id_raw = (request.args.get("deviceId") or "").strip()
    device_id = device_id_raw if device_id_raw else None

    try:
        page = max(1, int(request.args.get("page", "1") or 1))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get("pageSize", "50") or 50)
    except ValueError:
        page_size = 50
    page_size = max(1, min(500, page_size))

    events, total = repo.get_throughput_events_page(
        start_utc=start_utc,
        end_utc=end_utc,
        device_id=device_id,
        page=page,
        page_size=page_size,
    )

    payload = {
        "events": [
            {
                "id": row["id"],
                "timestamp": row["timestamp_utc"],
                "processed_lbs": row["processed_lbs"],
                "full_lbs": row["full_lbs"],
                "empty_lbs": row["empty_lbs"],
                "duration_ms": row["duration_ms"],
                "confidence": row["confidence"],
                "device_id": row["device_id"],
                "hopper_id": row["hopper_id"],
            }
            for row in events
        ],
        "page": page,
        "pageSize": page_size,
        "total": total,
    }
    return Response(
        json.dumps(payload),
        mimetype="application/json",
        headers={"Cache-Control": "no-cache"},
    )


@bp.get("/throughput/summary")
def throughput_summary() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    site_tz, site_tz_name = _site_timezone(repo)

    bucket = (request.args.get("bucket") or "daily").strip().lower()
    if bucket not in {"daily", "weekly", "monthly", "yearly"}:
        return Response(
            json.dumps({"error": "bucket must be one of: daily, weekly, monthly, yearly"}),
            mimetype="application/json",
            status=400,
        )

    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    try:
        start_utc, end_utc = _parse_utc_range_from_query(
            start_raw=start_raw,
            end_raw=end_raw,
            default_tz=site_tz,
        )
    except ValueError as e:
        return Response(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status=400,
        )

    device_id_raw = (request.args.get("deviceId") or "").strip()
    device_id = device_id_raw if device_id_raw else None

    totals = repo.get_throughput_totals(
        start_utc=start_utc,
        end_utc=end_utc,
        device_id=device_id,
    )
    rows = repo.get_throughput_events_range(
        start_utc=start_utc,
        end_utc=end_utc,
        device_id=device_id,
        order_desc=False,
    )

    series_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        ts_utc = _parse_iso_or_date(str(row["timestamp_utc"]), timezone.utc)
        if ts_utc is None:
            continue
        ts_local = ts_utc.astimezone(site_tz)
        bucket_start_local = _bucket_start_local(ts_local, bucket)
        bucket_key = bucket_start_local.date().isoformat()
        if bucket_key not in series_map:
            series_map[bucket_key] = {
                "bucket_start": bucket_key,
                "processed_lbs": 0.0,
                "event_count": 0,
            }
        series_map[bucket_key]["processed_lbs"] += float(row["processed_lbs"])
        series_map[bucket_key]["event_count"] += 1

    series = [series_map[key] for key in sorted(series_map.keys())]
    event_count = int(totals.get("event_count", 0) or 0)
    total_processed = float(totals.get("total_processed_lbs", 0.0) or 0.0)
    avg_per_event = (total_processed / event_count) if event_count > 0 else 0.0

    payload = {
        "total_processed_lbs": total_processed,
        "event_count": event_count,
        "avg_per_event_lbs": avg_per_event,
        "series": series,
        "timezone": site_tz_name,
    }
    return Response(
        json.dumps(payload),
        mimetype="application/json",
        headers={"Cache-Control": "no-cache"},
    )


@bp.get("/throughput/events.csv")
def throughput_events_csv() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    site_tz, _site_tz_name = _site_timezone(repo)

    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()
    try:
        start_utc, end_utc = _parse_utc_range_from_query(
            start_raw=start_raw,
            end_raw=end_raw,
            default_tz=site_tz,
        )
    except ValueError as e:
        return Response(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status=400,
        )

    device_id_raw = (request.args.get("deviceId") or "").strip()
    device_id = device_id_raw if device_id_raw else None

    rows = repo.get_throughput_events_range(
        start_utc=start_utc,
        end_utc=end_utc,
        device_id=device_id,
        order_desc=True,
    )

    sio = io.StringIO()
    writer = csv.writer(sio)
    writer.writerow(
        [
            "id",
            "timestamp_utc",
            "processed_lbs",
            "full_lbs",
            "empty_lbs",
            "duration_ms",
            "confidence",
            "device_id",
            "hopper_id",
            "created_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["id"],
                row["timestamp_utc"],
                row["processed_lbs"],
                row["full_lbs"],
                row["empty_lbs"],
                row["duration_ms"],
                row["confidence"],
                row["device_id"],
                row["hopper_id"],
                row["created_at"],
            ]
        )

    filename = f"throughput_events_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        sio.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@bp.post("/throughput/events/delete/<int:event_id>")
def throughput_event_delete_single(event_id: int) -> Response:
    repo: AppRepository = current_app.config["REPO"]
    deleted = repo.delete_throughput_event(event_id)
    if not deleted:
        return Response(
            json.dumps({"success": False, "error": f"Event {event_id} not found"}),
            mimetype="application/json",
            status=404,
        )
    repo.log_event(
        level="WARNING",
        code="THROUGHPUT_EVENT_DELETED",
        message=f"Deleted throughput event id={event_id}.",
        details={"event_id": event_id},
    )
    return Response(
        json.dumps({"success": True, "deleted_id": event_id}),
        mimetype="application/json",
        headers={"Cache-Control": "no-cache"},
    )


@bp.post("/throughput/events/delete")
def throughput_events_delete() -> Response:
    repo: AppRepository = current_app.config["REPO"]
    site_tz, _site_tz_name = _site_timezone(repo)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    def _param(name: str) -> str:
        return str(payload.get(name, request.args.get(name, "")) or "").strip()

    start_raw = _param("start")
    end_raw = _param("end")
    device_id = _param("deviceId") or None
    delete_all = _is_truthy(payload.get("deleteAll", request.args.get("deleteAll")))
    confirm_all = _is_truthy(payload.get("confirmAll", request.args.get("confirmAll")))

    if delete_all and not confirm_all:
        return Response(
            json.dumps({"error": "confirmAll=true is required when deleteAll=true"}),
            mimetype="application/json",
            status=400,
        )

    if not delete_all and (not start_raw and not end_raw and not device_id):
        return Response(
            json.dumps({"error": "Provide start/end/deviceId filters, or use deleteAll=true with confirmAll=true"}),
            mimetype="application/json",
            status=400,
        )

    if delete_all:
        start_utc = None
        end_utc = None
    else:
        try:
            start_utc, end_utc = _parse_utc_range_from_query(
                start_raw=start_raw,
                end_raw=end_raw,
                default_tz=site_tz,
            )
        except ValueError as e:
            return Response(
                json.dumps({"error": str(e)}),
                mimetype="application/json",
                status=400,
            )

    deleted = repo.delete_throughput_events(
        start_utc=start_utc,
        end_utc=end_utc,
        device_id=device_id,
    )
    repo.log_event(
        level="WARNING",
        code="THROUGHPUT_EVENTS_DELETED",
        message=f"Deleted {deleted} throughput event(s).",
        details={
            "deleted": deleted,
            "delete_all": delete_all,
            "start_utc": start_utc,
            "end_utc": end_utc,
            "device_id": device_id,
        },
    )
    return Response(
        json.dumps({"success": True, "deleted": deleted}),
        mimetype="application/json",
        headers={"Cache-Control": "no-cache"},
    )


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

    # Prefer weight-based zeroing so ZERO forces gross weight to 0 immediately.
    # This preserves calibration slope and only shifts baseline.
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
        # Fallback for uncalibrated startup scenarios.
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


@bp.post("/api/zero/clear")
def api_zero_clear() -> Response:
    """Clear (reset) the zero offset to 0.0 without re-zeroing.

    Useful when a stale offset from a previous calibration or testing session
    is contaminating the current weight readings.
    """
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    _reset_zero_offset(repo, state, reason="manual_clear")
    return Response(
        json.dumps({"success": True, "zero_offset_mv": 0.0, "message": "Zero offset cleared"}),
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

    requested_mode = request.form.get("mode", "overwrite")
    confirm_average = _is_truthy(request.form.get("confirm_average"))
    result = _apply_calibration_capture(
        repo=repo,
        snap=snap,
        known_weight_lbs=known_weight,
        requested_mode=requested_mode,
        confirm_average=confirm_average,
        state=state,
    )
    return Response(json.dumps(result), mimetype="application/json")


@bp.post("/api/calibration/delete/<int:point_id>")
def api_calibration_delete(point_id: int) -> Response:
    """Delete a calibration point."""
    repo: AppRepository = current_app.config["REPO"]
    state: LiveState = current_app.config["LIVE_STATE"]
    try:
        repo.delete_calibration_point(point_id)
        _reset_zero_offset(repo, state, reason="calibration_point_deleted")
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
    state: LiveState = current_app.config["LIVE_STATE"]
    try:
        repo.clear_calibration_points()
        _reset_zero_offset(repo, state, reason="calibration_points_cleared")
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


@bp.get("/api/calibration/history")
def api_calibration_history() -> Response:
    """Get recent calibration application history."""
    repo: AppRepository = current_app.config["REPO"]
    try:
        limit = int(request.args.get("limit", "50") or 50)
    except Exception:
        limit = 50
    limit = max(1, min(500, limit))
    history = repo.get_calibration_history(limit=limit)
    return Response(
        json.dumps({"success": True, "history": history}),
        mimetype="application/json",
        headers={"Cache-Control": "no-cache"},
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
    if not armed:
        # Disarm always exits special output modes.
        output["test_mode"] = False
        output["calibration_active"] = False
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
    channel = max(1, min(4, int(request.form.get("output_channel", "1") or 1)))
    output["ao_channel_v"] = channel
    output["ao_channel_ma"] = channel
    output["ao_channel"] = channel
    
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


@bp.post("/api/output/range/sync-profile")
def api_output_sync_range_from_profile() -> Response:
    """Fit linear min/max range from saved PLC profile points."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    output = cfg.get("output") or {}
    mode = str(output.get("mode", "0_10V"))
    points = repo.get_plc_profile_points(output_mode=mode, limit=500)

    if len(points) < 2:
        return Response(
            json.dumps({"success": False, "error": "Need at least 2 saved mapping points"}),
            mimetype="application/json",
            status=400,
        )

    try:
        fitted_min, fitted_max = _fit_linear_range_from_profile(points, mode)
    except ValueError as e:
        return Response(
            json.dumps({"success": False, "error": str(e)}),
            mimetype="application/json",
            status=400,
        )

    range_cfg = cfg.get("range") or {}
    old_min = float(range_cfg.get("min_lb", 0.0) or 0.0)
    old_max = float(range_cfg.get("max_lb", 300.0) or 300.0)
    range_cfg["min_lb"] = fitted_min
    range_cfg["max_lb"] = fitted_max
    cfg["range"] = range_cfg
    repo.save_config(cfg)

    repo.log_event(
        level="INFO",
        code="OUTPUT_RANGE_SYNCED_FROM_PROFILE",
        message="Range min/max synchronized from saved PLC profile points.",
        details={
            "mode": mode,
            "old_min_lb": old_min,
            "old_max_lb": old_max,
            "new_min_lb": fitted_min,
            "new_max_lb": fitted_max,
            "points_used": len(points),
        },
    )

    return Response(
        json.dumps(
            {
                "success": True,
                "mode": mode,
                "old_min_lb": old_min,
                "old_max_lb": old_max,
                "new_min_lb": fitted_min,
                "new_max_lb": fitted_max,
                "points_used": len(points),
            }
        ),
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
    mode = output.get("mode", "0_10V")
    if mode == "4_20mA":
        value = max(4.0, min(20.0, value))
    else:
        value = max(0.0, min(10.0, value))
    
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
        # Calibration nudge and test mode are mutually exclusive.
        output["calibration_active"] = False
    cfg["output"] = output
    repo.save_config(cfg)
    
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
    active_mode = str(mode or output.get("mode", "0_10V"))
    if active_mode == "4_20mA":
        value = max(4.0, min(20.0, value))
    else:
        value = max(0.0, min(10.0, value))
    output["calibration_active"] = active
    output["nudge_value"] = value
    if active:
        # Calibration nudge and test mode are mutually exclusive.
        output["test_mode"] = False
    
    if mode:
        output["mode"] = mode
    if channel:
        ch_int = max(1, min(4, int(channel)))
        output["ao_channel_v"] = ch_int
        output["ao_channel_ma"] = ch_int
        output["ao_channel"] = ch_int
        
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


@bp.post("/api/hdmi/launch")
def api_hdmi_launch() -> Response:
    """Start/restart kiosk fullscreen on local Pi HDMI display."""
    repo: AppRepository = current_app.config["REPO"]
    ok, details = _launch_hdmi_on_pi()

    if ok:
        repo.log_event(
            level="INFO",
            code="HDMI_LAUNCH_REQUESTED",
            message="Requested HDMI kiosk launch.",
            details={"result": details},
        )
        return Response(
            json.dumps({"success": True, "message": "HDMI launch sent to Pi display."}),
            mimetype="application/json",
        )

    repo.log_event(
        level="WARNING",
        code="HDMI_LAUNCH_FAILED",
        message="Failed to launch HDMI kiosk.",
        details={"error": details},
    )
    return Response(
        json.dumps(
            {
                "success": False,
                "error": "Could not auto-launch HDMI on this device.",
                "details": details,
            }
        ),
        mimetype="application/json",
        status=500,
    )


@bp.post("/api/hdmi/force-launch")
def api_hdmi_force_launch() -> Response:
    """Emergency action: force close kiosk/chromium, then relaunch HDMI."""
    repo: AppRepository = current_app.config["REPO"]
    ok, details = _force_relaunch_hdmi_on_pi()

    if ok:
        repo.log_event(
            level="WARNING",
            code="HDMI_FORCE_RELAUNCH",
            message="Forced HDMI kiosk relaunch requested.",
            details={"result": details},
        )
        return Response(
            json.dumps({"success": True, "message": "HDMI force relaunch sent."}),
            mimetype="application/json",
        )

    repo.log_event(
        level="ERROR",
        code="HDMI_FORCE_RELAUNCH_FAILED",
        message="Forced HDMI kiosk relaunch failed.",
        details={"error": details},
    )
    return Response(
        json.dumps(
            {
                "success": False,
                "error": "Could not force relaunch HDMI on this device.",
                "details": details,
            }
        ),
        mimetype="application/json",
        status=500,
    )


@bp.get("/api/daq/channels")
def api_daq_channels() -> Response:
    """Return live readings from all 8 DAQ channels. Used by settings page."""
    svc = current_app.config.get("ACQ_SERVICE")
    hw = getattr(svc, "hw", None) if svc else None
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    daq_cfg = cfg.get("daq") or cfg.get("daq24b8vin") or {}
    active_ch = int(daq_cfg.get("channel", 7))
    enabled_channels = list(daq_cfg.get("enabled_channels") or [True] * 8)
    while len(enabled_channels) < 8:
        enabled_channels.append(True)
    enabled_channels = enabled_channels[:8]

    channels = []
    for i in range(8):
        raw_mv = 0.0
        gain = 0
        if hw is not None and enabled_channels[i]:
            try:
                raw_mv = float(hw.daq.read_differential_mv(i))
                gain = int(hw.daq.get_gain_code(i))
            except Exception:
                pass
        channels.append({
            "ch": i,
            "ch_display": i + 1,
            "raw_mv": round(raw_mv, 4),
            "raw_v": round(raw_mv / 1000.0, 6),
            "gain_code": gain,
            "enabled": bool(enabled_channels[i]),
            "active": (i == active_ch),
        })

    return Response(
        json.dumps({"channels": channels, "active_channel": active_ch}),
        mimetype="application/json",
        headers={"Cache-Control": "no-cache"},
    )


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
    range_cfg = latest_cfg.get("range", {}) if isinstance(latest_cfg, dict) else {}
    scale_cfg = latest_cfg.get("scale", {}) if isinstance(latest_cfg, dict) else {}
    zero_tracking_cfg = latest_cfg.get("zero_tracking", {}) if isinstance(latest_cfg, dict) else {}
    production_cfg = latest_cfg.get("production", {}) if isinstance(latest_cfg, dict) else {}
    shift_start_utc = production_cfg.get("shift_start_utc")
    shift_total_lbs = repo.get_shift_total(shift_start_utc)

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
    zero_tracking_locked = bool(
        snap.get("zero_tracking_locked", (not zero_tracking_active))
    )
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
            "cal_points_total": int(snap.get("cal_points_count") or 0),
            "calibration_method": str(snap.get("calibration_method") or "uncalibrated"),
            "calibration_slope_lbs_per_mv": float(snap.get("calibration_slope_lbs_per_mv") or 0.0),
            "calibration_intercept_lbs": (
                float(snap.get("calibration_intercept_lbs"))
                if snap.get("calibration_intercept_lbs") is not None
                else None
            ),
            "calibration_last_utc": snap.get("calibration_last_utc"),
        },
        "calibration": {
            "method": str(snap.get("calibration_method") or "uncalibrated"),
            "slope_lbs_per_mv": float(snap.get("calibration_slope_lbs_per_mv") or 0.0),
            "intercept_lbs": (
                float(snap.get("calibration_intercept_lbs"))
                if snap.get("calibration_intercept_lbs") is not None
                else None
            ),
            "last_calibration_utc": snap.get("calibration_last_utc"),
            "active_points_count": int(snap.get("cal_points_used") or 0),
            "total_points_count": int(snap.get("cal_points_count") or 0),
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
            "ao_channel_v": int(out_cfg.get("ao_channel_v", out_cfg.get("ao_channel", 1)) or 1),
            "ao_channel_ma": int(out_cfg.get("ao_channel_ma", out_cfg.get("ao_channel", 1)) or 1),
            "mapping_mode": str(snap.get("output_mapping_mode", "linear")),
            "profile_active": bool(snap.get("output_profile_active", False)),
            "profile_points": int(snap.get("output_profile_points") or 0),
            "range_min_lb": float(range_cfg.get("min_lb", 0.0) or 0.0),
            "range_max_lb": float(range_cfg.get("max_lb", 300.0) or 300.0),
        },
        "production": {
            "totals": production_totals,
            "shift_total_lbs": shift_total_lbs,
            "shift_start_utc": shift_start_utc,
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


@bp.post("/api/production/shift/clear")
def api_production_shift_clear() -> Response:
    """Clear shift total by resetting shift start time to now."""
    repo: AppRepository = current_app.config["REPO"]
    cfg = repo.get_latest_config()
    
    # Update shift start time to current UTC time
    production = cfg.get("production") or {}
    new_shift_start = _utc_now()
    production["shift_start_utc"] = new_shift_start
    cfg["production"] = production
    
    repo.save_config(cfg)
    repo.log_event(
        level="INFO",
        code="SHIFT_TOTAL_CLEARED",
        message="Shift total cleared - shift start time reset.",
        details={"shift_start_utc": new_shift_start},
    )
    
    return Response(
        json.dumps({"success": True, "shift_start_utc": new_shift_start}),
        mimetype="application/json",
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


