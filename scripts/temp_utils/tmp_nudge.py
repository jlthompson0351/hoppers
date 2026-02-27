import sqlite3, json
from datetime import datetime, timezone

db = '/var/lib/loadcell-transmitter/data/app.sqlite3'
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute('SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1')
row = cur.fetchone()
cfg = json.loads(row[0])

cfg['output']['test_mode'] = True
cfg['output']['test_value'] = 0.450
cfg['output']['calibration_active'] = False

ts = datetime.now(timezone.utc).isoformat(timespec='seconds')
cur.execute("INSERT INTO config_versions(ts, config_json) VALUES (?, ?)", (ts, json.dumps(cfg)))
conn.commit()
conn.close()
print("Output set to TEST MODE: 0.450 V")
print("PLC should read 22.5 lbs")
