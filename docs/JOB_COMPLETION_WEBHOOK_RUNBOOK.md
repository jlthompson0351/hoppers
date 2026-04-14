# Completed Job Webhook Runbook

## Scope

This runbook documents the completed-job webhook summary workflow and payload contract.

It covers:
- payload shape and field meanings
- how cycle metrics are calculated
- override handling rules
- real-data examples

---

## Trigger Behavior

A completed-job summary is generated when a new normal `job_id` arrives for the same machine scope.

Rules:
- close previous normal job on next normal `job_id`
- attribute manual override records to the active normal job window
- ignore orphan manual overrides (override with no active normal job)

---

## Payload Contract (Current — schema_version 3)

**Key change as of 2026-04-13:** All cycle metrics now derive from the opto ISO signal (`counted_events` table), not from the hopper weight cycle detector (`throughput_events`). Hopper fill tracking is disabled.

```json
{
  "schema_version": 3,
  "job_id": "1707250",
  "line_id": "default_line",
  "machine_id": "PLP6",
  "job_start_record_time_set_utc": "2026-04-13T12:59:53+00:00",
  "job_end_record_time_set_utc": "2026-04-13T13:20:48+00:00",
  "first_erp_timestamp_utc": "2026-04-13T12:59:53+00:00",
  "last_erp_timestamp_utc": "2026-04-13T13:20:48+00:00",
  "cycle_count": 0,
  "dump_count": 0,
  "total_processed_lbs": 0.0,
  "avg_weight_lbs": 0.0,
  "avg_cycle_time_ms": 103000,
  "basket_dump_count_raw": 8,
  "basket_cycle_count": 8,
  "anomaly_detected": false,
  "first_basket_dump_utc": "2026-04-13T13:02:25+00:00",
  "last_basket_dump_utc": "2026-04-13T13:19:04+00:00",
  "idle_gaps": [],
  "avg_hopper_load_time_ms": 0,
  "avg_dump_time_ms": 0,
  "hopper_load_times": [],
  "valid_fill_count": 0,
  "excluded_fill_count": 0,
  "override_seen": false,
  "override_count": 0,
  "final_set_weight_lbs": 100.0,
  "final_set_weight_unit": "lb",
  "rezero_warning_seen": false,
  "rezero_warning_reason": null,
  "rezero_warning_weight_lbs": null,
  "rezero_warning_threshold_lbs": null,
  "post_dump_rezero_applied": false,
  "post_dump_rezero_last_apply_utc": null,
  "dump_events": [],
  "timezone": "UTC",
  "pi_system_time_utc": "2026-04-13T13:20:48",
  "pi_local_time": "2026-04-13T13:20:48",
  "completed_at_utc": "2026-04-13T13:20:48+00:00"
}
```

---

## Field Definitions

### Opto-Derived Fields (Active — source of truth for cycle metrics)

- `basket_dump_count_raw` — count of opto fires recorded in job window. Each fire = one complete basket rotation cycle. The 30-second cooldown in the Pi code suppresses the second fire of each double-shake, so this is already deduplicated.
- `basket_cycle_count` — same as `basket_dump_count_raw`. No `÷ 2` applied. **Do not halve this.**
- `avg_cycle_time_ms` — `(last_basket_dump_utc - first_basket_dump_utc) / (basket_dump_count_raw - 1)`. The average time between basket rotation cycles in milliseconds. Typical value: ~103,000 ms (~1:43 min). If significantly higher, line may be starving for parts.
- `first_basket_dump_utc` — UTC timestamp of first opto fire in job window. Null if no dumps.
- `last_basket_dump_utc` — UTC timestamp of last opto fire in job window. Null if no dumps.
- `idle_gaps` — array of time gaps ≥ 2 hours between consecutive dump events. Each entry: `{start_utc, end_utc, duration_minutes}`. Cross-reference against downtime in Supabase to determine legitimacy.
- `anomaly_detected` — always `false`. (Cooldown already handles double-fire deduplication; odd/even check removed.)

### Hopper Weight Fields (Disabled — will be 0 / [])

These come from the hopper weight cycle detector which is currently disabled:
- `cycle_count`, `dump_count` — always `0`
- `total_processed_lbs`, `avg_weight_lbs` — always `0.0`
- `avg_hopper_load_time_ms`, `avg_dump_time_ms` — always `0`
- `hopper_load_times`, `dump_events` — always `[]`
- `valid_fill_count`, `excluded_fill_count` — always `0`

### Job / ERP Fields
- `schema_version` — payload schema version (currently `3`)
- `job_id` — completed job identifier from ERP
- `line_id` — line scope key
- `machine_id` — machine scope key (e.g., `PLP6`)
- `job_start_record_time_set_utc` — first persisted set-weight timestamp for the job window
- `job_end_record_time_set_utc` — timestamp used to close the job window (new job arrives)
- `first_erp_timestamp_utc` — first ERP timestamp seen for the active job
- `last_erp_timestamp_utc` — last ERP timestamp seen before job closes
- `final_set_weight_lbs` — ERP set weight for the completed job (lbs or eaches value)
- `final_set_weight_unit` — `lb` or `ea`
- `override_seen` — true if operator overrode set weight during job
- `override_count` — number of manual overrides attributed to the job window

