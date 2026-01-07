#!/usr/bin/env python3
"""Test the uncalibrated fault by temporarily clearing cal points."""
import sys
import time
import subprocess
import json
sys.path.insert(0, '/opt/loadcell-transmitter')

from src.db.repo import AppRepository

repo = AppRepository('/var/lib/loadcell-transmitter/data/app.sqlite3')

def get_snapshot():
    result = subprocess.run(['curl', '-s', 'http://localhost:8080/api/snapshot'], 
                          capture_output=True, text=True)
    return json.loads(result.stdout)

# Save current points
saved_points = repo.get_calibration_points()
print(f"Saved {len(saved_points)} calibration points")

# Clear all points
repo.clear_calibration_points()
print("Cleared calibration points")
print()

# Wait for acquisition loop to detect
time.sleep(3)

# Check fault status
snap = get_snapshot()
system = snap['system']
weight = snap['weight']

print("System status with 0 calibration points:")
print(f"  Fault: {system['fault']}")
print(f"  Fault Reason: {system.get('fault_reason', 'None')}")
print(f"  Weight: {weight['total_lbs']} lb")
print(f"  Cal Points Used: {weight['cal_points_used']}")
print()

# Restore points
for p in saved_points:
    repo.add_calibration_point(p.known_weight_lbs, p.signal)
print(f"Restored {len(saved_points)} calibration points")

# Wait for it to update
time.sleep(3)

snap2 = get_snapshot()
system2 = snap2['system']
weight2 = snap2['weight']

print()
print("System status after restoring points:")
print(f"  Fault: {system2['fault']}")
print(f"  Fault Reason: {system2.get('fault_reason', 'None')}")
print(f"  Weight: {weight2['total_lbs']} lb")
print(f"  Cal Points Used: {weight2['cal_points_used']}")
