import sqlite3
import json

conn = sqlite3.connect('var/data/app.sqlite3')
cursor = conn.cursor()

cursor.execute("SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1")
row = cursor.fetchone()
if row:
    cfg = json.loads(row[0])
    print(json.dumps(cfg, indent=2))
else:
    print("No config found")

conn.close()
