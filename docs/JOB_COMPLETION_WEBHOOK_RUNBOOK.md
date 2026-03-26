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

Current version: `schema_version: 2` (since 2026-03-26).

**Breaking change from v1:** `basket_dump_count` renamed to `basket_dump_count_raw`. Nine new fields added (see Field Definitions below).

Use this JSON shape for both `lb` and `ea` modes:

```json
{
  "schema_version": 2,
  "job_id": "1704405",
  "line_id": "line-1",
  "machine_id": "PLP6",
  "job_start_record_time_set_utc": "2026-03-05T12:00:00+00:00",
  "job_end_record_time_set_utc": "2026-03-05T12:10:00+00:00",
  "first_erp_timestamp_utc": "2026-03-05T12:00:00+00:00",
  "last_erp_timestamp_utc": "2026-03-05T12:05:00+00:00",
  "cycle_count": 12,
  "dump_count": 12,
  "total_processed_lbs": 1286.6247075265994,
  "avg_weight_lbs": 107.21872562721661,
  "avg_cycle_time_ms": 109884,
  "basket_dump_count_raw": 24,
  "basket_cycle_count": 12,
  "anomaly_detected": false,
  "first_basket_dump_utc": "2026-03-05T12:01:00+00:00",
  "last_basket_dump_utc": "2026-03-05T12:09:30+00:00",
  "idle_gaps": [],
  "avg_hopper_load_time_ms": 18500,
  "avg_dump_time_ms": 11200,
  "hopper_load_times": [18000, 19200, 17800, 18500],
  "override_seen": false,
  "override_count": 0,
  "final_set_weight_lbs": 115.0,
  "final_set_weight_unit": "lb",
  "rezero_warning_seen": true,
  "rezero_warning_reason": "outside_tolerance",
  "rezero_warning_weight_lbs": 21.5,
  "rezero_warning_threshold_lbs": 20.0,
  "post_dump_rezero_applied": true,
  "post_dump_rezero_last_apply_utc": "2026-03-05T12:06:00+00:00",
  "completed_at_utc": "2026-03-05T14:40:40+00:00"
}
```

Notes:
- key names stay the same in both modes
- in `ea` mode, keep `final_set_weight_lbs` populated from ERP set weight and set `final_set_weight_unit` to `ea`
- in `ea` mode, `total_processed_lbs` and `avg_weight_lbs` carry converted eaches values (key names intentionally unchanged for compatibility)
- re-zero warning fields are close-time diagnostics from the Pi runtime and indicate whether the operator warning logic was seen for the completed job before the next normal job arrived

## Field Definitions

- `schema_version`: payload schema version
- `job_id`: completed job identifier
- `line_id`: line scope key for the completed job window
- `machine_id`: machine scope key
- `job_start_record_time_set_utc`: first persisted set-weight timestamp for the active job window
- `job_end_record_time_set_utc`: timestamp used to close the completed job window
- `first_erp_timestamp_utc`: first ERP timestamp seen for the active job
- `last_erp_timestamp_utc`: last ERP timestamp seen for the active job before close
- `cycle_count`: count of throughput cycle records included in the job window
- `dump_count`: count of included dump events (weight-based hopper cycles)
- `total_processed_lbs`: total processed amount (lb mode or converted eaches mode)
- `avg_weight_lbs`: average per dump (lb mode or converted eaches mode)
- `avg_cycle_time_ms`: average total cycle duration in milliseconds (fill start → dump end)
- `basket_dump_count_raw`: raw opto pulse count for basket dump events in the job window (from `counted_events` table); replaces `basket_dump_count` from schema_version 1
- `basket_cycle_count`: actual basket cycle count — `basket_dump_count_raw // 2` (each physical dump produces 2 opto pulses)
- `anomaly_detected`: true if `basket_dump_count_raw` is odd, indicating an incomplete cycle or maintenance test dump
- `first_basket_dump_utc`: UTC timestamp of the first basket dump opto event in the job window; null if no dumps recorded
- `last_basket_dump_utc`: UTC timestamp of the last basket dump opto event in the job window; null if no dumps recorded
- `idle_gaps`: array of time gaps ≥ 2 hours between consecutive basket dump events; each entry has `start_utc`, `end_utc`, and `duration_minutes`; Supabase cross-references against downtime events to determine legitimacy
- `avg_hopper_load_time_ms`: average hopper fill duration in milliseconds per cycle (from weight rise detection to full-stable confirmation); 0 if no timing data
- `avg_dump_time_ms`: average dump duration in milliseconds per cycle (from full-stable to empty confirmed); 0 if no timing data
- `hopper_load_times`: array of individual fill durations in milliseconds, one per qualifying cycle in the job window; ordered by timestamp ascending
- `override_seen`: true if an override occurred in the job window
- `override_count`: number of manual overrides attributed to the completed job window
- `final_set_weight_lbs`: ERP set weight reference for the completed job
- `final_set_weight_unit`: `lb` or `ea`
- `rezero_warning_seen`: true if the between-jobs re-zero warning latched for the completed job before the next normal job arrived
- `rezero_warning_reason`: Pi-side reason string for the warning latch, usually `outside_tolerance` or a post-dump diagnostic reason
- `rezero_warning_weight_lbs`: signed zero-relative weight that triggered the warning
- `rezero_warning_threshold_lbs`: warning threshold configured on the Pi at the time of the warning
- `post_dump_rezero_applied`: true when one-shot post-dump re-zero was successfully applied during the completed job lifecycle
- `post_dump_rezero_last_apply_utc`: UTC timestamp of the latest successful post-dump re-zero apply for the completed job window
- `completed_at_utc`: webhook creation timestamp in UTC

