import sqlite3
from datetime import datetime

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("CYCLE TIMES FOR DUMPS WITH ACTUAL WEIGHT")
print("=" * 60)

# Get throughput events where processed weight > 100 lbs (real production)
cursor.execute("""
    SELECT id, timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms
    FROM throughput_events 
    WHERE processed_lbs > 100
    ORDER BY id DESC LIMIT 100
""")

rows = cursor.fetchall()

if not rows:
    print("No records found with weight > 100 lbs")
    conn.close()
    exit()

durations_sec = []
print(f"\nLast {len(rows)} dumps with >100 lbs processed:")
print("-" * 60)

for row in rows[:30]:  # Show last 30
    id_, ts, processed, full, empty, duration_ms = row
    duration_sec = duration_ms / 1000
    duration_min = duration_sec / 60
    durations_sec.append(duration_sec)
    dt = datetime.fromisoformat(ts.replace('+00:00', ''))
    print(f"{dt.strftime('%H:%M')} | {duration_min:.1f} min | {processed:.0f} lb")

print("-" * 60)
print(f"\nSUMMARY FOR REAL PRODUCTION DUMPS:")
print(f"  Count: {len(durations_sec)} cycles")
print(f"  Fastest: {min(durations_sec)/60:.1f} min ({min(durations_sec):.0f} sec)")
print(f"  Slowest: {max(durations_sec)/60:.1f} min ({max(durations_sec):.0f} sec)")
print(f"  Average: {sum(durations_sec)/len(durations_sec)/60:.1f} min")

# Median
sorted_dur = sorted(durations_sec)
median = sorted_dur[len(sorted_dur)//2] / 60
print(f"  Median:  {median:.1f} min")
