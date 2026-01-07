#!/usr/bin/env python3
"""Check calibration points in database."""
import sqlite3

conn = sqlite3.connect('/var/lib/loadcell-transmitter/data/app.sqlite3')
conn.row_factory = sqlite3.Row
cur = conn.execute('SELECT id, ts, known_weight_lbs, signal, ratiometric FROM calibration_points ORDER BY known_weight_lbs ASC')
points = cur.fetchall()

print(f"Total points: {len(points)}\n")
for p in points:
    print(f"ID: {p['id']}")
    print(f"  Weight: {p['known_weight_lbs']} lb")
    print(f"  Signal: {p['signal']}")
    print(f"  Ratiometric: {p['ratiometric']}")
    print()

conn.close()

