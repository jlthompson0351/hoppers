import sqlite3
import json
import sys
import os

# Try standard locations
DB_PATHS = [
    "app.sqlite3",
    "/var/lib/loadcell-transmitter/data/app.sqlite3",
    "data/app.sqlite3",
    "var/data/app.sqlite3"
]

def find_db():
    for p in DB_PATHS:
        if os.path.exists(p):
            return p
    return None

def check_and_fix():
    db_path = find_db()
    if not db_path:
        print("Error: Could not find app.sqlite3 database.")
        return

    print(f"Checking database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    changes_made = False
    
    # 1. Check Config
    try:
        row = conn.execute("SELECT id, config_json FROM config_versions ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            cfg = json.loads(row['config_json'])
            output = cfg.get("output", {})
            scale = cfg.get("scale", {})
            
            print("\n--- CURRENT CONFIG ---")
            print(f"Output Mode: {output.get('mode')}")
            print(f"Range: Min={cfg.get('range', {}).get('min_lb')}, Max={cfg.get('range', {}).get('max_lb')}")
            print(f"Tare Offset: {scale.get('tare_offset_lbs')} lbs")
            print(f"Zero Offset Signal: {scale.get('zero_offset_signal')}")
            
            # Check for legacy offset
            legacy_offset = output.get("plc_output_zero_offset")
            if legacy_offset is not None:
                print(f"\n!!! FOUND LEGACY OFFSET: plc_output_zero_offset = {legacy_offset}")
                print("This is likely causing the issue.")
                response = input("Do you want to remove this legacy offset? (y/n): ")
                if response.lower() == 'y':
                    output.pop("plc_output_zero_offset", None)
                    cfg["output"] = output
                    conn.execute("UPDATE config_versions SET config_json=? WHERE id=?", (json.dumps(cfg), row['id']))
                    conn.commit()
                    print("Legacy offset removed.")
                    changes_made = True
            else:
                print("No legacy 'plc_output_zero_offset' found.")
                
    except Exception as e:
        print(f"Error reading config: {e}")

    # 2. Check PLC Profile Points
    try:
        print("\n--- PLC PROFILE POINTS ---")
        rows = conn.execute("SELECT * FROM plc_profile_points ORDER BY analog_value ASC").fetchall()
        if not rows:
            print("No PLC profile points found (using linear mapping).")
        else:
            print(f"Found {len(rows)} profile points:")
            for r in rows:
                print(f"  ID: {r['id']}, Mode: {r['output_mode']}, Analog: {r['analog_value']}, Lbs: {r['plc_displayed_lbs']}")
            
            print("\nIf you did not intend to use a custom profile, these points might be causing the offset.")
            response = input("Do you want to DELETE ALL profile points? (y/n): ")
            if response.lower() == 'y':
                conn.execute("DELETE FROM plc_profile_points")
                conn.commit()
                print("All profile points deleted.")
                changes_made = True

    except Exception as e:
        print(f"Error reading profile points: {e}")

    conn.close()
    
    if changes_made:
        print("\nDONE. Please restart the service or reboot the Pi for changes to take effect.")
    else:
        print("\nNo changes made.")

if __name__ == "__main__":
    check_and_fix()
