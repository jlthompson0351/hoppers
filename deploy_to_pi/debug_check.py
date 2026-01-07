import sqlite3
import json

db = '/var/lib/loadcell-transmitter/data/app.sqlite3'
conn = sqlite3.connect(db)
c = conn.cursor()

print("=== Calibration Points ===")
c.execute("SELECT id, signal, known_weight_lbs, ratiometric FROM calibration_points")
for row in c.fetchall():
    print(f"  ID:{row[0]} signal:{row[1]:.6f} weight:{row[2]:.1f}lbs ratio:{row[3]}")

print("\n=== Current Config (scale section) ===")
c.execute("SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1")
cfg = json.loads(c.fetchone()[0])
scale = cfg.get('scale', {})
print(f"  tare_offset_lbs: {scale.get('tare_offset_lbs', 0)}")
print(f"  zero_offset_signal: {scale.get('zero_offset_signal', 0)}")

print("\n=== Recent Events ===")
c.execute("SELECT ts, code, message FROM events ORDER BY id DESC LIMIT 10")
rows = c.fetchall()
for row in rows:
    print(f"  {row[0]} {row[1]}: {row[2]}")

conn.close()
