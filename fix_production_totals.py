#!/usr/bin/env python3
"""Fix production_totals to match throughput_events after deletions."""

import sqlite3
from datetime import date, datetime
from pathlib import Path

def period_start(d: date, period_type: str) -> str:
    if period_type == "day":
        return d.isoformat()
    if period_type == "week":
        start = d.fromordinal(d.toordinal() - d.weekday())
        return start.isoformat()
    if period_type == "month":
        return date(d.year, d.month, 1).isoformat()
    if period_type == "year":
        return date(d.year, 1, 1).isoformat()
    raise ValueError(f"Unknown period_type: {period_type}")

def main():
    # Find database
    db_paths = [
        Path("var/data/app.sqlite3"),
        Path("/var/lib/loadcell-transmitter/data/app.sqlite3"),
        Path("/opt/loadcell-transmitter/var/data/app.sqlite3"),
    ]
    
    db_path = None
    for path in db_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print("❌ Database not found. Checked:")
        for path in db_paths:
            print(f"  - {path}")
        return 1
    
    print(f"📂 Using database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Get all throughput events
    cur = conn.execute("SELECT timestamp_utc, processed_lbs FROM throughput_events ORDER BY timestamp_utc")
    events = cur.fetchall()
    
    print(f"📊 Found {len(events)} throughput events")
    
    # Calculate correct totals by period
    correct_totals = {}
    for event in events:
        timestamp_utc = event["timestamp_utc"]
        processed_lbs = float(event["processed_lbs"])
        
        try:
            dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
            event_date = dt.date()
        except (ValueError, AttributeError):
            continue
        
        for period_type in ["day", "week", "month", "year"]:
            ps = period_start(event_date, period_type)
            key = (period_type, ps)
            correct_totals[key] = correct_totals.get(key, 0.0) + processed_lbs
    
    print(f"✅ Calculated correct totals for {len(correct_totals)} periods")
    
    # Update production_totals
    updated = 0
    for (period_type, ps), correct_total in correct_totals.items():
        # Get current value
        cur = conn.execute(
            "SELECT total_lbs FROM production_totals WHERE period_type=? AND period_start=?",
            (period_type, ps)
        )
        row = cur.fetchone()
        current_total = float(row["total_lbs"]) if row else 0.0
        
        if abs(current_total - correct_total) > 0.01:
            print(f"  Fixing {period_type} {ps}: {current_total:.1f} → {correct_total:.1f} lb")
            conn.execute(
                "INSERT INTO production_totals(period_type, period_start, total_lbs) VALUES (?,?,?) "
                "ON CONFLICT(period_type, period_start) DO UPDATE SET total_lbs = excluded.total_lbs",
                (period_type, ps, correct_total)
            )
            updated += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ Updated {updated} production_totals records")
    print("✅ Production totals now match throughput_events!")
    
    return 0

if __name__ == "__main__":
    exit(main())
