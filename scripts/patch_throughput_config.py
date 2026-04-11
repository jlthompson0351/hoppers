#!/usr/bin/env python3
"""
One-shot config patch: update throughput timing defaults in the live Pi SQLite DB.
Run BEFORE restarting the loadcell-transmitter service.

Changes:
  - full_stability_s:    0.4 → 5.0  (conveyor fill takes 30-90+ sec minimum)
  - empty_confirm_s:     0.3 → 2.0  (dump needs physical time to complete)
  - full_pct_of_target:  (new) 0.80 (declare full at 80% of ERP set weight)
"""
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("/var/lib/loadcell-transmitter/data/app.sqlite3")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "+00:00")


def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT id, ts, config_json FROM config_versions ORDER BY ts DESC LIMIT 1;"
    ).fetchone()

    if row is None:
        print("ERROR: No config_versions rows found", file=sys.stderr)
        sys.exit(1)

    cfg = json.loads(row["config_json"])
    throughput = cfg.setdefault("throughput", {})

    old_full_stability = throughput.get("full_stability_s")
    old_empty_confirm = throughput.get("empty_confirm_s")

    throughput["full_stability_s"] = 5.0
    throughput["empty_confirm_s"] = 2.0
    throughput["full_pct_of_target"] = 0.80

    new_json = json.dumps(cfg)
    ts = utc_now()

    conn.execute(
        "INSERT INTO config_versions(ts, config_json) VALUES (?, ?);",
        (ts, new_json),
    )
    conn.commit()
    conn.close()

    print("✅ Config patch applied successfully:")
    print(f"   full_stability_s:   {old_full_stability} → 5.0")
    print(f"   empty_confirm_s:    {old_empty_confirm} → 2.0")
    print(f"   full_pct_of_target: (new) 0.80")
    print(f"   Written to config_versions at {ts}")
    print()
    print("Now restart the service:")
    print("   sudo systemctl restart loadcell-transmitter")


if __name__ == "__main__":
    main()
