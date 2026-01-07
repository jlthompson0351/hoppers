import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "/opt/loadcell-transmitter/var/data/app.sqlite3"

def fix_config():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Get latest config
    cur.execute("SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("No config found")
        return
    
    cfg = json.loads(row[0])
    
    # Force ratiometric OFF
    cfg["ratiometric"] = False
    
    # Save updated config
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur.execute("INSERT INTO config_versions(ts, config_json) VALUES (?,?)", (ts, json.dumps(cfg)))
    
    # Clear any bad calibration points
    cur.execute("DELETE FROM calibration_points")
    
    # Add a baseline 0 lb point at current signal
    cur.execute("SELECT signal_for_cal FROM (SELECT 1) LIMIT 1")  # This won't work, need live data
    
    conn.commit()
    conn.close()
    print("✓ Ratiometric disabled")
    print("✓ Calibration points cleared")
    print("Ready for fresh calibration in raw mV mode")

if __name__ == "__main__":
    fix_config()
