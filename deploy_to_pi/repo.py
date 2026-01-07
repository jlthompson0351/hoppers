from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _deep_merge(defaults: Any, overrides: Any) -> Any:
    """
    Deep-merge overrides onto defaults.

    - dict: merge keys recursively
    - list: if list-of-dicts, merge by index; otherwise overrides wins
    - scalar/other: overrides wins (including None)
    """

    if isinstance(defaults, dict) and isinstance(overrides, dict):
        out: Dict[str, Any] = dict(defaults)
        for k, v in overrides.items():
            if k in out:
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    if isinstance(defaults, list) and isinstance(overrides, list):
        if all(isinstance(x, dict) for x in defaults) and all(isinstance(x, dict) for x in overrides):
            merged: List[Any] = []
            for i in range(max(len(defaults), len(overrides))):
                if i < len(defaults) and i < len(overrides):
                    merged.append(_deep_merge(defaults[i], overrides[i]))
                elif i < len(overrides):
                    merged.append(overrides[i])
                else:
                    merged.append(defaults[i])
            return merged
        return overrides

    return overrides


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class CalibrationPointRow:
    id: int
    ts: str
    known_weight_lbs: float
    signal: float
    # NOTE: ratiometric field removed - we always use raw mV now


@dataclass(frozen=True)
class PlcProfilePointRow:
    id: int
    ts: str
    output_mode: str
    analog_value: float
    plc_displayed_lbs: float


class AppRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    # -------- events / logging --------
    def log_event(self, level: str, code: str, message: str, details: Optional[dict] = None) -> None:
        details_json = json.dumps(details or {})
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO events(ts, level, code, message, details_json) VALUES (?,?,?,?,?);",
                (_utc_now(), str(level), str(code), str(message), details_json),
            )

    def get_recent_events(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT ts, level, code, message, details_json FROM events ORDER BY id DESC LIMIT ?;",
                (int(limit),),
            )
            out: List[Dict[str, Any]] = []
            for r in cur.fetchall():
                out.append(
                    {
                        "ts": r["ts"],
                        "level": r["level"],
                        "code": r["code"],
                        "message": r["message"],
                        "details": json.loads(r["details_json"] or "{}"),
                    }
                )
            return out

    # -------- config --------
    def get_latest_config(self) -> Dict[str, Any]:
        with self._conn() as conn:
            cur = conn.execute("SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1;")
            row = cur.fetchone()
            if row is None:
                return self.default_config()
            try:
                cfg = json.loads(row["config_json"])
            except Exception as e:  # noqa: BLE001
                log.exception("Failed to parse config JSON: %s", e)
                return self.default_config()

            # Existing deployments may have an older config shape stored in SQLite.
            # Always deep-merge the stored config onto the current defaults so:
            # - new pages/templates don't 500 on missing nested keys
            # - new features default to safe "off" behavior unless explicitly configured
            defaults = self.default_config()
            if not isinstance(cfg, dict):
                return defaults
            return _deep_merge(defaults, cfg)

    def save_config(self, cfg: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO config_versions(ts, config_json) VALUES (?,?);",
                (_utc_now(), json.dumps(cfg)),
            )
        self.log_event(level="INFO", code="CONFIG_SAVED", message="Configuration saved.", details={})

    def default_config(self) -> Dict[str, Any]:
        # Comprehensive default config for industrial scale transmitter.
        return {
            # Hardware mode: "real" or "sim"
            "hw_mode": "sim",
            # I2C configuration
            "i2c": {
                "bus": 1,
                "required_addresses": {"megaind": None, "daq24b8vin": None},
            },
            # UI configuration
            "ui": {
                "maintenance_enabled": False,
                "poll_rate_ms": 500,
            },
            # DAQ board (24b8vin) configuration
            "daq24b8vin": {
                "stack_level": 0,
                "average_samples": 2,
                "channels": [
                    {"enabled": True, "role": "Load Cell (active)", "gain_code": 7},
                    {"enabled": True, "role": "Load Cell (active)", "gain_code": 7},
                    {"enabled": True, "role": "Load Cell (active)", "gain_code": 7},
                    {"enabled": True, "role": "Load Cell (active)", "gain_code": 7},
                    {"enabled": False, "role": "Not used", "gain_code": 7},
                    {"enabled": False, "role": "Not used", "gain_code": 7},
                    {"enabled": False, "role": "Not used", "gain_code": 7},
                    {"enabled": False, "role": "Not used", "gain_code": 7},
                ],
            },
            # Scale configuration
            "scale": {
                "tare_offset_lbs": 0.0,
                "zero_offset_signal": 0.0,
                "span_capture": {"zero_signal": None, "span_signal": None, "known_weight_lbs": None},
            },
            "enabled_channels": [0, 1, 2, 3],
            # Filter/signal processing settings
            "filter": {
                # Kalman filter (preferred)
                "use_kalman": True,
                "kalman_process_noise": 1.0,
                "kalman_measurement_noise": 50.0,
                # IIR filter (legacy fallback)
                "alpha": 0.18,
                # Stability detection
                "stability_window": 25,
                "stability_stddev_lb": 0.8,
                "stability_slope_lbs": 0.8,
                # Advanced noise reduction
                "median_enabled": False,
                "median_window": 5,
                "notch_enabled": False,
                "notch_freq": 60,
            },
            # Weight range for output scaling
            "range": {"min_lb": 0.0, "max_lb": 300.0},
            # NOTE: Ratiometric mode removed - always use raw mV
            # Excitation voltage monitoring
            "excitation": {"ai_channel": 1, "warn_v": 9.0, "fault_v": 8.0},
            # Analog output configuration
            "output": {
                "mode": "0_10V",
                "ao_channel_v": 1,
                "ao_channel_ma": 1,
                "safe_v": 0.0,
                "safe_ma": 4.0,
                "armed": False,
                "test_mode": False,
                "test_value": 0.0,
                "calibration_active": False,
                "nudge_value": 0.0,
                # Dead band
                "deadband_enabled": True,
                "deadband_lb": 0.5,
                # Output ramping
                "ramp_enabled": False,
                "ramp_rate_v": 5.0,
                "ramp_rate_ma": 8.0,
            },
            # Zero tracking (auto-zero maintenance)
            "zero_tracking": {
                "enabled": False,
                "range_lb": 0.5,
                "rate_lbs": 0.1,
            },
            # Startup behavior
            "startup": {
                "auto_zero": False,
                "auto_arm": False,
                "delay_s": 5,
                "output_value": 0.0,
            },
            # Alarms and limits
            "alarms": {
                "overload_lb": None,
                "overload_action": "alarm",
                "underload_lb": -5,
                "allow_negative": False,
                "high_lb": None,
                "low_lb": None,
                "rate_lbs": None,
            },
            # Fault handling
            "fault": {
                "delay_s": 2.0,
                "recovery": "auto",
            },
            # Dump detection
            "dump_detection": {"drop_threshold_lb": 25.0, "min_prev_stable_lb": 10.0},
            # Drift detection
            "drift": {"ratio_threshold": 0.12, "ema_alpha": 0.02, "consecutive_required": 20},
            # Timing
            "timing": {
                "loop_rate_hz": 20,
                "config_refresh_s": 2.0,
                "i2c_retry_count": 3,
                "board_offline_s": 5,
            },
            # Logging
            "logging": {
                "interval_s": 1,
                "retention_days": 30,
                "log_raw": False,
                "log_weight": True,
                "log_output": True,
                "event_only": False,
            },
            # Watchdog
            "watchdog": {
                "daq_enabled": False,
                "daq_period_s": 120,
                "megaind_enabled": False,
                "megaind_period_s": 120,
            },
            # RS485/MODBUS (disabled by default)
            "rs485": {
                "enabled": False,
                "mode": 0,
                "baudrate": 9600,
                "stop_bits": 1,
                "parity": "none",
                "slave_address": 1,
            },
            # One-wire bus (disabled by default)
            "onewire": {
                "enabled": False,
            },
            # LED indicators (disabled by default)
            "leds": {
                "enabled": False,
            },
            # MegaIND I/O (Maintenance / Extra Controls)
            "megaind_io": {
                "armed": False,
                "allow_plc_channel": False,
                "safe_v": 0.0,
                "role_map": {
                    "ao_1": "PLC_WEIGHT",
                    "ai_1": "EXCITATION",
                },
                "ao_v": [],
                "rules": [],
            },
        }

    # -------- calibration --------
    def add_calibration_point(self, known_weight_lbs: float, signal: float) -> None:
        """Add a calibration point. Always uses raw mV (ratiometric removed)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO calibration_points(ts, known_weight_lbs, signal, ratiometric) VALUES (?,?,?,?);",
                (_utc_now(), float(known_weight_lbs), float(signal), 0),  # Always 0 (raw mV)
            )
        self.log_event(
            level="INFO",
            code="CAL_POINT_ADDED",
            message="Calibration point added.",
            details={"known_weight_lbs": known_weight_lbs, "signal": signal},
        )

    def get_calibration_points(self, limit: int = 200) -> List[CalibrationPointRow]:
        """Get all calibration points. Ratiometric flag is ignored (always raw mV)."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT id, ts, known_weight_lbs, signal FROM calibration_points ORDER BY known_weight_lbs ASC LIMIT ?;",
                (int(limit),),
            )
            rows = []
            for r in cur.fetchall():
                rows.append(
                    CalibrationPointRow(
                        id=int(r["id"]),
                        ts=r["ts"],
                        known_weight_lbs=float(r["known_weight_lbs"]),
                        signal=float(r["signal"]),
                    )
                )
            return rows

    def delete_calibration_point(self, point_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM calibration_points WHERE id=?;", (int(point_id),))

    def clear_calibration_points(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM calibration_points;")

    # -------- PLC profile mapping --------
    def add_plc_profile_point(self, output_mode: str, analog_value: float, plc_displayed_lbs: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO plc_profile_points(ts, output_mode, analog_value, plc_displayed_lbs) VALUES (?,?,?,?);",
                (_utc_now(), str(output_mode), float(analog_value), float(plc_displayed_lbs)),
            )
        self.log_event(
            level="INFO",
            code="PLC_PROFILE_POINT_ADDED",
            message="PLC profile point added.",
            details={
                "output_mode": output_mode,
                "analog_value": analog_value,
                "plc_displayed_lbs": plc_displayed_lbs,
            },
        )

    def get_plc_profile_points(self, output_mode: str, limit: int = 500) -> List[PlcProfilePointRow]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT id, ts, output_mode, analog_value, plc_displayed_lbs "
                "FROM plc_profile_points WHERE output_mode=? ORDER BY analog_value ASC LIMIT ?;",
                (str(output_mode), int(limit)),
            )
            rows = []
            for r in cur.fetchall():
                rows.append(
                    PlcProfilePointRow(
                        id=int(r["id"]),
                        ts=r["ts"],
                        output_mode=r["output_mode"],
                        analog_value=float(r["analog_value"]),
                        plc_displayed_lbs=float(r["plc_displayed_lbs"]),
                    )
                )
            return rows

    def delete_plc_profile_point(self, point_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM plc_profile_points WHERE id=?;", (int(point_id),))

    # -------- trends (scaffold hooks) --------
    def add_excitation_sample(self, excitation_v: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO trends_excitation(ts, excitation_v) VALUES (?,?);",
                (_utc_now(), float(excitation_v)),
            )

    def add_channel_sample(self, channel: int, enabled: bool, raw_mv: float, filtered: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO trends_channels(ts, channel, enabled, raw_mv, filtered) VALUES (?,?,?,?,?);",
                (_utc_now(), int(channel), 1 if bool(enabled) else 0, float(raw_mv), float(filtered)),
            )

    def add_total_sample(self, total_lbs: float, stable: bool, output_mode: str, output_cmd: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO trends_total(ts, total_lbs, stable, output_mode, output_cmd) VALUES (?,?,?,?,?);",
                (_utc_now(), float(total_lbs), 1 if stable else 0, str(output_mode), float(output_cmd)),
            )

    def cleanup_trends(self, retention_days: int) -> None:
        """Delete trend rows older than retention_days.

        NOTE: Uses string comparison on ISO-8601 timestamps; this works because
        all timestamps are stored in a consistent UTC ISO format.
        """
        days = int(retention_days)
        if days <= 0:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        with self._conn() as conn:
            conn.execute("DELETE FROM trends_total WHERE ts < ?;", (cutoff,))
            conn.execute("DELETE FROM trends_excitation WHERE ts < ?;", (cutoff,))
            conn.execute("DELETE FROM trends_channels WHERE ts < ?;", (cutoff,))

    # -------- production totals --------
    @staticmethod
    def _period_start(d: date, period_type: str) -> str:
        if period_type == "day":
            return d.isoformat()
        if period_type == "week":
            # Monday as start of week
            start = d.fromordinal(d.toordinal() - d.weekday())
            return start.isoformat()
        if period_type == "month":
            return date(d.year, d.month, 1).isoformat()
        if period_type == "year":
            return date(d.year, 1, 1).isoformat()
        raise ValueError(f"Unknown period_type: {period_type}")

    def record_dump_and_increment_totals(self, prev_stable_lbs: float, new_stable_lbs: float, processed_lbs: float) -> None:
        ts = _utc_now()
        processed_lbs = float(processed_lbs)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO production_dumps(ts, prev_stable_lbs, new_stable_lbs, processed_lbs) VALUES (?,?,?,?);",
                (ts, float(prev_stable_lbs), float(new_stable_lbs), processed_lbs),
            )

            d = datetime.now(timezone.utc).date()
            for period_type in ("day", "week", "month", "year"):
                period_start = self._period_start(d, period_type)
                conn.execute(
                    "INSERT INTO production_totals(period_type, period_start, total_lbs) VALUES (?,?,?) "
                    "ON CONFLICT(period_type, period_start) DO UPDATE SET total_lbs = total_lbs + excluded.total_lbs;",
                    (period_type, period_start, processed_lbs),
                )

    # -------- production totals queries --------
    def get_production_totals(self, periods: Optional[List[str]] = None) -> Dict[str, float]:
        """Get production totals for specified periods.

        Args:
            periods: List of period types ('day', 'week', 'month', 'year').
                    Defaults to ['day', 'week', 'month'].

        Returns:
            Dict mapping period type to total_lbs
        """
        if periods is None:
            periods = ["day", "week", "month"]

        d = datetime.now(timezone.utc).date()
        result: Dict[str, float] = {}

        with self._conn() as conn:
            for period_type in periods:
                period_start = self._period_start(d, period_type)
                cur = conn.execute(
                    "SELECT total_lbs FROM production_totals WHERE period_type=? AND period_start=?;",
                    (period_type, period_start),
                )
                row = cur.fetchone()
                result[period_type] = float(row["total_lbs"]) if row else 0.0

        return result

    def get_dump_count(self, period: str = "day") -> int:
        """Get number of dumps for a period.

        Args:
            period: 'day', 'week', 'month', or 'year'

        Returns:
            Number of dumps in the period
        """
        d = datetime.now(timezone.utc).date()
        period_start = self._period_start(d, period)

        # Calculate end of period for query
        if period == "day":
            # Today's dumps
            start_ts = f"{period_start}T00:00:00"
            end_ts = f"{period_start}T23:59:59"
        elif period == "week":
            start_date = date.fromisoformat(period_start)
            end_date = date.fromordinal(start_date.toordinal() + 6)
            start_ts = f"{period_start}T00:00:00"
            end_ts = f"{end_date.isoformat()}T23:59:59"
        elif period == "month":
            # End of month
            start_date = date.fromisoformat(period_start)
            if start_date.month == 12:
                end_date = date(start_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(start_date.year, start_date.month + 1, 1) - timedelta(days=1)
            start_ts = f"{period_start}T00:00:00"
            end_ts = f"{end_date.isoformat()}T23:59:59"
        else:
            # Year
            start_ts = f"{period_start}T00:00:00"
            end_ts = f"{d.year}-12-31T23:59:59"

        with self._conn() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) as cnt FROM production_dumps WHERE ts >= ? AND ts <= ?;",
                (start_ts, end_ts),
            )
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0

    def get_last_dump(self) -> Optional[Dict[str, Any]]:
        """Get the most recent dump record."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT ts, prev_stable_lbs, new_stable_lbs, processed_lbs FROM production_dumps ORDER BY id DESC LIMIT 1;"
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "ts": row["ts"],
                "prev_stable_lbs": float(row["prev_stable_lbs"]),
                "new_stable_lbs": float(row["new_stable_lbs"]),
                "processed_lbs": float(row["processed_lbs"]),
            }


