import sqlite3
import json
from datetime import datetime

conn = sqlite3.connect('/var/lib/loadcell-transmitter/data/app.sqlite3')

print("=" * 100)
print("ALL ZERO-RELATED EVENTS FROM TODAY (2026-03-05)")
print("=" * 100)

# Get all events from today
c = conn.execute("SELECT ts, level, code, message, details_json FROM events WHERE ts LIKE '2026-03-05%' ORDER BY id DESC LIMIT 500")

for row in c.fetchall():
    ts, level, code, message, details = row
    
    # Check if this is a zero-related event
    is_zero_event = (
        'ZERO' in code or 
        'zero' in message.lower() or 
        'offset' in message.lower() or
        (details and ('offset' in details.lower() or 'zero' in details.lower()))
    )
    
    if is_zero_event:
        print(f"\nTIME: {ts}")
        print(f"LEVEL: {level}")
        print(f"CODE: {code}")
        print(f"MESSAGE: {message}")
        if details:
            try:
                d = json.loads(details)
                # Look for key fields
                important = {}
                for k in ['delta_lbs', 'zero_offset_delta_lbs', 'pending_delta_lbs', 'drift_lbs', 'correction_lb', 'offset']:
                    if k in d:
                        important[k] = d[k]
                if important:
                    print(f"KEY VALUES: {important}")
                if 'reason' in d:
                    print(f"REASON: {d['reason']}")
            except:
                pass
        print("-" * 80)

# Check for configuration
print("\n" + "=" * 100)
print("LATEST CONFIG zero_tracking settings")
print("=" * 100)

c2 = conn.execute("SELECT ts, level, code, message, details_json FROM events WHERE code = 'CONFIG_SAVED' AND ts LIKE '2026-03-05%' ORDER BY id DESC LIMIT 5")
for row in c2.fetchall():
    ts, level, code, message, details = row
    print(f"\nConfig saved at: {ts}")
    if details:
        try:
            d = json.loads(details)
            if 'zero_tracking' in str(d):
                print(f"Details: {json.dumps(d, indent=2)[:500]}")
        except:
            pass
