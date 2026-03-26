# HANDOFF — New Webhook Data (schema_version 2)

**Date:** 2026-03-26  
**Scope:** Supabase backend — edge function + table updates  
**Pi changes:** Already staged, takes effect on next `loadcell-transmitter` restart  
**Status:** Ready for backend implementation

---

## What Changed on the Pi

The completed-job webhook payload bumped from `schema_version: 1` to `schema_version: 2`.

### Breaking Change — Field Rename

| Old (v1) | New (v2) | Type |
|---|---|---|
| `basket_dump_count` | `basket_dump_count_raw` | integer |

### Nine New Fields

| Field | Type | Description |
|---|---|---|
| `basket_dump_count_raw` | integer | Raw opto pulse count (2 pulses = 1 physical dump) |
| `basket_cycle_count` | integer | Actual dump cycles — `raw // 2` |
| `anomaly_detected` | boolean | True if raw count is odd (incomplete cycle or maintenance test) |
| `first_basket_dump_utc` | timestamptz or null | Timestamp of first basket dump opto event in the job window |
| `last_basket_dump_utc` | timestamptz or null | Timestamp of last basket dump opto event in the job window |
| `idle_gaps` | jsonb array | Gaps ≥ 2 hours between consecutive basket dumps — see structure below |
| `avg_hopper_load_time_ms` | integer | Average hopper fill time per cycle in ms (rise detection → full stable) |
| `avg_dump_time_ms` | integer | Average dump duration per cycle in ms (full stable → empty confirmed) |
| `hopper_load_times` | jsonb array | Individual fill durations in ms, one per qualifying cycle, ordered by time |

### `idle_gaps` Array Structure

Each element:
```json
{
  "start_utc": "2026-03-26T10:00:00+00:00",
  "end_utc": "2026-03-26T12:05:00+00:00",
  "duration_minutes": 125
}
```

Empty array `[]` means no gaps ≥ 2 hours were detected.

### `hopper_load_times` Array Structure

Simple array of integers (milliseconds):
```json
[18500, 17200, 19100, 18800, 16900]
```

One entry per qualifying hopper fill cycle in the job window.

---

## Full v2 Payload Example

```json
{
  "schema_version": 2,
  "job_id": "1704575",
  "line_id": "PLP6",
  "machine_id": "PLP6",
  "job_start_record_time_set_utc": "2026-03-26T08:00:00+00:00",
  "job_end_record_time_set_utc": "2026-03-26T12:10:48+00:00",
  "first_erp_timestamp_utc": "2026-03-26T08:00:00+00:00",
  "last_erp_timestamp_utc": "2026-03-26T12:10:48+00:00",
  "cycle_count": 24,
  "dump_count": 24,
  "total_processed_lbs": 7800.0,
  "avg_weight_lbs": 325.0,
  "avg_cycle_time_ms": 150000,
  "basket_dump_count_raw": 48,
  "basket_cycle_count": 24,
  "anomaly_detected": false,
  "first_basket_dump_utc": "2026-03-26T08:05:12+00:00",
  "last_basket_dump_utc": "2026-03-26T12:10:45+00:00",
  "idle_gaps": [],
  "avg_hopper_load_time_ms": 18500,
  "avg_dump_time_ms": 11200,
  "hopper_load_times": [18500, 17200, 19100, 18800, 16900],
  "override_seen": false,
  "override_count": 0,
  "final_set_weight_lbs": 325.0,
  "final_set_weight_unit": "lb",
  "rezero_warning_seen": false,
  "rezero_warning_reason": null,
  "rezero_warning_weight_lbs": null,
  "rezero_warning_threshold_lbs": null,
  "post_dump_rezero_applied": false,
  "post_dump_rezero_last_apply_utc": null,
  "completed_at_utc": "2026-03-26T12:10:50+00:00"
}
```

---

## `scale_completion_data` — New Columns to Add

These columns need to be added to the raw canonical table.

