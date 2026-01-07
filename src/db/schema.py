from __future__ import annotations


SCHEMA_VERSION = 1


DDL_V1 = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS config_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  config_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  level TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS calibration_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  known_weight_lbs REAL NOT NULL,
  signal REAL NOT NULL,
  ratiometric INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cal_points_ts ON calibration_points(ts);

CREATE TABLE IF NOT EXISTS plc_profile_points (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  output_mode TEXT NOT NULL,
  analog_value REAL NOT NULL,
  plc_displayed_lbs REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_plc_points_mode_ts ON plc_profile_points(output_mode, ts);

CREATE TABLE IF NOT EXISTS trends_excitation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  excitation_v REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_exc_ts ON trends_excitation(ts);

CREATE TABLE IF NOT EXISTS trends_channels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  channel INTEGER NOT NULL,
  enabled INTEGER NOT NULL,
  raw_mv REAL NOT NULL,
  filtered REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ch_ts ON trends_channels(channel, ts);

CREATE TABLE IF NOT EXISTS trends_total (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  total_lbs REAL NOT NULL,
  stable INTEGER NOT NULL,
  output_mode TEXT NOT NULL,
  output_cmd REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_total_ts ON trends_total(ts);

CREATE TABLE IF NOT EXISTS production_dumps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  prev_stable_lbs REAL NOT NULL,
  new_stable_lbs REAL NOT NULL,
  processed_lbs REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS production_totals (
  period_type TEXT NOT NULL,
  period_start TEXT NOT NULL,
  total_lbs REAL NOT NULL,
  PRIMARY KEY (period_type, period_start)
);
"""


