#!/usr/bin/env python3
"""Clear the zero offset."""
import datetime
import sys
sys.path.insert(0, '/opt/loadcell-transmitter')

from src.db.repo import AppRepository

repo = AppRepository('/var/lib/loadcell-transmitter/data/app.sqlite3')
cfg = repo.get_latest_config()

scale = cfg.get('scale') or {}
old_offset = scale.get('zero_offset_mv', scale.get('zero_offset_signal', 0.0))

scale['zero_offset_mv'] = 0.0
scale['zero_offset_signal'] = 0.0
scale['zero_offset_updated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
cfg['scale'] = scale
repo.save_config(cfg)

print(f"Zero offset cleared!")
print(f"  Old: {old_offset} mV")
print(f"  New: 0.0 mV")