```sql
ALTER TABLE scale_completion_data
  ADD COLUMN IF NOT EXISTS schema_version          integer,
  ADD COLUMN IF NOT EXISTS basket_dump_count_raw   integer,
  ADD COLUMN IF NOT EXISTS basket_cycle_count      integer,
  ADD COLUMN IF NOT EXISTS anomaly_detected        boolean,
  ADD COLUMN IF NOT EXISTS first_basket_dump_utc   timestamptz,
  ADD COLUMN IF NOT EXISTS last_basket_dump_utc    timestamptz,
  ADD COLUMN IF NOT EXISTS idle_gaps               jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS avg_hopper_load_time_ms integer,
  ADD COLUMN IF NOT EXISTS avg_dump_time_ms        integer,
  ADD COLUMN IF NOT EXISTS hopper_load_times       jsonb DEFAULT '[]'::jsonb;
```

---

## `receive-scale-webhook` Edge Function — What to Update

The edge function needs to:

1. **Read `schema_version`** from the payload to know which shape arrived.

2. **Handle the field rename** — for v1 payloads that still have `basket_dump_count`, map it to `basket_dump_count_raw` before storing. For v2 payloads, read `basket_dump_count_raw` directly.

3. **Store all new fields** into `scale_completion_data`:

```typescript
const isV2 = payload.schema_version === 2;

const basketDumpCountRaw = isV2
  ? payload.basket_dump_count_raw
  : payload.basket_dump_count ?? null;

await supabase.from('scale_completion_data').upsert({
  // ... existing fields ...
  schema_version:          payload.schema_version ?? 1,
  basket_dump_count_raw:   basketDumpCountRaw,
  basket_cycle_count:      payload.basket_cycle_count ?? null,
  anomaly_detected:        payload.anomaly_detected ?? null,
  first_basket_dump_utc:   payload.first_basket_dump_utc ?? null,
  last_basket_dump_utc:    payload.last_basket_dump_utc ?? null,
  idle_gaps:               payload.idle_gaps ?? [],
  avg_hopper_load_time_ms: payload.avg_hopper_load_time_ms ?? null,
  avg_dump_time_ms:        payload.avg_dump_time_ms ?? null,
  hopper_load_times:       payload.hopper_load_times ?? [],
}, { onConflict: 'idempotency_key' });
```

---

## `completed_jobs` — Columns to Mirror

Pull these through from `scale_completion_data` when linking a job:

```sql
ALTER TABLE completed_jobs
  ADD COLUMN IF NOT EXISTS basket_dump_count_raw   integer,
  ADD COLUMN IF NOT EXISTS basket_cycle_count      integer,
  ADD COLUMN IF NOT EXISTS anomaly_detected        boolean,
  ADD COLUMN IF NOT EXISTS first_basket_dump_utc   timestamptz,
  ADD COLUMN IF NOT EXISTS last_basket_dump_utc    timestamptz,
  ADD COLUMN IF NOT EXISTS idle_gaps               jsonb DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS avg_hopper_load_time_ms integer,
  ADD COLUMN IF NOT EXISTS avg_dump_time_ms        integer,
  ADD COLUMN IF NOT EXISTS hopper_load_times       jsonb DEFAULT '[]'::jsonb;
```

---

## `job_efficiency` — Columns Needed for Efficiency Calculation

The efficiency calculation engine will use this data. Columns needed in `job_efficiency`:

```sql
ALTER TABLE job_efficiency
  ADD COLUMN IF NOT EXISTS basket_cycle_count      integer,
  ADD COLUMN IF NOT EXISTS anomaly_detected        boolean,
  ADD COLUMN IF NOT EXISTS first_basket_dump_utc   timestamptz,
  ADD COLUMN IF NOT EXISTS last_basket_dump_utc    timestamptz,
  ADD COLUMN IF NOT EXISTS total_job_minutes       integer,
  ADD COLUMN IF NOT EXISTS total_idle_minutes      integer,
  ADD COLUMN IF NOT EXISTS active_time_minutes     integer,
  ADD COLUMN IF NOT EXISTS avg_hopper_load_time_ms integer,
  ADD COLUMN IF NOT EXISTS avg_dump_time_ms        integer,
  ADD COLUMN IF NOT EXISTS efficiency_pct          numeric;
```

