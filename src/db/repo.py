from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

log = logging.getLogger(__name__)
CAL_POINT_WEIGHT_EPS_LB = 1e-6


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

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

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
        """Default config for summing-board scale transmitter."""
        return {
            # I2C configuration
            "i2c": {"bus": 1},
            # UI configuration
            "ui": {
                "maintenance_enabled": False,
                "poll_rate_ms": 500,
                "timezone": "UTC",
            },
            # DAQ board (24b8vin) -- summing board, single channel
            "daq": {
                "stack_level": 0,
                "channel": 7,           # 0-indexed, physical ch 8
                "gain_code": 6,         # +/-370mV range (best for load cells)
                "sample_rate": 0,       # 250 SPS (best noise rejection)
                "average_samples": 2,
            },
            # MegaIND configuration
            "megaind": {
                "stack_level": 0,
            },
            # Scale calibration
            "scale": {
                "zero_offset_mv": 0.0,
                "zero_offset_signal": 0.0,
                "zero_offset_updated_utc": None,
                "tare_offset_lbs": 0.0,
            },
            # Automatic near-zero drift compensation
            "zero_tracking": {
                "enabled": True,
                "range_lb": 0.5,
                "deadband_lb": 0.10,
                "hold_s": 6.0,
                "rate_lbs": 0.1,
                "persist_interval_s": 1.0,
            },
            # Physical button actions (opto inputs on MegaIND)
            "opto_actions": {
                "1": "tare",
                "2": "zero",
                "3": "print",
                "4": "none",
            },
            # Kalman filter and stability detection
            "filter": {
                "kalman_q": 1.0,        # Process noise
                "kalman_r": 50.0,       # Measurement noise
                # New key names used by settings page (kept in sync with legacy keys above).
                "kalman_process_noise": 1.0,
                "kalman_measurement_noise": 50.0,
                "stability_window": 25,
                "stability_threshold": 0.5,
                "stability_stddev_lb": 0.5,
                "stability_slope_lbs": 1.0,
            },
            # Excitation monitor thresholds (MegaIND analog input)
            "excitation": {
                "enabled": True,
                "ai_channel": 1,
                "warn_v": 9.0,
                "fault_v": 8.0,
            },
            # Startup output behavior
            "startup": {
                "delay_s": 0.0,
                "output_value": 0.0,
                "auto_arm": False,
                "auto_zero": False,
            },
            # Weight range for output scaling
            "range": {"min_lb": 0.0, "max_lb": 300.0},
            # Analog output to PLC
            "output": {
                "mode": "0_10V",
                "ao_channel": 1,
                "ao_channel_v": 1,
                "ao_channel_ma": 1,
                "safe_v": 0.0,
                "safe_ma": 4.0,
                "armed": True,
                "test_mode": False,
                "test_value": 0.0,
                "calibration_active": False,
                "nudge_value": 0.0,
                "deadband_enabled": True,
                "deadband_lb": 0.5,
                "ramp_enabled": False,
                "ramp_rate_v": 5.0,
                "ramp_rate_ma": 8.0,
            },
            # Timing
            "timing": {
                "loop_rate_hz": 20,
                "config_refresh_s": 2.0,
            },
            # Logging
            "logging": {
                "interval_s": 1,
                "retention_days": 30,
            },
            # Throughput cycle detection + event persistence
            "throughput": {
                "enabled": True,
                "device_id": None,
                "hopper_id": None,
                "empty_threshold_lb": 2.0,
                "rise_trigger_lb": 8.0,
                "full_min_lb": 15.0,
                "dump_drop_lb": 6.0,
                "full_stability_s": 0.4,
                "empty_confirm_s": 0.3,
                "min_processed_lb": 5.0,
                "max_cycle_s": 900.0,
            },
            # Production tracking (shift totals)
            "production": {
                "shift_start_utc": _utc_now(),
            },
        }

    # -------- calibration --------
    def upsert_calibration_point(
        self,
        known_weight_lbs: float,
        signal: float,
        weight_eps_lb: float = CAL_POINT_WEIGHT_EPS_LB,
    ) -> bool:
        """Compatibility wrapper that appends point and reports same-weight history.

        NOTE:
        - This method no longer deletes old rows.
        - Return value indicates whether same-weight history already existed.
        """
        known_weight_lbs = float(known_weight_lbs)
        signal = float(signal)
        weight_eps_lb = max(0.0, float(weight_eps_lb))
        existing_count = 0
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT COUNT(*) AS cnt FROM calibration_points WHERE ABS(known_weight_lbs - ?) <= ?;",
                (known_weight_lbs, weight_eps_lb),
            )
            row = cur.fetchone()
            existing_count = int(row["cnt"]) if row else 0
        self.add_calibration_point(known_weight_lbs=known_weight_lbs, signal=signal)
        return existing_count > 0

    def add_calibration_point(self, known_weight_lbs: float, signal: float) -> int:
        """Append calibration point and return inserted row id."""
        known_weight_lbs = float(known_weight_lbs)
        signal = float(signal)
        inserted_id = 0
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO calibration_points(ts, known_weight_lbs, signal, ratiometric) VALUES (?,?,?,?);",
                (_utc_now(), known_weight_lbs, signal, 0),  # Always 0 (raw mV)
            )
            inserted_id = int(cur.lastrowid or 0)
        self.log_event(
            level="INFO",
            code="CAL_POINT_ADDED",
            message="Calibration point added.",
            details={"known_weight_lbs": known_weight_lbs, "signal": signal, "point_id": inserted_id},
        )
        return inserted_id

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

    def get_calibration_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent calibration application history from events."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT ts, details_json FROM events WHERE code=? ORDER BY id DESC LIMIT ?;",
                ("CALIBRATION_APPLIED", int(limit)),
            )
            history: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                details = json.loads(row["details_json"] or "{}")
                history.append(
                    {
                        "ts": row["ts"],
                        "known_weight_lbs": details.get("known_weight_lbs"),
                        "requested_mode": details.get("requested_mode"),
                        "applied_mode": details.get("applied_mode"),
                        "captured_signal_mv": details.get("captured_signal_mv"),
                        "applied_signal_mv": details.get("applied_signal_mv"),
                        "previous_active_signal_mv": details.get("previous_active_signal_mv"),
                        "calibration_method": details.get("calibration_method"),
                        "slope_lbs_per_mv": details.get("slope_lbs_per_mv"),
                        "intercept_lbs": details.get("intercept_lbs"),
                        "active_points_count": details.get("active_points_count"),
                        "total_points_count": details.get("total_points_count"),
                    }
                )
            return history

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

    # -------- throughput events --------
    @staticmethod
    def _throughput_where_clause(
        start_utc: Optional[str],
        end_utc: Optional[str],
        device_id: Optional[str],
    ) -> tuple[str, List[Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if start_utc:
            clauses.append("timestamp_utc >= ?")
            params.append(str(start_utc))
        if end_utc:
            clauses.append("timestamp_utc < ?")
            params.append(str(end_utc))
        if device_id:
            clauses.append("device_id = ?")
            params.append(str(device_id))
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def add_throughput_event(
        self,
        *,
        processed_lbs: float,
        timestamp_utc: Optional[str] = None,
        full_lbs: Optional[float] = None,
        empty_lbs: Optional[float] = None,
        duration_ms: Optional[int] = None,
        confidence: Optional[float] = None,
        device_id: Optional[str] = None,
        hopper_id: Optional[str] = None,
    ) -> int:
        ts_utc = str(timestamp_utc or _utc_now())
        created_at = _utc_now()
        inserted_id = 0
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO throughput_events("
                "timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms, confidence, device_id, hopper_id, created_at"
                ") VALUES (?,?,?,?,?,?,?,?,?);",
                (
                    ts_utc,
                    float(processed_lbs),
                    (None if full_lbs is None else float(full_lbs)),
                    (None if empty_lbs is None else float(empty_lbs)),
                    (None if duration_ms is None else int(duration_ms)),
                    (None if confidence is None else float(confidence)),
                    (None if device_id is None else str(device_id)),
                    (None if hopper_id is None else str(hopper_id)),
                    created_at,
                ),
            )
            inserted_id = int(cur.lastrowid or 0)
        return inserted_id

    def get_throughput_events_page(
        self,
        *,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        device_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[Dict[str, Any]], int]:
        page = max(1, int(page))
        page_size = max(1, min(500, int(page_size)))
        offset = (page - 1) * page_size
        where_sql, where_params = self._throughput_where_clause(start_utc, end_utc, device_id)

        with self._conn() as conn:
            count_cur = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM throughput_events{where_sql};",
                tuple(where_params),
            )
            count_row = count_cur.fetchone()
            total = int(count_row["cnt"]) if count_row else 0

            cur = conn.execute(
                "SELECT id, timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms, "
                "confidence, device_id, hopper_id, created_at "
                f"FROM throughput_events{where_sql} "
                "ORDER BY timestamp_utc DESC, id DESC LIMIT ? OFFSET ?;",
                tuple(where_params + [page_size, offset]),
            )

            events: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                events.append(
                    {
                        "id": int(row["id"]),
                        "timestamp_utc": row["timestamp_utc"],
                        "processed_lbs": float(row["processed_lbs"]),
                        "full_lbs": (None if row["full_lbs"] is None else float(row["full_lbs"])),
                        "empty_lbs": (None if row["empty_lbs"] is None else float(row["empty_lbs"])),
                        "duration_ms": (None if row["duration_ms"] is None else int(row["duration_ms"])),
                        "confidence": (None if row["confidence"] is None else float(row["confidence"])),
                        "device_id": row["device_id"],
                        "hopper_id": row["hopper_id"],
                        "created_at": row["created_at"],
                    }
                )
            return events, total

    def get_throughput_events_range(
        self,
        *,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        device_id: Optional[str] = None,
        order_desc: bool = False,
    ) -> List[Dict[str, Any]]:
        where_sql, where_params = self._throughput_where_clause(start_utc, end_utc, device_id)
        order_sql = "DESC" if order_desc else "ASC"
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT id, timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms, "
                "confidence, device_id, hopper_id, created_at "
                f"FROM throughput_events{where_sql} "
                f"ORDER BY timestamp_utc {order_sql}, id {order_sql};",
                tuple(where_params),
            )
            rows: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                rows.append(
                    {
                        "id": int(row["id"]),
                        "timestamp_utc": row["timestamp_utc"],
                        "processed_lbs": float(row["processed_lbs"]),
                        "full_lbs": (None if row["full_lbs"] is None else float(row["full_lbs"])),
                        "empty_lbs": (None if row["empty_lbs"] is None else float(row["empty_lbs"])),
                        "duration_ms": (None if row["duration_ms"] is None else int(row["duration_ms"])),
                        "confidence": (None if row["confidence"] is None else float(row["confidence"])),
                        "device_id": row["device_id"],
                        "hopper_id": row["hopper_id"],
                        "created_at": row["created_at"],
                    }
                )
            return rows

    def get_throughput_totals(
        self,
        *,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        where_sql, where_params = self._throughput_where_clause(start_utc, end_utc, device_id)
        with self._conn() as conn:
            cur = conn.execute(
                f"SELECT COALESCE(SUM(processed_lbs), 0.0) AS total_lbs, COUNT(*) AS cnt FROM throughput_events{where_sql};",
                tuple(where_params),
            )
            row = cur.fetchone()
        total_processed = float(row["total_lbs"]) if row else 0.0
        event_count = int(row["cnt"]) if row else 0
        avg_per_event = (total_processed / event_count) if event_count > 0 else 0.0
        return {
            "total_processed_lbs": total_processed,
            "event_count": event_count,
            "avg_per_event_lbs": avg_per_event,
        }

    def get_shift_total(self, shift_start_utc: Optional[str] = None) -> float:
        """Get total processed weight since shift start time.
        
        Args:
            shift_start_utc: ISO-8601 timestamp for shift start. If None, returns 0.0.
            
        Returns:
            Total weight processed in pounds since shift_start_utc.
        """
        if shift_start_utc is None:
            return 0.0
        
        totals = self.get_throughput_totals(start_utc=shift_start_utc, end_utc=None, device_id=None)
        return float(totals.get("total_processed_lbs", 0.0) or 0.0)

    def delete_throughput_event(self, event_id: int) -> bool:
        with self._conn() as conn:
            # Get event data BEFORE deleting so we can update production_totals
            cur = conn.execute(
                "SELECT timestamp_utc, processed_lbs FROM throughput_events WHERE id = ?;",
                (int(event_id),),
            )
            event = cur.fetchone()
            if not event:
                return False
            
            # Delete from throughput_events
            conn.execute(
                "DELETE FROM throughput_events WHERE id = ?;",
                (int(event_id),),
            )
            
            # Update production_totals - subtract the deleted weight
            timestamp_utc = event["timestamp_utc"]
            processed_lbs = float(event["processed_lbs"])
            
            # Parse timestamp to get date
            try:
                dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
                event_date = dt.date()
            except (ValueError, AttributeError):
                # If we can't parse timestamp, skip production_totals update
                return True
            
            # Update all period types (day, week, month, year)
            for period_type in ["day", "week", "month", "year"]:
                period_start = self._period_start(event_date, period_type)
                conn.execute(
                    "UPDATE production_totals SET total_lbs = total_lbs - ? "
                    "WHERE period_type = ? AND period_start = ?;",
                    (processed_lbs, period_type, period_start),
                )
            
            return True

    def delete_throughput_events(
        self,
        *,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> int:
        where_sql, where_params = self._throughput_where_clause(start_utc, end_utc, device_id)
        with self._conn() as conn:
            # Get events BEFORE deleting so we can update production_totals
            cur = conn.execute(
                f"SELECT timestamp_utc, processed_lbs FROM throughput_events{where_sql};",
                tuple(where_params),
            )
            events = cur.fetchall()
            
            # Delete from throughput_events
            conn.execute(
                f"DELETE FROM throughput_events{where_sql};",
                tuple(where_params),
            )
            cur = conn.execute("SELECT changes() AS cnt;")
            row = cur.fetchone()
            deleted_count = int(row["cnt"]) if row else 0
            
            # Update production_totals - subtract each deleted event's weight
            for event in events:
                timestamp_utc = event["timestamp_utc"]
                processed_lbs = float(event["processed_lbs"])
                
                # Parse timestamp to get date
                try:
                    dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
                    event_date = dt.date()
                except (ValueError, AttributeError):
                    continue
                
                # Update all period types (day, week, month, year)
                for period_type in ["day", "week", "month", "year"]:
                    period_start = self._period_start(event_date, period_type)
                    conn.execute(
                        "UPDATE production_totals SET total_lbs = total_lbs - ? "
                        "WHERE period_type = ? AND period_start = ?;",
                        (processed_lbs, period_type, period_start),
                    )
            
            return deleted_count

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


