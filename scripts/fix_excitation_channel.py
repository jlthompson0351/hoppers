#!/usr/bin/env python3
"""Fix excitation channel to 1."""
import sys
sys.path.insert(0, '/opt/loadcell-transmitter')

from src.db.repo import AppRepository

repo = AppRepository('/var/lib/loadcell-transmitter/data/app.sqlite3')
cfg = repo.get_latest_config()

old_ch = cfg.get('excitation', {}).get('ai_channel', 1)
cfg.setdefault('excitation', {})['ai_channel'] = 1
repo.save_config(cfg)

print(f'Fixed: excitation.ai_channel changed from {old_ch} to 1')