---

## Idle Gap Resolution Logic (Inside `dispatch-scale-webhook` or a new function)

When a webhook arrives, for each entry in `idle_gaps`:

```sql
-- Check if a downtime event covers this gap
SELECT id FROM completed_events
WHERE machine_id = $machine_id
  AND start_time <= $gap_end_utc
  AND end_time   >= $gap_start_utc
LIMIT 1;
```

- If a downtime record overlaps → gap is legitimate, exclude from efficiency penalty
- If no downtime found → unexcused gap, add `duration_minutes` to `total_idle_minutes`

Then:

```
total_job_minutes  = (job_end_utc - job_start_utc) in minutes
active_time_minutes = total_job_minutes - total_idle_minutes
efficiency_pct      = (basket_cycle_count × machine_theoretical_cycle_min) / active_time_minutes × 100
```

`machine_theoretical_cycle_min` is hardcoded per machine in Supabase (e.g., PLP6 = 2.5 min). This is the baseline to compare against.

---

## Backward Compatibility Rules

| `schema_version` | `basket_dump_count` present | `basket_dump_count_raw` present | Action |
|---|---|---|---|
| 1 or missing | yes | no | Map `basket_dump_count` → `basket_dump_count_raw`, set new fields to null |
| 2 | no | yes | Read all fields directly |

Do not reject v1 payloads — the Pi may still send v1 until restarted.

---

## What Is NOT Changing

These existing fields are unchanged and still required:

- `job_id`, `line_id`, `machine_id`
- `job_start_record_time_set_utc`, `job_end_record_time_set_utc`
- `completed_at_utc`
- All `rezero_warning_*` and `post_dump_rezero_*` fields
- `cycle_count`, `dump_count`, `total_processed_lbs`, `avg_weight_lbs`
- `avg_cycle_time_ms`, `final_set_weight_lbs`, `final_set_weight_unit`
- `override_seen`, `override_count`

The idempotency key (dedup logic) is unchanged:
`(line_id, machine_id, job_id, job_start_record_time_set_utc, job_end_record_time_set_utc)`

---

## Testing the New Payload

Once Pi is restarted and a job completes, replay test via PowerShell:

```powershell
$uri = "https://yvpkeqfqwxuacncvzhwc.supabase.co/functions/v1/receive-scale-webhook"
$payload = @{
  schema_version             = 2
  job_id                     = "TEST-001"
  line_id                    = "PLP6"
  machine_id                 = "PLP6"
  job_start_record_time_set_utc = "2026-03-26T08:00:00+00:00"
  job_end_record_time_set_utc   = "2026-03-26T12:10:48+00:00"
  cycle_count                = 24
  dump_count                 = 24
  total_processed_lbs        = 7800.0
  avg_weight_lbs             = 325.0
  avg_cycle_time_ms          = 150000
  basket_dump_count_raw      = 48
  basket_cycle_count         = 24
  anomaly_detected           = $false
  first_basket_dump_utc      = "2026-03-26T08:05:12+00:00"
  last_basket_dump_utc       = "2026-03-26T12:10:45+00:00"
  idle_gaps                  = @()
  avg_hopper_load_time_ms    = 18500
  avg_dump_time_ms           = 11200
  hopper_load_times          = @(18500, 17200, 19100)
  final_set_weight_lbs       = 325.0
  final_set_weight_unit      = "lb"
  override_seen              = $false
  override_count             = 0
  rezero_warning_seen        = $false
  completed_at_utc           = "2026-03-26T12:10:50+00:00"
}
Invoke-WebRequest -Method Post -Uri $uri -ContentType "application/json" -Body ($payload | ConvertTo-Json -Compress -Depth 5)
```

Verify in Supabase:
- `scale_completion_data` row has non-null `basket_dump_count_raw`, `hopper_load_times`, etc.
- `completed_jobs` row is linked and mirrors the new columns
- `job_efficiency` row is created with `active_time_minutes` and `efficiency_pct` populated
