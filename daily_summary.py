import sqlite3
from datetime import datetime

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

cursor.execute("""
    SELECT id, ts, prev_stable_lbs, new_stable_lbs, processed_lbs
    FROM production_dumps
    WHERE processed_lbs > 100
    ORDER BY id ASC
""")

rows = cursor.fetchall()

by_day = {}
cycles_by_day = {}

for i, row in enumerate(rows):
    dt = datetime.fromisoformat(row[1].replace('+00:00', ''))
    day = dt.strftime('%Y-%m-%d')
    if day not in by_day:
        by_day[day] = {'dumps': 0, 'total_lbs': 0}
    by_day[day]['dumps'] += 1
    by_day[day]['total_lbs'] += row[4]

    if i > 0:
        prev_dt = datetime.fromisoformat(rows[i-1][1].replace('+00:00', ''))
        gap_min = (dt - prev_dt).total_seconds() / 60
        if 1.0 <= gap_min <= 10.0:
            if day not in cycles_by_day:
                cycles_by_day[day] = []
            cycles_by_day[day].append(gap_min)

print(f"{'Date':>12} | {'Dumps':>5} | {'Total lbs':>10} | {'Avg Cycle':>10}")
print("-" * 50)
for day in sorted(by_day.keys()):
    d = by_day[day]
    avg = ""
    if day in cycles_by_day and cycles_by_day[day]:
        avg = f"{sum(cycles_by_day[day])/len(cycles_by_day[day]):.2f} min"
    print(f"{day} | {d['dumps']:5d} | {d['total_lbs']:>9.0f} | {avg:>10}")