### Re-Zero Warning Fields
- `rezero_warning_seen` — true if zero drift warning latched during the job
- `rezero_warning_reason` — Pi diagnostic reason string
- `rezero_warning_weight_lbs` — signed weight that triggered the warning
- `rezero_warning_threshold_lbs` — threshold configured at time of warning
- `post_dump_rezero_applied` — true if one-shot post-dump re-zero was applied

### Timestamp Fields
- `completed_at_utc` — webhook creation timestamp in UTC
- `pi_system_time_utc` — Pi clock at job close (for diagnostic clock drift detection)
- `pi_local_time` — Pi local time at job close

---

## Backend Integration Decisions

- `schema_version = 3` is current. `schema_version = 2` payloads used `basket_dump_count_raw // 2` for `basket_cycle_count` — **that was wrong**. Version 3 uses `basket_cycle_count = basket_dump_count_raw`.
- `avg_cycle_time_ms` in v1/v2 came from `throughput_events` (was always 0 due to detector issues). In v3 it comes from opto timestamps and is reliable.
- Treat `basket_dump_count_raw` and `basket_cycle_count` as equal — they are the same value.
- Use `avg_cycle_time_ms` for line efficiency: baseline ≈ 103,000 ms (~1:43 min). Flag if > 130,000 ms.
- `idle_gaps` is the primary signal for identifying shift breaks, downtime, or parts starvation periods.

### Idempotency Key
```
(line_id, machine_id, job_id, job_start_record_time_set_utc, job_end_record_time_set_utc)
```
If the same tuple arrives again, ignore the duplicate but return success.

### Required Fields
- `schema_version`, `job_id`, `line_id`, `machine_id`
- `job_start_record_time_set_utc`, `job_end_record_time_set_utc`
- `completed_at_utc`

### Nullable-But-Valid Fields
- `first_erp_timestamp_utc`, `last_erp_timestamp_utc`
- `final_set_weight_lbs`, `final_set_weight_unit`
- `first_basket_dump_utc`, `last_basket_dump_utc`
- `rezero_warning_reason`, `rezero_warning_weight_lbs`, `rezero_warning_threshold_lbs`
- `post_dump_rezero_last_apply_utc`

---

## Key Reporting Fields

| Field | Use |
|---|---|
| `basket_dump_count_raw` = `basket_cycle_count` | Total basket rotations in job |
| `avg_cycle_time_ms` | Line speed — flag if >> 103,000 ms |
| `first_basket_dump_utc` / `last_basket_dump_utc` | Active production window |
| `idle_gaps` | Identify stoppages |
| `final_set_weight_lbs` | ERP target weight |
| `override_seen` / `override_count` | Operator interventions |
| `rezero_warning_seen` | Zero drift alert |
| `post_dump_rezero_applied` | Auto-correction active |

---

## Line Starvation Detection

The primary signal for line starvation is `avg_cycle_time_ms`:
- Normal rate: ~30 dumps/hour → ~103,000 ms avg cycle time
- If average cycle time increases significantly (e.g., > 130,000 ms) → parts are not reaching the machine fast enough
- Use `idle_gaps` to identify multi-hour stoppages

---

## Timezone and Timestamp Notes
- All UTC timestamps use `+00:00` suffix by convention
- Pi timezone is configured per-site; `pi_local_time` reflects that timezone
- Use `job_end_record_time_set_utc` as the true completion timestamp for analytics
- Use `completed_at_utc` for webhook receipt tracking

---

## Manual Test Command (Windows PowerShell)

```powershell
$uri = "https://yvpkeqfqwxuacncvzhwc.supabase.co/functions/v1/receive-scale-webhook"
$payload = @{
  schema_version = 3
  job_id = "1707250"
  line_id = "default_line"
  machine_id = "PLP6"
  job_start_record_time_set_utc = "2026-04-13T12:59:53+00:00"
  job_end_record_time_set_utc = "2026-04-13T13:20:48+00:00"
  first_erp_timestamp_utc = "2026-04-13T12:59:53+00:00"
  last_erp_timestamp_utc = "2026-04-13T13:20:48+00:00"
  cycle_count = 0
  dump_count = 0
  total_processed_lbs = 0.0
  avg_weight_lbs = 0.0
  avg_cycle_time_ms = 103000
  basket_dump_count_raw = 8
  basket_cycle_count = 8
  anomaly_detected = $false
  first_basket_dump_utc = "2026-04-13T13:02:25+00:00"
  last_basket_dump_utc = "2026-04-13T13:19:04+00:00"
  idle_gaps = @()
  avg_hopper_load_time_ms = 0
  avg_dump_time_ms = 0
  hopper_load_times = @()
  override_seen = $false
  override_count = 0
  final_set_weight_lbs = 100.0
  final_set_weight_unit = "lb"
  rezero_warning_seen = $false
  post_dump_rezero_applied = $false
  completed_at_utc = "2026-04-13T13:20:48+00:00"
}
Invoke-WebRequest -Method Post -Uri $uri -ContentType "application/json" -Body ($payload | ConvertTo-Json -Compress)
```
