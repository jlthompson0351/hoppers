from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

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


@dataclass(frozen=True)
class SetWeightCurrentRow:
    line_id: str
    machine_id: str
    set_weight_value: float
    set_weight_unit: str
    set_weight_lbs: float
    source: str
    source_event_id: Optional[str]
    erp_timestamp_utc: Optional[str]
    product_id: Optional[str]
    operator_id: Optional[str]
    job_id: Optional[str]
    step_id: Optional[str]
    metadata: Dict[str, Any]
    state_seq: int
    received_at_utc: str
    record_time_set_utc: str
    updated_at_utc: str


@dataclass(frozen=True)
class SetWeightReceiptResult:
    applied_to_current: bool
    duplicate_event: bool
    state_seq: int
    current_set_weight_lbs: float
    current_set_weight_unit: str


@dataclass(frozen=True)
class JobLifecycleStateRow:
    line_id: str
    machine_id: str
    active_job_id: str
    active_job_started_record_time_set_utc: str
    active_job_last_record_time_set_utc: str
    active_job_first_erp_timestamp_utc: Optional[str]
    active_job_last_erp_timestamp_utc: Optional[str]
    override_count: int
    last_set_weight_lbs: Optional[float]
    last_set_weight_unit: Optional[str]
    last_source_event_id: Optional[str]
    updated_at_utc: str


class AppRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    @staticmethod
    def _configure_connection(conn: sqlite3.Connection) -> None:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("PRAGMA foreign_keys=ON;")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        self._configure_connection(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _write_conn(self) -> Iterator[sqlite3.Connection]:
        """Open a write-locked SQLite transaction for atomic RMW updates."""
        conn = sqlite3.connect(self.db_path, timeout=30.0, isolation_level=None)
        self._configure_connection(conn)
        conn.execute("BEGIN IMMEDIATE;")
        try:
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    def _load_latest_config_from_conn(self, conn: sqlite3.Connection) -> Dict[str, Any]:
        cur = conn.execute("SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        if row is None:
            return self.default_config()
        try:
            cfg = json.loads(row["config_json"])
        except Exception as e:  # noqa: BLE001
            log.exception("Failed to parse config JSON: %s", e)
            return self.default_config()

        defaults = self.default_config()
        if not isinstance(cfg, dict):
            return defaults
        return _deep_merge(defaults, cfg)

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
            return self._load_latest_config_from_conn(conn)

    def save_config(self, cfg: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO config_versions(ts, config_json) VALUES (?,?);",
                (_utc_now(), json.dumps(cfg)),
            )
        self.log_event(level="INFO", code="CONFIG_SAVED", message="Configuration saved.", details={})

    def update_config_section(
        self,
        section: str,
        mutator: Callable[[Dict[str, Any], Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        """Atomically read-modify-write a single config section.

        This method acquires an immediate write lock before reading current
        config so concurrent writers cannot clobber each other with stale reads.
        """
        section_name = str(section or "").strip()
        if not section_name:
            raise ValueError("section must be a non-empty string")

        with self._write_conn() as conn:
            cfg = self._load_latest_config_from_conn(conn)
            section_cfg = cfg.get(section_name)
            if not isinstance(section_cfg, dict):
                section_cfg = {}
            mutator(section_cfg, cfg)
            cfg[section_name] = section_cfg

            ts = _utc_now()
            conn.execute(
                "INSERT INTO config_versions(ts, config_json) VALUES (?,?);",
                (ts, json.dumps(cfg)),
            )
            conn.execute(
                "INSERT INTO events(ts, level, code, message, details_json) VALUES (?,?,?,?,?);",
                (ts, "INFO", "CONFIG_SAVED", "Configuration saved.", "{}"),
            )
            return cfg

    @staticmethod
    def _clean_required_text(value: Any, field_name: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            raise ValueError(f"{field_name} is required")
        return cleaned

    @staticmethod
    def _clean_optional_text(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None

    @staticmethod
    def _normalize_weight_unit(value: Any) -> str:
        unit = str(value or "").strip().lower()
        alias_map = {
            "lb": "lb",
            "lbs": "lb",
            "pound": "lb",
            "pounds": "lb",
            "kg": "kg",
            "kgs": "kg",
            "kilogram": "kg",
            "kilograms": "kg",
            "g": "g",
            "gram": "g",
            "grams": "g",
            "oz": "oz",
            "ounce": "oz",
            "ounces": "oz",
        }
        normalized = alias_map.get(unit)
        if normalized is None:
            raise ValueError(f"Unsupported weight unit: {value!r}")
        return normalized

    @staticmethod
    def _parse_metadata_json(value: Any) -> Dict[str, Any]:
        try:
            parsed = json.loads(value or "{}")
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _row_to_set_weight_current(self, row: sqlite3.Row) -> SetWeightCurrentRow:
        return SetWeightCurrentRow(
            line_id=str(row["line_id"]),
            machine_id=str(row["machine_id"]),
            set_weight_value=float(row["set_weight_value"]),
            set_weight_unit=str(row["set_weight_unit"]),
            set_weight_lbs=float(row["set_weight_lbs"]),
            source=str(row["source"]),
            source_event_id=self._clean_optional_text(row["source_event_id"]),
            erp_timestamp_utc=self._clean_optional_text(row["erp_timestamp_utc"]),
            product_id=self._clean_optional_text(row["product_id"]),
            operator_id=self._clean_optional_text(row["operator_id"]),
            job_id=self._clean_optional_text(row["job_id"]),
            step_id=self._clean_optional_text(row["step_id"]),
            metadata=self._parse_metadata_json(row["metadata_json"]),
            state_seq=int(row["state_seq"] or 0),
            received_at_utc=str(row["received_at_utc"]),
            record_time_set_utc=str(row["record_time_set_utc"] or row["received_at_utc"]),
            updated_at_utc=str(row["updated_at_utc"]),
        )

    # -------- set weight persistence --------
    def get_set_weight_current(self, line_id: str, machine_id: str) -> Optional[SetWeightCurrentRow]:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT line_id, machine_id, set_weight_value, set_weight_unit, set_weight_lbs, "
                "source, source_event_id, erp_timestamp_utc, product_id, operator_id, "
                "job_id, step_id, metadata_json, state_seq, received_at_utc, record_time_set_utc, updated_at_utc "
                "FROM set_weight_current WHERE line_id = ? AND machine_id = ? LIMIT 1;",
                (line_id_clean, machine_id_clean),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_set_weight_current(row)

    def get_latest_set_weight_current(self) -> Optional[SetWeightCurrentRow]:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT line_id, machine_id, set_weight_value, set_weight_unit, set_weight_lbs, "
                "source, source_event_id, erp_timestamp_utc, product_id, operator_id, "
                "job_id, step_id, metadata_json, state_seq, received_at_utc, record_time_set_utc, updated_at_utc "
                "FROM set_weight_current ORDER BY updated_at_utc DESC, rowid DESC LIMIT 1;"
            )
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_set_weight_current(row)

    def record_set_weight_receipt(
        self,
        *,
        line_id: str,
        machine_id: str,
        set_weight_value: float,
        set_weight_unit: str,
        set_weight_lbs: float,
        source: str,
        state_seq: int,
        received_at_utc: Optional[str] = None,
        source_event_id: Optional[str] = None,
        erp_timestamp_utc: Optional[str] = None,
        product_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        job_id: Optional[str] = None,
        step_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        record_time_set_utc: Optional[str] = None,
    ) -> SetWeightReceiptResult:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        unit_clean = self._normalize_weight_unit(set_weight_unit)
        source_clean = self._clean_required_text(source, "source")
        source_event_id_clean = self._clean_optional_text(source_event_id)
        erp_timestamp_utc_clean = self._clean_optional_text(erp_timestamp_utc)
        product_id_clean = self._clean_optional_text(product_id)
        operator_id_clean = self._clean_optional_text(operator_id)
        job_id_clean = self._clean_optional_text(job_id)
        step_id_clean = self._clean_optional_text(step_id)
        received_ts = str(received_at_utc or _utc_now())
        record_time_set_ts = str(record_time_set_utc or received_ts)
        metadata_json = json.dumps(metadata or {}, sort_keys=True)

        weight_value = float(set_weight_value)
        weight_lbs = float(set_weight_lbs)
        if (not math.isfinite(weight_value)) or weight_value < 0.0:
            raise ValueError("set_weight_value must be finite and >= 0")
        if (not math.isfinite(weight_lbs)) or weight_lbs < 0.0:
            raise ValueError("set_weight_lbs must be finite and >= 0")

        requested_state_seq = max(0, int(state_seq))
        current_state_seq = 0
        current_lbs = 0.0
        current_unit = unit_clean
        previous_lbs: Optional[float] = None
        previous_unit: Optional[str] = None
        duplicate_event = False
        applied_to_current = False

        with self._write_conn() as conn:
            cur = conn.execute(
                "SELECT set_weight_lbs, set_weight_unit, state_seq "
                "FROM set_weight_current WHERE line_id = ? AND machine_id = ? LIMIT 1;",
                (line_id_clean, machine_id_clean),
            )
            current_row = cur.fetchone()
            if current_row is not None:
                previous_lbs = float(current_row["set_weight_lbs"])
                previous_unit = str(current_row["set_weight_unit"])
                current_state_seq = int(current_row["state_seq"] or 0)
                current_lbs = previous_lbs
                current_unit = previous_unit

            if source_event_id_clean:
                dup_cur = conn.execute(
                    "SELECT 1 FROM set_weight_history "
                    "WHERE line_id = ? AND machine_id = ? AND source_event_id = ? LIMIT 1;",
                    (line_id_clean, machine_id_clean, source_event_id_clean),
                )
                duplicate_event = dup_cur.fetchone() is not None

            if not duplicate_event:
                effective_state_seq = max(requested_state_seq, current_state_seq + 1)
                applied_to_current = True
                current_state_seq = effective_state_seq
                current_lbs = weight_lbs
                current_unit = unit_clean
                conn.execute(
                    "INSERT INTO set_weight_current("
                    "line_id, machine_id, set_weight_value, set_weight_unit, set_weight_lbs, "
                    "source, source_event_id, erp_timestamp_utc, product_id, operator_id, "
                    "job_id, step_id, metadata_json, state_seq, received_at_utc, record_time_set_utc, updated_at_utc"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(line_id, machine_id) DO UPDATE SET "
                    "set_weight_value=excluded.set_weight_value, "
                    "set_weight_unit=excluded.set_weight_unit, "
                    "set_weight_lbs=excluded.set_weight_lbs, "
                    "source=excluded.source, "
                    "source_event_id=excluded.source_event_id, "
                    "erp_timestamp_utc=excluded.erp_timestamp_utc, "
                    "product_id=excluded.product_id, "
                    "operator_id=excluded.operator_id, "
                    "job_id=excluded.job_id, "
                    "step_id=excluded.step_id, "
                    "metadata_json=excluded.metadata_json, "
                    "state_seq=excluded.state_seq, "
                    "received_at_utc=excluded.received_at_utc, "
                    "record_time_set_utc=excluded.record_time_set_utc, "
                    "updated_at_utc=excluded.updated_at_utc;",
                    (
                        line_id_clean,
                        machine_id_clean,
                        weight_value,
                        unit_clean,
                        weight_lbs,
                        source_clean,
                        source_event_id_clean,
                        erp_timestamp_utc_clean,
                        product_id_clean,
                        operator_id_clean,
                        job_id_clean,
                        step_id_clean,
                        metadata_json,
                        current_state_seq,
                        received_ts,
                        record_time_set_ts,
                        _utc_now(),
                    ),
                )
            else:
                effective_state_seq = current_state_seq

            conn.execute(
                "INSERT INTO set_weight_history("
                "received_at_utc, record_time_set_utc, line_id, machine_id, set_weight_value, set_weight_unit, set_weight_lbs, "
                "source, source_event_id, erp_timestamp_utc, product_id, operator_id, "
                "job_id, step_id, metadata_json, applied_to_current, duplicate_event, "
                "previous_set_weight_lbs, previous_set_weight_unit, state_seq, created_at_utc"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);",
                (
                    received_ts,
                    record_time_set_ts,
                    line_id_clean,
                    machine_id_clean,
                    weight_value,
                    unit_clean,
                    weight_lbs,
                    source_clean,
                    source_event_id_clean,
                    erp_timestamp_utc_clean,
                    product_id_clean,
                    operator_id_clean,
                    job_id_clean,
                    step_id_clean,
                    metadata_json,
                    1 if applied_to_current else 0,
                    1 if duplicate_event else 0,
                    previous_lbs,
                    previous_unit,
                    effective_state_seq,
                    _utc_now(),
                ),
            )

        return SetWeightReceiptResult(
            applied_to_current=applied_to_current,
            duplicate_event=duplicate_event,
            state_seq=current_state_seq,
            current_set_weight_lbs=current_lbs,
            current_set_weight_unit=current_unit,
        )

    def get_set_weight_history_range(
        self,
        *,
        line_id: str,
        machine_id: str,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        clauses = ["line_id = ?", "machine_id = ?"]
        params: List[Any] = [line_id_clean, machine_id_clean]
        if start_utc:
            clauses.append("received_at_utc >= ?")
            params.append(str(start_utc))
        if end_utc:
            clauses.append("received_at_utc < ?")
            params.append(str(end_utc))
        where_sql = " AND ".join(clauses)
        sql = (
            "SELECT id, received_at_utc, record_time_set_utc, line_id, machine_id, set_weight_value, set_weight_unit, "
            "set_weight_lbs, source, source_event_id, erp_timestamp_utc, product_id, operator_id, "
            "job_id, step_id, metadata_json, applied_to_current, duplicate_event, "
            "previous_set_weight_lbs, previous_set_weight_unit, state_seq, created_at_utc "
            f"FROM set_weight_history WHERE {where_sql} "
            "ORDER BY received_at_utc DESC, id DESC LIMIT ?;"
        )
        params.append(max(1, int(limit)))

        with self._conn() as conn:
            cur = conn.execute(sql, tuple(params))
            out: List[Dict[str, Any]] = []
            for row in cur.fetchall():
                out.append(
                    {
                        "id": int(row["id"]),
                        "received_at_utc": row["received_at_utc"],
                        "record_time_set_utc": row["record_time_set_utc"],
                        "line_id": row["line_id"],
                        "machine_id": row["machine_id"],
                        "set_weight_value": float(row["set_weight_value"]),
                        "set_weight_unit": row["set_weight_unit"],
                        "set_weight_lbs": float(row["set_weight_lbs"]),
                        "source": row["source"],
                        "source_event_id": row["source_event_id"],
                        "erp_timestamp_utc": row["erp_timestamp_utc"],
                        "product_id": row["product_id"],
                        "operator_id": row["operator_id"],
                        "job_id": row["job_id"],
                        "step_id": row["step_id"],
                        "metadata": self._parse_metadata_json(row["metadata_json"]),
                        "applied_to_current": bool(row["applied_to_current"]),
                        "duplicate_event": bool(row["duplicate_event"]),
                        "previous_set_weight_lbs": (
                            None
                            if row["previous_set_weight_lbs"] is None
                            else float(row["previous_set_weight_lbs"])
                        ),
                        "previous_set_weight_unit": row["previous_set_weight_unit"],
                        "state_seq": int(row["state_seq"] or 0),
                        "created_at_utc": row["created_at_utc"],
                    }
                )
            return out

    def get_job_lifecycle_state(
        self,
        *,
        line_id: str,
        machine_id: str,
    ) -> Optional[JobLifecycleStateRow]:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT line_id, machine_id, active_job_id, "
                "active_job_started_record_time_set_utc, active_job_last_record_time_set_utc, "
                "active_job_first_erp_timestamp_utc, active_job_last_erp_timestamp_utc, "
                "override_count, last_set_weight_lbs, last_set_weight_unit, "
                "last_source_event_id, updated_at_utc "
                "FROM job_lifecycle_state WHERE line_id = ? AND machine_id = ? LIMIT 1;",
                (line_id_clean, machine_id_clean),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return JobLifecycleStateRow(
            line_id=str(row["line_id"]),
            machine_id=str(row["machine_id"]),
            active_job_id=str(row["active_job_id"]),
            active_job_started_record_time_set_utc=str(
                row["active_job_started_record_time_set_utc"]
            ),
            active_job_last_record_time_set_utc=str(
                row["active_job_last_record_time_set_utc"]
            ),
            active_job_first_erp_timestamp_utc=self._clean_optional_text(
                row["active_job_first_erp_timestamp_utc"]
            ),
            active_job_last_erp_timestamp_utc=self._clean_optional_text(
                row["active_job_last_erp_timestamp_utc"]
            ),
            override_count=max(0, int(row["override_count"] or 0)),
            last_set_weight_lbs=(
                None
                if row["last_set_weight_lbs"] is None
                else float(row["last_set_weight_lbs"])
            ),
            last_set_weight_unit=self._clean_optional_text(row["last_set_weight_unit"]),
            last_source_event_id=self._clean_optional_text(row["last_source_event_id"]),
            updated_at_utc=str(row["updated_at_utc"]),
        )

    def set_job_lifecycle_state(
        self,
        *,
        line_id: str,
        machine_id: str,
        active_job_id: str,
        active_job_started_record_time_set_utc: str,
        active_job_last_record_time_set_utc: str,
        active_job_first_erp_timestamp_utc: Optional[str] = None,
        active_job_last_erp_timestamp_utc: Optional[str] = None,
        override_count: int = 0,
        last_set_weight_lbs: Optional[float] = None,
        last_set_weight_unit: Optional[str] = None,
        last_source_event_id: Optional[str] = None,
    ) -> None:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        active_job_id_clean = self._clean_required_text(active_job_id, "active_job_id")
        started_clean = str(active_job_started_record_time_set_utc or "").strip()
        last_clean = str(active_job_last_record_time_set_utc or "").strip()
        if not started_clean:
            raise ValueError("active_job_started_record_time_set_utc is required")
        if not last_clean:
            raise ValueError("active_job_last_record_time_set_utc is required")
        first_erp_clean = self._clean_optional_text(active_job_first_erp_timestamp_utc)
        last_erp_clean = self._clean_optional_text(active_job_last_erp_timestamp_utc)
        last_unit_clean = (
            None
            if last_set_weight_unit in (None, "")
            else self._normalize_weight_unit(last_set_weight_unit)
        )
        last_event_clean = self._clean_optional_text(last_source_event_id)
        updated_utc = _utc_now()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO job_lifecycle_state("
                "line_id, machine_id, active_job_id, "
                "active_job_started_record_time_set_utc, active_job_last_record_time_set_utc, "
                "active_job_first_erp_timestamp_utc, active_job_last_erp_timestamp_utc, "
                "override_count, last_set_weight_lbs, last_set_weight_unit, "
                "last_source_event_id, updated_at_utc"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(line_id, machine_id) DO UPDATE SET "
                "active_job_id=excluded.active_job_id, "
                "active_job_started_record_time_set_utc=excluded.active_job_started_record_time_set_utc, "
                "active_job_last_record_time_set_utc=excluded.active_job_last_record_time_set_utc, "
                "active_job_first_erp_timestamp_utc=excluded.active_job_first_erp_timestamp_utc, "
                "active_job_last_erp_timestamp_utc=excluded.active_job_last_erp_timestamp_utc, "
                "override_count=excluded.override_count, "
                "last_set_weight_lbs=excluded.last_set_weight_lbs, "
                "last_set_weight_unit=excluded.last_set_weight_unit, "
                "last_source_event_id=excluded.last_source_event_id, "
                "updated_at_utc=excluded.updated_at_utc;",
                (
                    line_id_clean,
                    machine_id_clean,
                    active_job_id_clean,
                    started_clean,
                    last_clean,
                    first_erp_clean,
                    last_erp_clean,
                    max(0, int(override_count)),
                    (
                        None
                        if last_set_weight_lbs is None
                        else float(last_set_weight_lbs)
                    ),
                    last_unit_clean,
                    last_event_clean,
                    updated_utc,
                ),
            )

    def increment_job_lifecycle_override(
        self,
        *,
        line_id: str,
        machine_id: str,
        last_record_time_set_utc: str,
        last_set_weight_lbs: Optional[float] = None,
        last_set_weight_unit: Optional[str] = None,
        last_source_event_id: Optional[str] = None,
        active_job_last_erp_timestamp_utc: Optional[str] = None,
    ) -> None:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        last_record_time_clean = str(last_record_time_set_utc or "").strip()
        if not last_record_time_clean:
            raise ValueError("last_record_time_set_utc is required")
        last_unit_clean = (
            None
            if last_set_weight_unit in (None, "")
            else self._normalize_weight_unit(last_set_weight_unit)
        )
        last_event_clean = self._clean_optional_text(last_source_event_id)
        last_erp_clean = self._clean_optional_text(active_job_last_erp_timestamp_utc)
        updated_utc = _utc_now()
        with self._conn() as conn:
            conn.execute(
                "UPDATE job_lifecycle_state SET "
                "override_count = override_count + 1, "
                "active_job_last_record_time_set_utc = ?, "
                "active_job_last_erp_timestamp_utc = COALESCE(?, active_job_last_erp_timestamp_utc), "
                "last_set_weight_lbs = COALESCE(?, last_set_weight_lbs), "
                "last_set_weight_unit = COALESCE(?, last_set_weight_unit), "
                "last_source_event_id = COALESCE(?, last_source_event_id), "
                "updated_at_utc = ? "
                "WHERE line_id = ? AND machine_id = ?;",
                (
                    last_record_time_clean,
                    last_erp_clean,
                    (
                        None
                        if last_set_weight_lbs is None
                        else float(last_set_weight_lbs)
                    ),
                    last_unit_clean,
                    last_event_clean,
                    updated_utc,
                    line_id_clean,
                    machine_id_clean,
                ),
            )

    def clear_job_lifecycle_state(self, *, line_id: str, machine_id: str) -> None:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM job_lifecycle_state WHERE line_id = ? AND machine_id = ?;",
                (line_id_clean, machine_id_clean),
            )

    def get_job_window_throughput_summary(
        self,
        *,
        start_utc: str,
        end_utc: str,
    ) -> Dict[str, Any]:
        start_clean = str(start_utc or "").strip()
        end_clean = str(end_utc or "").strip()
        if not start_clean or not end_clean:
            raise ValueError("start_utc and end_utc are required")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT "
                "COUNT(*) AS total_cycle_count, "
                "SUM(CASE WHEN dump_type IN ('full','end_of_lot') THEN 1 ELSE 0 END) AS dump_count, "
                "COALESCE(SUM(CASE WHEN dump_type IN ('full','end_of_lot') THEN processed_lbs ELSE 0.0 END), 0.0) AS total_processed_lbs, "
                "COALESCE(AVG(CASE WHEN dump_type IN ('full','end_of_lot') THEN processed_lbs END), 0.0) AS avg_weight_lbs, "
                "COALESCE(AVG(CASE WHEN dump_type IN ('full','end_of_lot') THEN duration_ms END), 0.0) AS avg_cycle_time_ms, "
                "COALESCE(AVG(CASE WHEN dump_type IN ('full','end_of_lot') THEN fill_time_ms END), 0.0) AS avg_fill_time_ms, "
                "COALESCE(AVG(CASE WHEN dump_type IN ('full','end_of_lot') THEN dump_time_ms END), 0.0) AS avg_dump_time_ms "
                "FROM throughput_events WHERE timestamp_utc >= ? AND timestamp_utc < ?;",
                (start_clean, end_clean),
            )
            row = cur.fetchone()
        if row is None:
            return {
                "cycle_count": 0,
                "dump_count": 0,
                "total_processed_lbs": 0.0,
                "avg_weight_lbs": 0.0,
                "avg_cycle_time_ms": 0.0,
                "avg_fill_time_ms": 0.0,
                "avg_dump_time_ms": 0.0,
            }
        return {
            "cycle_count": int(row["total_cycle_count"] or 0),
            "dump_count": int(row["dump_count"] or 0),
            "total_processed_lbs": float(row["total_processed_lbs"] or 0.0),
            "avg_weight_lbs": float(row["avg_weight_lbs"] or 0.0),
            "avg_cycle_time_ms": float(row["avg_cycle_time_ms"] or 0.0),
            "avg_fill_time_ms": float(row["avg_fill_time_ms"] or 0.0),
            "avg_dump_time_ms": float(row["avg_dump_time_ms"] or 0.0),
        }

    def get_job_window_hopper_load_times(
        self,
        *,
        start_utc: str,
        end_utc: str,
    ) -> list:
        start_clean = str(start_utc or "").strip()
        end_clean = str(end_utc or "").strip()
        if not start_clean or not end_clean:
            raise ValueError("start_utc and end_utc are required")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT fill_time_ms FROM throughput_events "
                "WHERE timestamp_utc >= ? AND timestamp_utc < ? "
                "AND dump_type IN ('full','end_of_lot') "
                "AND fill_time_ms IS NOT NULL "
                "ORDER BY timestamp_utc ASC;",
                (start_clean, end_clean),
            )
            rows = cur.fetchall()
        return [int(r["fill_time_ms"]) for r in rows]

    def get_counted_events_in_window(
        self,
        *,
        event_type: str,
        line_id: str,
        machine_id: str,
        start_utc: str,
        end_utc: str,
    ) -> list:
        event_type_clean = self._clean_required_text(event_type, "event_type")
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        start_clean = str(start_utc or "").strip()
        end_clean = str(end_utc or "").strip()
        if not start_clean or not end_clean:
            raise ValueError("start_utc and end_utc are required")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT id, timestamp_utc FROM counted_events "
                "WHERE event_type = ? AND line_id = ? AND machine_id = ? "
                "AND timestamp_utc >= ? AND timestamp_utc < ? "
                "ORDER BY timestamp_utc ASC;",
                (event_type_clean, line_id_clean, machine_id_clean, start_clean, end_clean),
            )
            rows = cur.fetchall()
        return [{"id": int(r["id"]), "timestamp_utc": str(r["timestamp_utc"])} for r in rows]

    def record_counted_event(
        self,
        *,
        timestamp_utc: Optional[str] = None,
        event_type: str,
        source: str,
        line_id: str,
        machine_id: str,
        source_channel: Optional[int] = None,
    ) -> int:
        timestamp_clean = str(timestamp_utc or _utc_now()).strip()
        event_type_clean = self._clean_required_text(event_type, "event_type")
        source_clean = self._clean_required_text(source, "source")
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        created_at = _utc_now()
        source_channel_value = (
            None if source_channel is None else max(1, int(source_channel))
        )
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO counted_events("
                "timestamp_utc, event_type, source, source_channel, line_id, machine_id, created_at"
                ") VALUES (?,?,?,?,?,?,?);",
                (
                    timestamp_clean,
                    event_type_clean,
                    source_clean,
                    source_channel_value,
                    line_id_clean,
                    machine_id_clean,
                    created_at,
                ),
            )
            return int(cur.lastrowid or 0)

    def get_job_window_counted_event_summary(
        self,
        *,
        line_id: str,
        machine_id: str,
        start_utc: str,
        end_utc: str,
    ) -> Dict[str, int]:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        start_clean = str(start_utc or "").strip()
        end_clean = str(end_utc or "").strip()
        if not start_clean or not end_clean:
            raise ValueError("start_utc and end_utc are required")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT event_type, COUNT(*) AS event_count "
                "FROM counted_events "
                "WHERE line_id = ? AND machine_id = ? "
                "AND timestamp_utc >= ? AND timestamp_utc < ? "
                "GROUP BY event_type;",
                (line_id_clean, machine_id_clean, start_clean, end_clean),
            )
            rows = cur.fetchall()
        return {
            str(row["event_type"]): int(row["event_count"] or 0)
            for row in rows
            if str(row["event_type"] or "").strip()
        }

    def get_job_window_set_weight_summary(
        self,
        *,
        line_id: str,
        machine_id: str,
        job_id: str,
        start_utc: str,
        end_utc: str,
    ) -> Dict[str, Any]:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        job_id_clean = self._clean_required_text(job_id, "job_id")
        start_clean = str(start_utc or "").strip()
        end_clean = str(end_utc or "").strip()
        if not start_clean or not end_clean:
            raise ValueError("start_utc and end_utc are required")
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT "
                "SUM(CASE WHEN source LIKE 'manual_override:%' THEN 1 ELSE 0 END) AS override_count "
                "FROM set_weight_history "
                "WHERE line_id = ? AND machine_id = ? "
                "AND record_time_set_utc >= ? AND record_time_set_utc < ? "
                "AND (job_id = ? OR source LIKE 'manual_override:%');",
                (
                    line_id_clean,
                    machine_id_clean,
                    start_clean,
                    end_clean,
                    job_id_clean,
                ),
            )
            count_row = cur.fetchone()
            cur = conn.execute(
                "SELECT set_weight_lbs, set_weight_unit, record_time_set_utc "
                "FROM set_weight_history "
                "WHERE line_id = ? AND machine_id = ? "
                "AND record_time_set_utc >= ? AND record_time_set_utc < ? "
                "AND (job_id = ? OR source LIKE 'manual_override:%') "
                "ORDER BY record_time_set_utc DESC, id DESC LIMIT 1;",
                (
                    line_id_clean,
                    machine_id_clean,
                    start_clean,
                    end_clean,
                    job_id_clean,
                ),
            )
            last_row = cur.fetchone()

        return {
            "override_count": int((count_row["override_count"] if count_row else 0) or 0),
            "final_set_weight_lbs": (
                None if last_row is None else float(last_row["set_weight_lbs"])
            ),
            "final_set_weight_unit": (
                None if last_row is None else str(last_row["set_weight_unit"])
            ),
            "final_set_weight_record_time_set_utc": (
                None if last_row is None else str(last_row["record_time_set_utc"])
            ),
        }

    def enqueue_job_completion_outbox(
        self,
        *,
        line_id: str,
        machine_id: str,
        job_id: str,
        job_start_record_time_set_utc: str,
        job_end_record_time_set_utc: str,
        payload: Dict[str, Any],
    ) -> int:
        line_id_clean = self._clean_required_text(line_id, "line_id")
        machine_id_clean = self._clean_required_text(machine_id, "machine_id")
        job_id_clean = self._clean_required_text(job_id, "job_id")
        start_clean = str(job_start_record_time_set_utc or "").strip()
        end_clean = str(job_end_record_time_set_utc or "").strip()
        if not start_clean:
            raise ValueError("job_start_record_time_set_utc is required")
        if not end_clean:
            raise ValueError("job_end_record_time_set_utc is required")
        created_utc = _utc_now()
        payload_json = json.dumps(payload or {}, sort_keys=True)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO job_completion_outbox("
                "created_at_utc, line_id, machine_id, job_id, "
                "job_start_record_time_set_utc, job_end_record_time_set_utc, payload_json, "
                "status, attempt_count, next_retry_at_utc"
                ") VALUES (?,?,?,?,?,?,?,?,?,?);",
                (
                    created_utc,
                    line_id_clean,
                    machine_id_clean,
                    job_id_clean,
                    start_clean,
                    end_clean,
                    payload_json,
                    "pending",
                    0,
                    created_utc,
                ),
            )
            inserted = int(cur.lastrowid or 0)
            if inserted > 0:
                return inserted
            cur = conn.execute(
                "SELECT id FROM job_completion_outbox "
                "WHERE line_id = ? AND machine_id = ? AND job_id = ? "
                "AND job_start_record_time_set_utc = ? AND job_end_record_time_set_utc = ? "
                "LIMIT 1;",
                (line_id_clean, machine_id_clean, job_id_clean, start_clean, end_clean),
            )
            row = cur.fetchone()
            return int(row["id"]) if row else 0

    def get_pending_job_completion_outbox(
        self,
        *,
        now_utc: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        now_clean = str(now_utc or _utc_now())
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT id, created_at_utc, line_id, machine_id, job_id, "
                "job_start_record_time_set_utc, job_end_record_time_set_utc, "
                "payload_json, status, attempt_count, next_retry_at_utc, "
                "last_attempt_at_utc, last_error, sent_at_utc "
                "FROM job_completion_outbox "
                "WHERE status = 'pending' AND next_retry_at_utc <= ? "
                "ORDER BY id ASC LIMIT ?;",
                (now_clean, max(1, int(limit))),
            )
            rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "id": int(row["id"]),
                    "created_at_utc": row["created_at_utc"],
                    "line_id": row["line_id"],
                    "machine_id": row["machine_id"],
                    "job_id": row["job_id"],
                    "job_start_record_time_set_utc": row["job_start_record_time_set_utc"],
                    "job_end_record_time_set_utc": row["job_end_record_time_set_utc"],
                    "payload": self._parse_metadata_json(row["payload_json"]),
                    "status": row["status"],
                    "attempt_count": int(row["attempt_count"] or 0),
                    "next_retry_at_utc": row["next_retry_at_utc"],
                    "last_attempt_at_utc": row["last_attempt_at_utc"],
                    "last_error": row["last_error"],
                    "sent_at_utc": row["sent_at_utc"],
                }
            )
        return out

    def mark_job_completion_outbox_sent(
        self,
        *,
        outbox_id: int,
        sent_at_utc: Optional[str] = None,
    ) -> None:
        sent_ts = str(sent_at_utc or _utc_now())
        with self._conn() as conn:
            conn.execute(
                "UPDATE job_completion_outbox SET "
                "status = 'sent', "
                "sent_at_utc = ?, "
                "last_attempt_at_utc = ?, "
                "last_error = NULL "
                "WHERE id = ?;",
                (sent_ts, sent_ts, int(outbox_id)),
            )

    def mark_job_completion_outbox_retry(
        self,
        *,
        outbox_id: int,
        last_error: str,
        next_retry_at_utc: str,
        attempted_at_utc: Optional[str] = None,
    ) -> None:
        attempted_ts = str(attempted_at_utc or _utc_now())
        next_retry_ts = str(next_retry_at_utc or attempted_ts)
        with self._conn() as conn:
            conn.execute(
                "UPDATE job_completion_outbox SET "
                "attempt_count = attempt_count + 1, "
                "last_attempt_at_utc = ?, "
                "last_error = ?, "
                "next_retry_at_utc = ? "
                "WHERE id = ?;",
                (
                    attempted_ts,
                    str(last_error or "")[:1000],
                    next_retry_ts,
                    int(outbox_id),
                ),
            )

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
            # Physical stack: Pi → DAC (stack 0) → MegaIND (stack 2)
            # Board address: 0x52 (base 0x50 + stack 2), verified 2026-02-15
            "megaind": {
                "stack_level": 2,
            },
            # Scale calibration
            "scale": {
                "zero_offset_mv": 0.0,           # Canonical zero offset (signal domain)
                "zero_offset_lbs": 0.0,          # Derived compatibility field
                "zero_offset_signal": 0.0,       # Legacy alias for zero_offset_mv
                "zero_offset_updated_utc": None,
                "tare_offset_lbs": 0.0,
                "last_tare_utc": None,
                # Safety gate: hardware DI noise can look like button presses.
                "allow_opto_tare": False,
                "zero_target_lb": 0.0,
                "rezero_warning_threshold_lb": 20.0,
            },
            # Automatic near-zero drift compensation
            "zero_tracking": {
                "enabled": True,
                # Industrial-style AZT (Automatic Zero Tracking):
                # micro range near zero, slow rate, stable-only (enforced in runtime).
                "range_lb": 0.05,
                "deadband_lb": 0.02,
                "hold_s": 1.0,
                "rate_lbs": 0.05,
                "persist_interval_s": 1.0,
                # Post-dump re-zero (event-driven, one-shot capture after each cycle).
                "post_dump_enabled": True,
                "post_dump_min_delay_s": 5.0,
                "post_dump_window_s": 10.0,
                "post_dump_empty_threshold_lb": 4.0,
                "post_dump_max_correction_lb": 8.0,
            },
            # Physical button actions (opto inputs on MegaIND)
            "opto_actions": {
                "1": "none",
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
                "stability_threshold": 1.5,
                "stability_stddev_lb": 1.5,
                "stability_slope_lbs": 3.0,
            },
            # Startup output behavior
            "startup": {
                "delay_s": 0.0,
                "output_value": 0.0,
                "auto_arm": False,
                "auto_zero": False,
                # Hopper safety gate:
                # require one operator-confirmed manual ZERO after boot
                # before automatic zero logic is allowed.
                "require_manual_zero_before_auto_zero": True,
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
            # Webhook-driven job target control.
            # Legacy behavior remains default ("legacy_weight_mapping").
            "job_control": {
                "enabled": False,
                "mode": "legacy_weight_mapping",
                "trigger_mode": "exact",
                # Optional fixed output to hold while legacy mode is at/below
                # the configured floor threshold. When None, follow the PLC
                # profile's mapped output at the floor weight.
                "legacy_floor_signal_value": None,
                # Fixed output signal to send when scale_weight >= set_weight.
                # Units follow output.mode (V for 0-10V, mA for 4-20mA).
                "trigger_signal_value": 1.0,
                # Output value when scale_weight < set_weight (idle).
                "low_signal_value": 0.0,
                # Trigger early by this many pounds (trigger at set_weight - pretrigger_lb).
                "pretrigger_lb": 0.0,
                # Optional shared secret for /api/job/webhook.
                "webhook_token": "",
                # Destination URL for completed-job summary webhook POSTs.
                "completed_job_webhook_url": "",
                # Dispatcher runtime settings for durable outbox delivery.
                "completed_job_webhook_timeout_s": 5.0,
                "completed_job_webhook_dispatch_interval_s": 2.0,
                "completed_job_webhook_retry_min_s": 5.0,
                "completed_job_webhook_retry_max_s": 300.0,
                # SHA-256 hash of 4-digit manager PIN for manual HDMI overrides.
                "override_pin_hash": "",
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
        target_set_weight_lbs: Optional[float] = None,
        dump_type: Optional[str] = None,
        fill_time_ms: Optional[int] = None,
        dump_time_ms: Optional[int] = None,
    ) -> int:
        ts_utc = str(timestamp_utc or _utc_now())
        created_at = _utc_now()
        inserted_id = 0
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO throughput_events("
                "timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms, confidence, device_id, "
                "hopper_id, target_set_weight_lbs, dump_type, fill_time_ms, dump_time_ms, created_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);",
                (
                    ts_utc,
                    float(processed_lbs),
                    (None if full_lbs is None else float(full_lbs)),
                    (None if empty_lbs is None else float(empty_lbs)),
                    (None if duration_ms is None else int(duration_ms)),
                    (None if confidence is None else float(confidence)),
                    (None if device_id is None else str(device_id)),
                    (None if hopper_id is None else str(hopper_id)),
                    (None if target_set_weight_lbs is None else float(target_set_weight_lbs)),
                    (None if dump_type is None else str(dump_type)),
                    (None if fill_time_ms is None else int(fill_time_ms)),
                    (None if dump_time_ms is None else int(dump_time_ms)),
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
                "confidence, device_id, hopper_id, target_set_weight_lbs, dump_type, created_at "
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
                        "target_set_weight_lbs": (
                            None
                            if row["target_set_weight_lbs"] is None
                            else float(row["target_set_weight_lbs"])
                        ),
                        "dump_type": row["dump_type"],
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
                "confidence, device_id, hopper_id, target_set_weight_lbs, dump_type, created_at "
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
                        "target_set_weight_lbs": (
                            None
                            if row["target_set_weight_lbs"] is None
                            else float(row["target_set_weight_lbs"])
                        ),
                        "dump_type": row["dump_type"],
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

    def record_dump_and_increment_totals(
        self,
        prev_stable_lbs: float,
        new_stable_lbs: float,
        processed_lbs: float,
        target_set_weight_lbs: Optional[float] = None,
        dump_type: Optional[str] = None,
    ) -> None:
        ts = _utc_now()
        processed_lbs = float(processed_lbs)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO production_dumps("
                "ts, prev_stable_lbs, new_stable_lbs, processed_lbs, target_set_weight_lbs, dump_type"
                ") VALUES (?,?,?,?,?,?);",
                (
                    ts,
                    float(prev_stable_lbs),
                    float(new_stable_lbs),
                    processed_lbs,
                    (None if target_set_weight_lbs is None else float(target_set_weight_lbs)),
                    (None if dump_type is None else str(dump_type)),
                ),
            )

            if dump_type == "empty":
                return

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
                "SELECT COUNT(*) as cnt FROM production_dumps "
                "WHERE ts >= ? AND ts <= ? AND (dump_type IS NULL OR dump_type = 'full');",
                (start_ts, end_ts),
            )
            row = cur.fetchone()
            return int(row["cnt"]) if row else 0

    def get_last_dump(self) -> Optional[Dict[str, Any]]:
        """Get the most recent dump record."""
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT ts, prev_stable_lbs, new_stable_lbs, processed_lbs, "
                "target_set_weight_lbs, dump_type "
                "FROM production_dumps ORDER BY id DESC LIMIT 1;"
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "ts": row["ts"],
                "prev_stable_lbs": float(row["prev_stable_lbs"]),
                "new_stable_lbs": float(row["new_stable_lbs"]),
                "processed_lbs": float(row["processed_lbs"]),
                "target_set_weight_lbs": (
                    None
                    if row["target_set_weight_lbs"] is None
                    else float(row["target_set_weight_lbs"])
                ),
                "dump_type": row["dump_type"],
            }


