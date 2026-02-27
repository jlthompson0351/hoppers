#!/usr/bin/env python3
"""Check for any hidden offsets."""
import sys
sys.path.insert(0, '/opt/loadcell-transmitter')

from src.db.repo import AppRepository

repo = AppRepository('/var/lib/loadcell-transmitter/data/app.sqlite3')
cfg = repo.get_latest_config()

scale = cfg.get('scale') or {}
print("Scale offsets:")
print(f"  zero_offset_mv: {scale.get('zero_offset_mv', 0.0)} mV")
print(f"  zero_offset_signal: {scale.get('zero_offset_signal', 0.0)} mV")
print(f"  tare_offset_lbs: {scale.get('tare_offset_lbs', 0.0)} lb")
print()

points = repo.get_calibration_points()
print(f"Calibration points: {len(points)}")
for p in points:
    print(f"  {p.known_weight_lbs} lb at {p.signal} mV")
print()

if len(points) < 2:
    print("⚠️  WARNING: Need at least 2 calibration points!")
    print("   Currently using fallback: signal × 10 = weight")
else:
    print("✅ Enough points for proper calibration")

