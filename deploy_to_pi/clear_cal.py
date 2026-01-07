#!/usr/bin/env python3
"""Clear calibration points from the database."""
import sqlite3

conn = sqlite3.connect('/var/lib/loadcell-transmitter/data/app.sqlite3')
conn.execute('DELETE FROM calibration_points')
conn.commit()
count = conn.execute('SELECT COUNT(*) FROM calibration_points').fetchone()[0]
print(f'Calibration points cleared! Rows remaining: {count}')
conn.close()

