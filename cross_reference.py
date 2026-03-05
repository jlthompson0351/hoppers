import sqlite3
from datetime import datetime

conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

print("=" * 70)
print("DUMPS vs SET WEIGHT CROSS-REFERENCE")
print("=" * 70)

# Get all set weight changes in order
cursor.execute("""
    SELECT received_at_utc, set_weight_lbs, job_id, source, machine_id
    FROM set_weight_history
    ORDER BY id ASC
""")
sw_rows = cursor.fetchall()

print("\nSet weight timeline:")
for r in sw_rows:
    dt = datetime.fromisoformat(r[0].replace('+00:00', ''))
    print(f"  {dt.strftime('%m/%d %H:%M')} -> {r[1]:.0f} lb (job {r[2]}, {r[3][:30]})")

# Get all dumps
cursor.execute("""
    SELECT id, ts, prev_stable_lbs, new_stable_lbs, processed_lbs
    FROM production_dumps
    ORDER BY id ASC
""")
dump_rows = cursor.fetchall()

# For each set weight period, show the dumps
print("\n" + "=" * 70)
print("DUMPS DURING EACH SET WEIGHT PERIOD")
print("=" * 70)

for i, sw in enumerate(sw_rows):
    sw_time = datetime.fromisoformat(sw[0].replace('+00:00', ''))
    sw_lbs = sw[1]
    job_id = sw[2]
    
    # Find end of this period (next set weight change)
    if i + 1 < len(sw_rows):
        end_time = datetime.fromisoformat(sw_rows[i+1][0].replace('+00:00', ''))
    else:
        end_time = datetime(2099, 1, 1)
    
    # Find dumps in this window
    period_dumps = []
    for d in dump_rows:
        dt = datetime.fromisoformat(d[1].replace('+00:00', ''))
        if sw_time <= dt < end_time:
            period_dumps.append({
                'time': dt,
                'full': d[2],
                'empty': d[3],
                'processed': d[4]
            })
    
    if not period_dumps:
        continue
    
    weights = [d['processed'] for d in period_dumps]
    avg_w = sum(weights) / len(weights) if weights else 0
    
    print(f"\nJob {job_id} | Set Weight: {sw_lbs:.0f} lb | {sw_time.strftime('%m/%d %H:%M')} - {end_time.strftime('%m/%d %H:%M')}")
    print(f"  Dumps: {len(period_dumps)} | Avg processed: {avg_w:.1f} lb")
    print(f"  {'Time':>8} | {'Full':>7} | {'Empty':>7} | {'Processed':>9} | {'vs Target':>9}")
    print(f"  {'-'*55}")
    for d in period_dumps[:15]:
        diff = d['processed'] - sw_lbs
        flag = " !!!" if abs(diff) > sw_lbs * 0.3 else ""
        print(f"  {d['time'].strftime('%H:%M:%S')} | {d['full']:6.1f} | {d['empty']:6.1f} | {d['processed']:8.1f} | {diff:+8.1f}{flag}")
    if len(period_dumps) > 15:
        print(f"  ... and {len(period_dumps) - 15} more dumps")
