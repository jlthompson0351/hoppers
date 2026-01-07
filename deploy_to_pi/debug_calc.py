#!/usr/bin/env python3
"""Debug the calibration calculation."""
import sqlite3
import sys
sys.path.insert(0, '/opt/loadcell-transmitter')

from src.core.calibration import CalibrationCurve
from src.db.repo import AppRepository

# Get config
repo = AppRepository('/var/lib/loadcell-transmitter/data/app.sqlite3')
cfg = repo.get_latest_config()
scale = cfg.get('scale') or {}
zero_offset = scale.get('zero_offset_signal', 0.0)

print(f"Zero offset: {zero_offset}")
print()

# Get calibration points
points = repo.get_calibration_points()
print(f"Calibration points: {len(points)}")
for p in points:
    print(f"  {p.known_weight_lbs} lb at signal {p.signal}")
print()

# Test calculation
test_signal = 6.682  # From snapshot
print(f"Test signal (raw): {test_signal} mV")
calibrated_signal = test_signal - zero_offset
print(f"Calibrated signal (after offset): {calibrated_signal} mV")
print()

# Create curve
if len(points) >= 2:
    curve = CalibrationCurve(
        points=[(float(p.signal), float(p.known_weight_lbs)) for p in points],
        ratiometric=False
    )
    weight = curve.weight_from_signal(calibrated_signal)
    print(f"Calculated weight: {weight} lb")
    print()
    
    # Manual check
    p0 = points[0]
    p1 = points[1]
    slope = (p1.known_weight_lbs - p0.known_weight_lbs) / (p1.signal - p0.signal)
    manual_weight = p0.known_weight_lbs + (calibrated_signal - p0.signal) * slope
    print(f"Manual calculation:")
    print(f"  Slope: {slope} lb/mV")
    print(f"  Weight: {manual_weight} lb")

