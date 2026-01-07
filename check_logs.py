import sqlite3
import json

conn = sqlite3.connect('var/data/app.sqlite3')
cursor = cursor = conn.cursor()

# Check recent ZERO events
print("=== Recent ZERO Events ===")
cursor.execute("SELECT ts, code, message, details_json FROM events WHERE code LIKE '%ZERO%' ORDER BY id DESC LIMIT 10")
for row in cursor.fetchall():
    ts, code, message, details = row
    print(f"{ts} - {code}")
    print(f"  {message}")
    if details and details != '{}':
        print(f"  Details: {details}")
    print()

# Check current config
print("=== Current Config ===")
cursor.execute("SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1")
cfg = json.loads(cursor.fetchone()[0])
scale = cfg.get('scale', {})
print(f"Tare offset: {scale.get('tare_offset_lbs', 0)} lbs")
print(f"Zero offset: {scale.get('zero_offset_signal', 0)} signal units")

conn.close()

