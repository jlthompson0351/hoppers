import sqlite3

conn = sqlite3.connect('/opt/loadcell-transmitter/data/scale.db')
cur = conn.cursor()

# Check throughput_events
cur.execute('SELECT COUNT(*), COALESCE(SUM(processed_lbs), 0) FROM throughput_events')
event_count, event_total = cur.fetchone()
print(f"throughput_events: {event_count} events, {event_total:.1f} lb total")

# Check production_totals for today
cur.execute('SELECT period_type, period_start, total_lbs FROM production_totals WHERE period_type="day" ORDER BY period_start DESC LIMIT 1')
result = cur.fetchone()
if result:
    period_type, period_start, total_lbs = result
    print(f"production_totals (day): {total_lbs:.1f} lb on {period_start}")
else:
    print("production_totals (day): No data found")

conn.close()
