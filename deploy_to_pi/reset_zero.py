import sqlite3
import json

db = '/var/lib/loadcell-transmitter/data/app.sqlite3'
conn = sqlite3.connect(db)
c = conn.cursor()

# Get current config
c.execute("SELECT id, config_json FROM config_versions ORDER BY id DESC LIMIT 1")
row = c.fetchone()
cfg_id, cfg_json = row
cfg = json.loads(cfg_json)

# Reset zero offset to 0
if 'scale' not in cfg:
    cfg['scale'] = {}
cfg['scale']['zero_offset_signal'] = 0.0

# Save updated config
import datetime
ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
c.execute("INSERT INTO config_versions (ts, config_json) VALUES (?, ?)", (ts, json.dumps(cfg)))
conn.commit()

print("Zero offset reset to 0.0")
print("Restart the service to apply: sudo systemctl restart loadcell-transmitter")

conn.close()
