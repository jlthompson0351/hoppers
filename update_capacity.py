import sqlite3
import json
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

conn = sqlite3.connect('var/data/app.sqlite3')
cursor = conn.cursor()

# Get latest config
cursor.execute("SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1")
row = cursor.fetchone()
if row:
    cfg = json.loads(row[0])
    
    # Update max capacity
    print(f"Old max_lb: {cfg.get('range', {}).get('max_lb')}")
    if 'range' not in cfg:
        cfg['range'] = {}
    cfg['range']['max_lb'] = 1000.0
    print(f"New max_lb: {cfg['range']['max_lb']}")
    
    # Save new config
    cursor.execute("INSERT INTO config_versions (ts, config_json) VALUES (?, ?)", (utc_now(), json.dumps(cfg)))
    conn.commit()
    print("Config updated successfully.")
else:
    print("No config found to update.")

conn.close()