## Backend Integration Decisions

- Treat this payload as the current canonical contract for `schema_version = 2`.
- `schema_version = 1` payloads used `basket_dump_count`; `schema_version = 2` renames it to `basket_dump_count_raw` and adds nine new fields. Backend should check `schema_version` and handle both gracefully during the rollout window.
- Keep backend parsing backward-tolerant during rollout; old payloads may still exist until the staged Pi runtime is activated by restart.
- Treat these as required fields and reject/log payloads if any are missing:
  - `schema_version`
  - `job_id`
  - `line_id`
  - `machine_id`
  - `job_start_record_time_set_utc`
  - `job_end_record_time_set_utc`
  - `completed_at_utc`
- Treat this tuple as the permanent idempotency key for completed-job rows:
  - `line_id`
  - `machine_id`
  - `job_id`
  - `job_start_record_time_set_utc`
  - `job_end_record_time_set_utc`
- If the same completed-job tuple arrives again, ignore the duplicate but return success.
- Preserve numeric precision as received.
- Use `job_end_record_time_set_utc` as the true completion timestamp for analytics.
- Use `completed_at_utc` as webhook creation / receipt-tracking time.
- Use `final_set_weight_unit` to interpret whether `final_set_weight_lbs`, `total_processed_lbs`, and `avg_weight_lbs` are operating in `lb` or `ea` mode.
- Treat the warning fields as explicit source-of-truth fields. If downstream compatibility still needs generic warning columns, derive them from the explicit fields instead of storing only the legacy names.

## Nullable-But-Valid Fields

- `first_erp_timestamp_utc`
- `last_erp_timestamp_utc`
- `final_set_weight_lbs`
- `final_set_weight_unit`
- `rezero_warning_reason`
- `rezero_warning_weight_lbs`
- `rezero_warning_threshold_lbs`
- `post_dump_rezero_last_apply_utc`

These should be accepted as valid when `null`. In normal production flow, `final_set_weight_lbs` and `final_set_weight_unit` are usually present, but backend storage should still accept the payload without special fallback behavior when they are not.

## Reporting Guidance

Completed-job fields most likely to be consumed directly by backend/UI reporting:

- `basket_dump_count_raw`
- `basket_cycle_count`
- `anomaly_detected`
- `first_basket_dump_utc`
- `last_basket_dump_utc`
- `idle_gaps`
- `avg_hopper_load_time_ms`
- `avg_dump_time_ms`
- `hopper_load_times`
- `override_seen`
- `override_count`
- `final_set_weight_lbs`
- `final_set_weight_unit`
- `rezero_warning_seen`
- `rezero_warning_reason`
- `post_dump_rezero_applied`

Fields that are still worth storing at the raw completed-job level even if they are not immediately surfaced:

- `rezero_warning_weight_lbs`
- `rezero_warning_threshold_lbs`
- `post_dump_rezero_last_apply_utc`
- `first_erp_timestamp_utc`
- `last_erp_timestamp_utc`

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
  "override_count": 0,
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
  "override_count": 0,
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
  "override_count": 0,
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
  line_id = "line-1"
  machine_id = "PLP6"
  job_start_record_time_set_utc = "2026-03-05T12:00:00+00:00"
  job_end_record_time_set_utc = "2026-03-05T12:10:00+00:00"
  first_erp_timestamp_utc = "2026-03-05T12:00:00+00:00"
  last_erp_timestamp_utc = "2026-03-05T12:05:00+00:00"
  cycle_count = 12
  dump_count = 12
  basket_dump_count = 12
  total_processed_lbs = 1286.6247075265994
  avg_weight_lbs = 107.21872562721661
  avg_cycle_time_ms = 109884
  override_seen = $false
  override_count = 0
  final_set_weight_lbs = 115.0
  final_set_weight_unit = "lb"
  rezero_warning_seen = $true
  rezero_warning_reason = "outside_tolerance"
  rezero_warning_weight_lbs = 21.5
  rezero_warning_threshold_lbs = 20.0
  post_dump_rezero_applied = $true
  post_dump_rezero_last_apply_utc = "2026-03-05T12:06:00+00:00"
  completed_at_utc = "2026-03-05T14:40:40+00:00"
}
Invoke-WebRequest -Method Post -Uri $uri -ContentType "application/json" -Body ($payload | ConvertTo-Json -Compress)
```
