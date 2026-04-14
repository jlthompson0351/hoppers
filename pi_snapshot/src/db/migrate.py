from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from src.db.schema import DDL_V1, DDL_V2, DDL_V3, DDL_V4, DDL_V5, DDL_V6, DDL_V7, DDL_V8, SCHEMA_VERSION

log = logging.getLogger(__name__)


def _get_version(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
    )
    if cur.fetchone() is None:
        return 0
    cur = conn.execute("SELECT version FROM schema_version LIMIT 1;")
    row = cur.fetchone()
    if row is None:
        return 0
    return int(row[0])


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("DELETE FROM schema_version;")
    conn.execute("INSERT INTO schema_version(version) VALUES (?);", (int(version),))


def _has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table_name});")
    for row in cur.fetchall():
        if str(row[1]) == str(column_name):
            return True
    return False


def ensure_db(db_path: Path) -> None:
    """Ensure database exists and is migrated to latest schema version."""

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        current = _get_version(conn)
        if current == SCHEMA_VERSION:
            return
        if current > SCHEMA_VERSION:
            raise RuntimeError(f"DB schema {current} is newer than app supports ({SCHEMA_VERSION}).")

        # Migrations (scaffold only has v1)
        if current < 1:
            log.info("Applying DB schema v1...")
            conn.executescript(DDL_V1)
            _set_version(conn, 1)

        if current < 2:
            log.info("Applying DB schema v2...")
            conn.executescript(DDL_V2)
            _set_version(conn, 2)

        if current < 3:
            log.info("Applying DB schema v3...")
            conn.executescript(DDL_V3)
            _set_version(conn, 3)

        if current < 4:
            log.info("Applying DB schema v4...")
            if not _has_column(conn, "throughput_events", "target_set_weight_lbs"):
                conn.execute("ALTER TABLE throughput_events ADD COLUMN target_set_weight_lbs REAL;")
            if not _has_column(conn, "production_dumps", "target_set_weight_lbs"):
                conn.execute("ALTER TABLE production_dumps ADD COLUMN target_set_weight_lbs REAL;")
            conn.executescript(DDL_V4)
            _set_version(conn, 4)

        if current < 5:
            log.info("Applying DB schema v5...")
            if not _has_column(conn, "throughput_events", "dump_type"):
                conn.execute("ALTER TABLE throughput_events ADD COLUMN dump_type TEXT;")
            if not _has_column(conn, "production_dumps", "dump_type"):
                conn.execute("ALTER TABLE production_dumps ADD COLUMN dump_type TEXT;")
            conn.executescript(DDL_V5)
            _set_version(conn, 5)

        if current < 6:
            log.info("Applying DB schema v6...")
            if not _has_column(conn, "set_weight_current", "record_time_set_utc"):
                conn.execute("ALTER TABLE set_weight_current ADD COLUMN record_time_set_utc TEXT;")
            conn.execute(
                "UPDATE set_weight_current "
                "SET record_time_set_utc = COALESCE(record_time_set_utc, received_at_utc, updated_at_utc);"
            )
            if not _has_column(conn, "set_weight_history", "record_time_set_utc"):
                conn.execute("ALTER TABLE set_weight_history ADD COLUMN record_time_set_utc TEXT;")
            conn.execute(
                "UPDATE set_weight_history "
                "SET record_time_set_utc = COALESCE(record_time_set_utc, received_at_utc, created_at_utc);"
            )
            conn.executescript(DDL_V6)
            _set_version(conn, 6)

        if current < 7:
            log.info("Applying DB schema v7...")
            conn.executescript(DDL_V7)
            _set_version(conn, 7)

        if current < 8:
            log.info("Applying DB schema v8...")
            if not _has_column(conn, "throughput_events", "fill_time_ms"):
                conn.execute("ALTER TABLE throughput_events ADD COLUMN fill_time_ms INTEGER;")
            if not _has_column(conn, "throughput_events", "dump_time_ms"):
                conn.execute("ALTER TABLE throughput_events ADD COLUMN dump_time_ms INTEGER;")
            conn.executescript(DDL_V8)
            _set_version(conn, 8)

        conn.commit()
        final = _get_version(conn)
        if final != SCHEMA_VERSION:
            raise RuntimeError(f"DB migration incomplete: have {final}, expected {SCHEMA_VERSION}.")
    finally:
        conn.close()


