#!/usr/bin/env python3
"""Debug script to check excitation reading configuration."""

import sqlite3
import json

db_path = '/var/lib/loadcell-transmitter/data/app.sqlite3'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)

# Try to get config from config_versions
if 'config_versions' in tables:
    cur.execute('SELECT config_json FROM config_versions ORDER BY id DESC LIMIT 1')
    row = cur.fetchone()
    if row:
        cfg = json.loads(row['config_json'])
        print('\nConfig from config_versions:')
        exc = cfg.get('excitation', {})
        print(f"  excitation config: {exc}")
        print(f"  ai_channel: {exc.get('ai_channel', 'NOT SET (default 1)')}")
        print(f"  ratiometric: {cfg.get('ratiometric', 'NOT SET')}")
    else:
        print('No config found in config_versions')
else:
    print('config_versions table does not exist!')

# Try app_config table
if 'app_config' in tables:
    cur.execute('SELECT json FROM app_config ORDER BY id DESC LIMIT 1')
    row = cur.fetchone()
    if row:
        cfg = json.loads(row['json'])
        print('\nConfig from app_config:')
        exc = cfg.get('excitation', {})
        print(f"  excitation config: {exc}")
        print(f"  ai_channel: {exc.get('ai_channel', 'NOT SET (default 1)')}")
        print(f"  ratiometric: {cfg.get('ratiometric', 'NOT SET')}")
    else:
        print('No config found in app_config')

conn.close()

# Now test the megaind driver
print('\n--- Testing MegaIND driver ---')
import sys
sys.path.insert(0, '/opt/loadcell-transmitter')
try:
    from src.hw.sequent_megaind import SequentMegaInd
    m = SequentMegaInd(0)
    for ch in [1, 2, 3, 4]:
        v = m.read_analog_in_v(ch)
        print(f'  Channel {ch}: {v:.3f} V')
except Exception as e:
    print(f'Error: {e}')
