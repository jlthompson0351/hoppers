import sqlite3
conn = sqlite3.connect("/var/lib/loadcell-transmitter/data/app.sqlite3")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("Tables:", tables)

# Check for dump/fill related tables
for table in tables:
    if any(kw in table.lower() for kw in ['dump', 'fill', 'event', 'cycle', 'process']):
        print(f"\n=== {table} ===")
        cursor.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            print(row)
