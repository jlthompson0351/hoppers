from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from src.db.schema import DDL_V1, SCHEMA_VERSION

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

        conn.commit()
        final = _get_version(conn)
        if final != SCHEMA_VERSION:
            raise RuntimeError(f"DB migration incomplete: have {final}, expected {SCHEMA_VERSION}.")
    finally:
        conn.close()


