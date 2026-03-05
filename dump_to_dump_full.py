import sqlite3
from datetime import datetime

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("=" * 60)
print("DUMP-TO-DUMP CYCLE TIME - FULL HISTORY")
print("Only dumps with > 100 lbs processed")
print("Gaps > 10 min excluded (downtime/shift)")
print("=" * 60)

cursor.execute("""
    SELECT id, ts, prev_stable_lbs, new_stable_lbs, processed_lbs
    FROM production_dumps
    WHERE processed_lbs > 100
    ORDER BY id ASC
""")

rows = cursor.fetchall()
print(f"\nTotal production dumps with weight: {len(rows)}")

all_cycles = []
by_day = {}

for i in range(1, len(rows)):
    curr = rows[i]
    prev = rows[i - 1]
    curr_dt = datetime.fromisoformat(curr[1].replace('+00:00', ''))
    prev_dt = datetime.fromisoformat(prev[1].replace('+00:00', ''))
    gap_sec = (curr_dt - prev_dt).total_seconds()
    gap_min = gap_sec / 60

    if gap_sec > 600:
        continue

    day = curr_dt.strftime('%Y-%m-%d')
    if day not in by_day:
        by_day[day] = []
    by_day[day].append(gap_min)
    all_cycles.append(gap_min)

print(f"Valid consecutive cycles: {len(all_cycles)}")

print(f"\nDAILY AVERAGES:")
print(f"{'Date':>12} | {'Avg':>6} | {'Med':>6} | {'Count':>5}")
print("-" * 45)
for day in sorted(by_day.keys()):
    gaps = by_day[day]
    avg = sum(gaps) / len(gaps)
    s = sorted(gaps)
    med = s[len(s)//2]
    print(f"{day} | {avg:.2f} | {med:.2f} | {len(gaps):5d}")

if all_cycles:
    s = sorted(all_cycles)
    med = s[len(s)//2]
    print("-" * 45)
    print(f"\nOVERALL RESULTS:")
    print(f"  Total cycles:  {len(all_cycles)}")
    print(f"  Shortest:      {min(all_cycles):.2f} min")
    print(f"  Longest:       {max(all_cycles):.2f} min")
    print(f"  Average:       {sum(all_cycles)/len(all_cycles):.2f} min")
    print(f"  Median:        {med:.2f} min")
