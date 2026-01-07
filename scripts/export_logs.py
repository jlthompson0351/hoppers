from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.db.repo import AppRepository


def main() -> int:
    p = argparse.ArgumentParser(description="Export recent events from the transmitter SQLite DB.")
    p.add_argument("--db", default="var/data/app.sqlite3", help="Path to SQLite database")
    p.add_argument("--limit", type=int, default=5000, help="Max events to export")
    p.add_argument("--out", default="var/export/events.json", help="Output file path (.json or .csv)")
    args = p.parse_args()

    repo = AppRepository(Path(args.db))
    events = repo.get_recent_events(limit=args.limit)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == ".csv":
        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["ts", "level", "code", "message", "details_json"])
            w.writeheader()
            for e in events:
                w.writerow(
                    {
                        "ts": e["ts"],
                        "level": e["level"],
                        "code": e["code"],
                        "message": e["message"],
                        "details_json": json.dumps(e.get("details") or {}),
                    }
                )
    else:
        out_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(f"Wrote {len(events)} events to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


