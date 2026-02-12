import sqlite3
import json

try:
    conn = sqlite3.connect('var/data/app.sqlite3')
    cursor = conn.cursor()

    print("=== Last 20 Events ===")
    cursor.execute("SELECT ts, code, message, details_json FROM events ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    if not rows:
        print("No events found.")
    for row in rows:
        ts, code, message, details = row
        print(f"{ts} - {code}")
        print(f"  {message}")
        if details and details != '{}':
            print(f"  Details: {details}")
        print()

    conn.close()
except Exception as e:
    print(f"Error: {e}")
