import sqlite3, csv, sys

DB = '/var/lib/loadcell-transmitter/data/app.sqlite3'
conn = sqlite3.connect(DB)

# Check row counts
for table in ['trends_total', 'production_dumps', 'throughput_events', 'counted_events', 'job_lifecycle_state']:
    try:
        cnt = conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        print(f'{table}: {cnt} rows')
    except Exception as e:
        print(f'{table}: ERROR - {e}')

# Get date range
try:
    row = conn.execute('SELECT MIN(ts), MAX(ts) FROM trends_total').fetchone()
    print(f'trends_total range: {row[0]} to {row[1]}')
except Exception as e:
    print(f'trends range error: {e}')

# Sample recent weight readings (last 3 days, 1 in every 60 rows to keep it small)
print('\n--- Sample weight readings (every 60th row, last 3 days) ---')
try:
    rows = conn.execute(
        "SELECT ts, total_lbs, stable FROM trends_total WHERE ts > datetime('now','-3 days') ORDER BY ts ASC"
    ).fetchall()
    print(f'Rows in last 3 days: {len(rows)}')
    sampled = rows[::60]
    for r in sampled[:200]:
        print(r)
except Exception as e:
    print(f'Weight query error: {e}')

# Get production dumps (all - likely not huge)
print('\n--- Production dumps ---')
try:
    cols_info = conn.execute('PRAGMA table_info(production_dumps)').fetchall()
    cols = [c[1] for c in cols_info]
    print('Columns:', cols)
    rows = conn.execute('SELECT * FROM production_dumps ORDER BY ts DESC LIMIT 50').fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print(f'Dumps error: {e}')

# Get counted_events (basket dumps from opto)
print('\n--- Counted events (opto basket dumps) ---')
try:
    cols_info = conn.execute('PRAGMA table_info(counted_events)').fetchall()
    cols = [c[1] for c in cols_info]
    print('Columns:', cols)
    rows = conn.execute("SELECT * FROM counted_events ORDER BY ts DESC LIMIT 50").fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print(f'counted_events error: {e}')

conn.close()
