# Completed Job Webhook Runbook

## Scope

This runbook documents the completed-job webhook summary workflow and payload contract used for backend integration tests.

It covers:
- payload shape and field meanings
- `lb` vs `ea` representation using the same JSON keys
- override handling rules
- real-data examples from the production Pi database

## Trigger Behavior

A completed-job summary is generated when a new normal `job_id` arrives for the same machine scope.

Rules:
- close previous normal job on next normal `job_id`
- attribute manual override records to the active normal job window
- ignore orphan manual overrides (override with no active normal job)

## Payload Contract (Current Integration Shape)

Use this exact JSON shape for both `lb` and `ea` modes:

```json
{
  "schema_version": 1,
  "job_id": "1704405",
  "machine_id": "PLP6",
  "dump_count": 12,
  "basket_dump_count": 12,
  "total_processed_lbs": 1286.6247075265994,
  "avg_weight_lbs": 107.21872562721661,
  "avg_cycle_time_ms": 109884,
  "override_seen": false,
  "override_weight_lbs": null,
  "final_set_weight_lbs": 115.0,
  "final_set_weight_unit": "lb",
  "completed_at_utc": "2026-03-05T14:40:40+00:00"
}
```

Notes:
- key names stay the same in both modes
- in `ea` mode, keep `final_set_weight_lbs` populated from ERP set weight and set `final_set_weight_unit` to `ea`
- in `ea` mode, `total_processed_lbs` and `avg_weight_lbs` carry converted eaches values (key names intentionally unchanged for compatibility)

## Field Definitions

- `schema_version`: payload schema version
- `job_id`: completed job identifier
- `machine_id`: machine scope key
- `dump_count`: count of included dump events
- `basket_dump_count`: count of opto-mapped basket dump pulses in the job window (from `counted_events` table)
- `total_processed_lbs`: total processed amount (lb mode or converted eaches mode)
- `avg_weight_lbs`: average per dump (lb mode or converted eaches mode)
- `avg_cycle_time_ms`: average cycle duration in milliseconds
- `override_seen`: true if an override occurred in the job window
- `override_weight_lbs`: override set weight value (null if none)
- `final_set_weight_lbs`: ERP set weight reference for the completed job
- `final_set_weight_unit`: `lb` or `ea`
- `completed_at_utc`: webhook creation timestamp in UTC

## Real Examples (Pi Database)

These examples were generated from real data on Pi `172.16.190.25` (`/var/lib/loadcell-transmitter/data/app.sqlite3`).

### A) LBS example (no override)

```json
{
  "schema_version": 1,
  "job_id": "1704405",
  "machine_id": "PLP6",
  "dump_count": 12,
  "basket_dump_count": 12,
  "total_processed_lbs": 1286.6247075265994,
  "avg_weight_lbs": 107.21872562721661,
  "avg_cycle_time_ms": 109884,
  "override_seen": false,
  "override_weight_lbs": null,
  "final_set_weight_lbs": 115.0,
  "final_set_weight_unit": "lb",
  "completed_at_utc": "2026-03-05T14:40:40+00:00"
}
```

### B) EACHES example (same job, same shape)

```json
{
  "schema_version": 1,
  "job_id": "1704405",
  "machine_id": "PLP6",
  "dump_count": 12,
  "basket_dump_count": 12,
  "total_processed_lbs": 11.188040935013907,
  "avg_weight_lbs": 0.9323367445844923,
  "avg_cycle_time_ms": 109884,
  "override_seen": false,
  "override_weight_lbs": null,
  "final_set_weight_lbs": 115.0,
  "final_set_weight_unit": "ea",
  "completed_at_utc": "2026-03-05T14:40:40+00:00"
}
```

### C) Zero-dump edge case

```json
{
  "schema_version": 1,
  "job_id": "1704327",
  "machine_id": "PLP6",
  "dump_count": 0,
  "basket_dump_count": 0,
  "total_processed_lbs": 0.0,
  "avg_weight_lbs": 0.0,
  "avg_cycle_time_ms": 0,
  "override_seen": false,
  "override_weight_lbs": null,
  "final_set_weight_lbs": 115.0,
  "final_set_weight_unit": "lb",
  "completed_at_utc": "2026-03-05T14:40:40+00:00"
}
```

## Timezone and Timestamp Notes

- `completed_at_utc` is UTC by design.
- Example: `2026-03-05T14:40:40+00:00` equals `08:40:40` in CST (`UTC-6`).
- Pi timezone correction (`America/Chicago`) is an operational step and does not change the UTC payload convention.

## Idle/Overnight Gap Risk

Real DB review shows some long job windows when the same job spans idle periods.

Recommended guard:
- define a maximum no-dump gap threshold (for example, 60 minutes)
- split job-session metrics at that gap to avoid counting idle time as active cycle context

## Manual Test Command (Windows PowerShell)

```powershell
$uri = "https://yvpkeqfqwxuacncvzhwc.supabase.co/functions/v1/receive-scale-webhook"
$payload = @{
  schema_version = 1
  job_id = "1704405"
  machine_id = "PLP6"
  dump_count = 12
  basket_dump_count = 12
  total_processed_lbs = 1286.6247075265994
  avg_weight_lbs = 107.21872562721661
  avg_cycle_time_ms = 109884
  override_seen = $false
  override_weight_lbs = $null
  final_set_weight_lbs = 115.0
  final_set_weight_unit = "lb"
  completed_at_utc = "2026-03-05T14:40:40+00:00"
}
Invoke-WebRequest -Method Post -Uri $uri -ContentType "application/json" -Body ($payload | ConvertTo-Json -Compress)
```
