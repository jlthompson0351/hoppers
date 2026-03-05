import sqlite3
conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()

for table in ['production_dumps', 'throughput_events', 'events']:
    print(f"\n=== {table} ===")
    cursor.execute(f"PRAGMA table_info({table})")
    for row in cursor.fetchall():
        print(f"  {row[1]} ({row[2]})")
