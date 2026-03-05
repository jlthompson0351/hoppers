import sqlite3
import json

conn = sqlite3.connect('/var/lib/loadcell-transmitter/data/app.sqlite3')

# Get all events from today
c = conn.execute("SELECT ts, level, code, message, details_json FROM events WHERE ts LIKE '2026-03-05%' ORDER BY id DESC LIMIT 300")

print("=" * 100)
print("ZERO-RELATED EVENTS FROM TODAY (2026-03-05)")
print("=" * 100)

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
                print(f"DETAILS: {json.dumps(d, indent=2)}")
            except:
                print(f"DETAILS: {details[:200]}")
        print("-" * 80)

# Also look for any events with large negative values
print("\n" + "=" * 100)
print("ALL EVENTS FROM TODAY (first 100)")
print("=" * 100)

c2 = conn.execute("SELECT ts, level, code, message, details_json FROM events WHERE ts LIKE '2026-03-05%' ORDER BY id DESC LIMIT 100")

for row in c2.fetchall():
    ts, level, code, message, details = row
    print(f"{ts} | {level:8} | {code:40} | {message[:50]}")
