import sqlite3, json, csv, sys

DB = "/var/lib/loadcell-transmitter/data/app.sqlite3"
c = sqlite3.connect(DB)

# Calibration points
print("=== CAL_CSV ===")
print("id,ts,known_weight_lbs,signal")
for r in c.execute("SELECT id, ts, known_weight_lbs, signal FROM calibration_points ORDER BY known_weight_lbs, id"):
    print(f"{r[0]},{r[1]},{r[2]},{r[3]}")

print("=== PLC_CSV ===")
print("id,ts,output_mode,analog_value,plc_displayed_lbs")
for r in c.execute("SELECT id, ts, output_mode, analog_value, plc_displayed_lbs FROM plc_profile_points ORDER BY plc_displayed_lbs, id"):
    print(f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}")

print("=== CONFIG_JSON ===")
row = c.execute("SELECT value FROM app_config ORDER BY rowid DESC LIMIT 1").fetchone()
if row:
    print(row[0])
else:
    # Try alternate table name
    try:
        row = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(json.dumps({"tables": [r[0] for r in row]}))
    except:
        print("{}")

c.close()
