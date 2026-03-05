import sqlite3
from datetime import datetime

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("=" * 60)
print("DUMP-TO-DUMP CYCLE TIME - CLEAN DATA")
print("Filters:")
print("  - Only dumps with > 100 lbs processed")
print("  - Cycle must be 1-10 min (removes noise/downtime)")
print("=" * 60)

cursor.execute("""
    SELECT id, ts, prev_stable_lbs, new_stable_lbs, processed_lbs
    FROM production_dumps
    WHERE processed_lbs > 100
    ORDER BY id ASC
""")

rows = cursor.fetchall()

all_cycles = []
by_day = {}

for i in range(1, len(rows)):
    curr = rows[i]
    prev = rows[i - 1]
    curr_dt = datetime.fromisoformat(curr[1].replace('+00:00', ''))
    prev_dt = datetime.fromisoformat(prev[1].replace('+00:00', ''))
    gap_sec = (curr_dt - prev_dt).total_seconds()
    gap_min = gap_sec / 60

    if gap_min < 1.0 or gap_min > 10.0:
        continue

    day = curr_dt.strftime('%Y-%m-%d')
    if day not in by_day:
        by_day[day] = []
    by_day[day].append(gap_min)
    all_cycles.append(gap_min)

print(f"\nValid cycles: {len(all_cycles)}")
print(f"\nDAILY AVERAGES:")
print(f"{'Date':>12} | {'Avg':>8} | {'Count':>5}")
print("-" * 35)
for day in sorted(by_day.keys()):
    gaps = by_day[day]
    avg = sum(gaps) / len(gaps)
    print(f"{day} | {avg:.2f} min | {len(gaps):5d}")

if all_cycles:
    s = sorted(all_cycles)
    med = s[len(s)//2]
    print("-" * 35)
    print(f"\n{'='*60}")
    print(f"OVERALL AVERAGE CYCLE TIME: {sum(all_cycles)/len(all_cycles):.2f} min")
    print(f"MEDIAN CYCLE TIME:          {med:.2f} min")
    print(f"RANGE:                      {min(all_cycles):.2f} - {max(all_cycles):.2f} min")
    print(f"TOTAL CYCLES:               {len(all_cycles)}")
    print(f"{'='*60}")
