import sqlite3
import json
import sys
from datetime import datetime

DB_PATH = "/var/lib/loadcell-transmitter/data/app.sqlite3"

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def main():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = dict_factory
        cursor = conn.cursor()
    except sqlite3.Error as e:
        print(json.dumps({"error": f"Failed to connect to database: {e}"}))
        sys.exit(1)

    output = {}

    # 1. Get latest config
    try:
        cursor.execute("SELECT config_json, ts FROM config_versions ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            output["config"] = json.loads(row["config_json"])
            output["config_ts"] = row["ts"]
        else:
            output["config"] = None
            output["config_error"] = "No config found"
    except Exception as e:
        output["config"] = None
        output["config_error"] = str(e)

    # 2. Get calibration points
    try:
        cursor.execute("SELECT id, ts, known_weight_lbs, signal FROM calibration_points ORDER BY known_weight_lbs ASC")
        output["calibration_points"] = cursor.fetchall()
    except Exception as e:
        output["calibration_points"] = []
        output["calibration_error"] = str(e)

    # 3. Get PLC profile points
    try:
        cursor.execute("SELECT id, ts, output_mode, analog_value, plc_displayed_lbs FROM plc_profile_points ORDER BY output_mode, analog_value ASC")
        output["plc_profile_points"] = cursor.fetchall()
    except Exception as e:
        output["plc_profile_points"] = []
        output["plc_profile_error"] = str(e)
        
    # 4. Get recent events (last 20)
    try:
        cursor.execute("SELECT ts, level, code, message FROM events ORDER BY id DESC LIMIT 20")
        output["recent_events"] = cursor.fetchall()
    except Exception as e:
        output["recent_events"] = []
        output["events_error"] = str(e)

    conn.close()
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
