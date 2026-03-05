from __future__ import annotations


SCHEMA_VERSION = 6


DDL_V1 = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;

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


DDL_V2 = """
CREATE TABLE IF NOT EXISTS throughput_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp_utc TEXT NOT NULL,
  processed_lbs REAL NOT NULL,
  full_lbs REAL,
  empty_lbs REAL,
  duration_ms INTEGER,
  confidence REAL,
  device_id TEXT,
  hopper_id TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_throughput_events_ts ON throughput_events(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_throughput_events_device_ts ON throughput_events(device_id, timestamp_utc);

-- Best-effort backfill from legacy dump table, preserving historical data.
INSERT INTO throughput_events(
  timestamp_utc,
  processed_lbs,
  full_lbs,
  empty_lbs,
  duration_ms,
  confidence,
  device_id,
  hopper_id,
  created_at
)
SELECT
  pd.ts,
  pd.processed_lbs,
  pd.prev_stable_lbs,
  pd.new_stable_lbs,
  NULL,
  NULL,
  NULL,
  NULL,
  pd.ts
FROM production_dumps pd
WHERE NOT EXISTS (
  SELECT 1
  FROM throughput_events te
  WHERE te.timestamp_utc = pd.ts
    AND ABS(te.processed_lbs - pd.processed_lbs) < 1e-9
    AND ABS(COALESCE(te.full_lbs, 0.0) - pd.prev_stable_lbs) < 1e-9
    AND ABS(COALESCE(te.empty_lbs, 0.0) - pd.new_stable_lbs) < 1e-9
);
"""


DDL_V3 = """
CREATE TABLE IF NOT EXISTS set_weight_current (
  line_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  set_weight_value REAL NOT NULL CHECK(set_weight_value >= 0.0),
  set_weight_unit TEXT NOT NULL CHECK(set_weight_unit IN ('lb', 'kg', 'g', 'oz')),
  set_weight_lbs REAL NOT NULL CHECK(set_weight_lbs >= 0.0),
  source TEXT NOT NULL,
  source_event_id TEXT,
  erp_timestamp_utc TEXT,
  product_id TEXT,
  operator_id TEXT,
  job_id TEXT,
  step_id TEXT,
  metadata_json TEXT NOT NULL,
  state_seq INTEGER NOT NULL CHECK(state_seq >= 0),
  received_at_utc TEXT NOT NULL,
  record_time_set_utc TEXT NOT NULL,
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (line_id, machine_id),
  CHECK(length(trim(line_id)) > 0),
  CHECK(length(trim(machine_id)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_set_weight_current_updated
ON set_weight_current(updated_at_utc DESC);

CREATE TABLE IF NOT EXISTS set_weight_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  received_at_utc TEXT NOT NULL,
  record_time_set_utc TEXT NOT NULL,
  line_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  set_weight_value REAL NOT NULL CHECK(set_weight_value >= 0.0),
  set_weight_unit TEXT NOT NULL CHECK(set_weight_unit IN ('lb', 'kg', 'g', 'oz')),
  set_weight_lbs REAL NOT NULL CHECK(set_weight_lbs >= 0.0),
  source TEXT NOT NULL,
  source_event_id TEXT,
  erp_timestamp_utc TEXT,
  product_id TEXT,
  operator_id TEXT,
  job_id TEXT,
  step_id TEXT,
  metadata_json TEXT NOT NULL,
  applied_to_current INTEGER NOT NULL CHECK(applied_to_current IN (0, 1)),
  duplicate_event INTEGER NOT NULL CHECK(duplicate_event IN (0, 1)),
  previous_set_weight_lbs REAL,
  previous_set_weight_unit TEXT CHECK(previous_set_weight_unit IS NULL OR previous_set_weight_unit IN ('lb', 'kg', 'g', 'oz')),
  state_seq INTEGER NOT NULL CHECK(state_seq >= 0),
  created_at_utc TEXT NOT NULL,
  CHECK(length(trim(line_id)) > 0),
  CHECK(length(trim(machine_id)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_set_weight_history_scope_ts
ON set_weight_history(line_id, machine_id, received_at_utc DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_set_weight_history_ts
ON set_weight_history(received_at_utc DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_set_weight_history_event
ON set_weight_history(source_event_id);
"""


DDL_V4 = """
CREATE INDEX IF NOT EXISTS idx_throughput_events_target_set_weight
ON throughput_events(target_set_weight_lbs);
CREATE INDEX IF NOT EXISTS idx_production_dumps_target_set_weight
ON production_dumps(target_set_weight_lbs);
"""


DDL_V5 = """
CREATE INDEX IF NOT EXISTS idx_throughput_events_dump_type
ON throughput_events(dump_type);
CREATE INDEX IF NOT EXISTS idx_production_dumps_dump_type
ON production_dumps(dump_type);
"""


DDL_V6 = """
CREATE TABLE IF NOT EXISTS job_lifecycle_state (
  line_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  active_job_id TEXT NOT NULL,
  active_job_started_record_time_set_utc TEXT NOT NULL,
  active_job_last_record_time_set_utc TEXT NOT NULL,
  active_job_first_erp_timestamp_utc TEXT,
  active_job_last_erp_timestamp_utc TEXT,
  override_count INTEGER NOT NULL DEFAULT 0 CHECK(override_count >= 0),
  last_set_weight_lbs REAL,
  last_set_weight_unit TEXT CHECK(last_set_weight_unit IS NULL OR last_set_weight_unit IN ('lb', 'kg', 'g', 'oz')),
  last_source_event_id TEXT,
  updated_at_utc TEXT NOT NULL,
  PRIMARY KEY (line_id, machine_id),
  CHECK(length(trim(line_id)) > 0),
  CHECK(length(trim(machine_id)) > 0),
  CHECK(length(trim(active_job_id)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_job_lifecycle_state_job
ON job_lifecycle_state(active_job_id, updated_at_utc DESC);

CREATE TABLE IF NOT EXISTS job_completion_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at_utc TEXT NOT NULL,
  line_id TEXT NOT NULL,
  machine_id TEXT NOT NULL,
  job_id TEXT NOT NULL,
  job_start_record_time_set_utc TEXT NOT NULL,
  job_end_record_time_set_utc TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending', 'sent')),
  attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
  next_retry_at_utc TEXT NOT NULL,
  last_attempt_at_utc TEXT,
  last_error TEXT,
  sent_at_utc TEXT,
  CHECK(length(trim(line_id)) > 0),
  CHECK(length(trim(machine_id)) > 0),
  CHECK(length(trim(job_id)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_job_completion_outbox_pending
ON job_completion_outbox(status, next_retry_at_utc, id);
CREATE INDEX IF NOT EXISTS idx_job_completion_outbox_job
ON job_completion_outbox(job_id, created_at_utc DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_job_completion_outbox_dedupe
ON job_completion_outbox(line_id, machine_id, job_id, job_start_record_time_set_utc, job_end_record_time_set_utc);
"""

