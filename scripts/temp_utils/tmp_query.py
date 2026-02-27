import sqlite3
import json

db_path = "/var/lib/loadcell-transmitter/data/app.sqlite3"
try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT ts as timestamp_utc, level, code, message, details_json
    FROM events 
    WHERE code IN ('THROUGHPUT_CYCLE_COMPLETE')
      AND ts >= '2026-02-23'
    ORDER BY id DESC LIMIT 50 OFFSET 50;
    """

    for row in cursor.execute(query):
        print(f"[{row['timestamp_utc']}] {row['code']}: {row['message']}")
        if row['details_json']:
            try:
                details = json.loads(row['details_json'])
                print(f"   Details: {details}")
            except:
                print(f"   Details (raw): {row['details_json']}")
except Exception as e:
    print("Error:", e)
