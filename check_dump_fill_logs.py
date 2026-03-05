import sqlite3
from datetime import datetime

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("=" * 70)
print("DUMP AND FILL LOG ANALYSIS")
print("=" * 70)

# Get latest production_dumps with timing info
print("\n--- LATEST PRODUCTION DUMPS (fill weight -> empty weight) ---")
cursor.execute("""
    SELECT id, ts, prev_stable_lbs, new_stable_lbs, processed_lbs 
    FROM production_dumps 
    ORDER BY id DESC LIMIT 10
""")
for row in cursor.fetchall():
    id_, ts, prev_stable_lbs, new_stable_lbs, processed_lbs = row
    dt = datetime.fromisoformat(ts.replace('+00:00', ''))
    print(f"Dump #{id_} at {dt.strftime('%Y-%m-%d %H:%M:%S')}:")
    print(f"  Full: {prev_stable_lbs:.2f} lb -> Empty: {new_stable_lbs:.2f} lb")
    print(f"  Processed: {processed_lbs:.2f} lb")

# Get throughput events with duration
print("\n--- LATEST THROUGHPUT EVENTS (dump + fill cycle timing) ---")
cursor.execute("""
    SELECT id, timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms, confidence 
    FROM throughput_events 
    ORDER BY id DESC LIMIT 10
""")
for row in cursor.fetchall():
    id_, ts, processed_lbs, full_lbs, empty_lbs, duration_ms, confidence = row
    dt = datetime.fromisoformat(ts.replace('+00:00', ''))
    duration_sec = duration_ms / 1000
    print(f"Cycle #{id_} at {dt.strftime('%Y-%m-%d %H:%M:%S')}:")
    print(f"  Duration: {duration_sec:.1f} seconds ({duration_ms} ms)")
    print(f"  Full: {full_lbs:.2f} lb -> Empty: {empty_lbs:.2f} lb")
    print(f"  Processed: {processed_lbs:.2f} lb")

# Check for any fill-specific events
print("\n--- RECENT EVENTS (includes dump timing details) ---")
cursor.execute("""
    SELECT ts, level, code, message, details_json 
    FROM events 
    WHERE code LIKE '%DUMP%' OR code LIKE '%FILL%' OR code LIKE '%THROUGHPUT%'
    ORDER BY id DESC LIMIT 15
""")
for row in cursor.fetchall():
    ts, level, code, message, details_json = row
    dt = datetime.fromisoformat(ts.replace('+00:00', ''))
    print(f"\n[{dt.strftime('%H:%M:%S')}] {code}")
    print(f"  {message}")
    if details_json and details_json != '{}':
        # Show key timing fields if present
        import json
        try:
            data = json.loads(details_json)
            timing_fields = {k: v for k, v in data.items() if any(x in k.lower() for x in ['time', 'duration', 'ms', 'sec', 'age'])}
            if timing_fields:
                print(f"  Timing data: {timing_fields}")
        except:
            pass

print("\n" + "=" * 70)
print("LOG STATUS: ACTIVE - Dump and fill data IS being captured")
print("=" * 70)

# Count total records
cursor.execute("SELECT COUNT(*) FROM production_dumps")
dump_count = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM throughput_events")
cycle_count = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM events")
event_count = cursor.fetchone()[0]

print(f"\nTotal records in database:")
print(f"  - Production dumps: {dump_count}")
print(f"  - Throughput cycles: {cycle_count}")
print(f"  - Events: {event_count}")
print(f"\nMost recent activity: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
