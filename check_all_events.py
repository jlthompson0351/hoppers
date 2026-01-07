import sqlite3

conn = sqlite3.connect('var/data/app.sqlite3')
cursor = conn.cursor()

print("=== Last 20 Events (All Types) ===")
cursor.execute("SELECT ts, code, message FROM events ORDER BY id DESC LIMIT 20")
for row in cursor.fetchall():
    ts, code, message = row
    print(f"{ts} - {code}: {message}")

conn.close()

