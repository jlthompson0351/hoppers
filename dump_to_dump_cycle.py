import sqlite3
from datetime import datetime

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("=" * 60)
print("DUMP-TO-DUMP CYCLE TIME (timestamp based)")
print("Only dumps with > 100 lbs processed")
print("=" * 60)

cursor.execute("""
    SELECT id, ts, prev_stable_lbs, new_stable_lbs, processed_lbs
    FROM production_dumps
    WHERE processed_lbs > 100
    ORDER BY id DESC LIMIT 101
""")

rows = cursor.fetchall()

cycles = []
for i in range(len(rows) - 1):
    curr = rows[i]
    prev = rows[i + 1]
    curr_dt = datetime.fromisoformat(curr[1].replace('+00:00', ''))
    prev_dt = datetime.fromisoformat(prev[1].replace('+00:00', ''))
    gap_sec = (curr_dt - prev_dt).total_seconds()
    gap_min = gap_sec / 60

    # Skip gaps > 10 min (shift change, downtime, etc)
    if gap_sec > 600:
        continue

    cycles.append({
        'time': curr_dt,
        'gap_sec': gap_sec,
        'gap_min': gap_min,
        'weight': curr[4],
        'full': curr[2],
        'empty': curr[3]
    })

print(f"\nLast {len(cycles)} consecutive dump-to-dump gaps:")
print(f"{'Time':>8} | {'Cycle':>8} | {'Weight':>7}")
print("-" * 35)
for c in cycles[:40]:
    print(f"{c['time'].strftime('%H:%M:%S')} | {c['gap_min']:5.2f} min | {c['weight']:.0f} lb")

durations = [c['gap_min'] for c in cycles]
if durations:
    sorted_d = sorted(durations)
    median = sorted_d[len(sorted_d)//2]

    print("-" * 35)
    print(f"\nRESULTS ({len(durations)} cycles, gaps > 10 min excluded):")
    print(f"  Shortest: {min(durations):.2f} min")
    print(f"  Longest:  {max(durations):.2f} min")
    print(f"  Average:  {sum(durations)/len(durations):.2f} min")
    print(f"  Median:   {median:.2f} min")
