# Employee Efficiency Feature - Hopper Scale Pi Changes

**Feature:** Employee Efficiency Tracking  
**Component:** Hopper Scale Pi (PLP6)  
**Target File:** `/opt/loadcell-transmitter/src/services/acquisition.py`  
**Date:** 2026-03-26  
**Status:** IMPLEMENTED (2026-03-26) — all code changes staged, 141 tests passing

---

## Overview

Enhance the job completion webhook to include additional timing and dump metrics needed for calculating operator efficiency in Supabase.

**No changes to the core scale logic** — we're just querying existing data and adding it to the webhook payload.

---

## Basket Dump Detection (CH1 Opto Input)

**Hardware setup on PLP6:**
- **CH1** is wired to the basket dump rotation signal
- **Wiring:** VEX1 = positive, IN1 = negative (REVERSED from schematic)
- **Signal:** 2 pulses = 1 basket dump
  - Pulse 1: Basket dumps into paint vat
  - Pulse 2: Basket returns and dumps after spin to remove excess paint

**Software monitoring:**
- `_poll_buttons` in `acquisition.py` already monitors CH1
- Events are logged as `"basket_dump"` type
- Each pulse increments the count
- Total count stored in `counted_summary.get("basket_dump")`

**For efficiency calculation:**
- `basket_dump_count_raw` = total pulses (e.g., 48)
- `basket_cycle_count` = `basket_dump_count_raw / 2` (e.g., 24 actual cycles)
- If `basket_dump_count_raw` is odd → `anomaly_detected = True` (incomplete cycle or maintenance test)

---

## Changes Required

### 1. Query Basket Dump Events

When building the completed job payload (in `_build_completed_job_payload`), after retrieving the existing `basket_dump_count`, add:

```python
# Query all basket_dump events for this job from throughput_events table
dump_events = repo.query_events(
    event_type="basket_dump",  # or however basket dumps are identified
    start_time=lifecycle_state.active_job_started_record_time_set_utc,
    end_time=closed_at_record_time_set_utc,
    order_by="timestamp_utc ASC"
)
```

**Note:** If `repo.query_events()` doesn't exist, you'll need to add a simple SQL query method.

---

### 2. Calculate Basket Cycles

```python
basket_dump_count_raw = int(counted_summary.get("basket_dump", 0))
basket_cycle_count = basket_dump_count_raw // 2  # Integer division
anomaly_detected = (basket_dump_count_raw % 2 != 0)  # Flag odd numbers
```

**Why:** Baskets dump twice per cycle (into paint, then after spin). Raw count / 2 = actual cycles.

---

### 3. Extract First/Last Dump Timestamps

```python
if dump_events and len(dump_events) > 0:
    first_basket_dump_utc = dump_events[0]['timestamp_utc']
    last_basket_dump_utc = dump_events[-1]['timestamp_utc']
else:
    first_basket_dump_utc = None
    last_basket_dump_utc = None
```

---

### 4. Detect Idle Gaps (≥2 Hours)

```python
idle_gaps = []
GAP_THRESHOLD_SECONDS = 2 * 60 * 60  # 2 hours

for i in range(len(dump_events) - 1):
    current_time = parse_timestamp(dump_events[i]['timestamp_utc'])
    next_time = parse_timestamp(dump_events[i+1]['timestamp_utc'])
    
    gap_seconds = (next_time - current_time).total_seconds()
    
    if gap_seconds >= GAP_THRESHOLD_SECONDS:
        idle_gaps.append({
            "start_utc": dump_events[i]['timestamp_utc'],
            "end_utc": dump_events[i+1]['timestamp_utc'],
            "duration_minutes": int(gap_seconds / 60)
        })
```

**Important:** Do NOT filter by downtime on the Pi. Send ALL gaps ≥2 hours. Supabase will cross-reference with the downtime table.

**Design Decision:** Keep Pi logic simple. No external API calls. Just report what you see. Supabase handles the intelligence.

---

### 5. Query Hopper Load Time Data

```python
# Query hopper fill/dump cycle events (throughput_events table)
cycle_events = repo.query_events(
    event_type="hopper_cycle",  # or whatever the cycle event type is
    start_time=lifecycle_state.active_job_started_record_time_set_utc,
    end_time=closed_at_record_time_set_utc
)

# Extract load times (duration_ms field from ThroughputCycleDetector)
hopper_load_times = [event['duration_ms'] for event in cycle_events if 'duration_ms' in event]

if hopper_load_times:
    avg_hopper_load_time_ms = int(sum(hopper_load_times) / len(hopper_load_times))
else:
    avg_hopper_load_time_ms = None
    hopper_load_times = []
```

**Note:** The `ThroughputCycleDetector` already calculates `duration_ms` (fill start → full stable). We just need to retrieve it from the events table.

---

### 6. Calculate Dump Time Metrics

```python
# If cycle events include dump_time_ms or similar:
dump_times = [event.get('dump_time_ms', 0) for event in cycle_events]
avg_dump_time_ms = int(sum(dump_times) / len(dump_times)) if dump_times else None

# Total cycle duration (fill → dump → empty)
total_cycle_durations = [event.get('total_duration_ms', 0) for event in cycle_events]
avg_total_cycle_duration_ms = int(sum(total_cycle_durations) / len(total_cycle_durations)) if total_cycle_durations else None
```

**Note:** Verify field names in the actual `throughput_events` schema. Adjust if needed.

---

### 7. Add New Fields to Webhook Payload

Update the `payload` dictionary in `_build_completed_job_payload`:

```python
payload = {
    # ... all existing fields stay the same ...
    
    # NEW FIELDS:
    "basket_cycle_count": int(basket_cycle_count),
    "anomaly_detected": bool(anomaly_detected),
    
    "first_basket_dump_utc": first_basket_dump_utc,
    "last_basket_dump_utc": last_basket_dump_utc,
    
    "idle_gaps": idle_gaps,
    
    "avg_hopper_load_time_ms": avg_hopper_load_time_ms,
    "hopper_load_times": hopper_load_times,
    
    "avg_dump_time_ms": avg_dump_time_ms,
    "total_cycle_duration_ms": avg_total_cycle_duration_ms
}
```

---

## Example Enhanced Webhook Payload

```json
{
  "schema_version": 1,
  "job_id": "1704575",
  "line_id": "PLP6",
  "machine_id": "PLP6",
  "job_start_record_time_set_utc": "2026-03-26T08:00:00Z",
  "job_end_record_time_set_utc": "2026-03-26T12:10:48Z",
  
  "cycle_count": 24,
  "dump_count": 24,
  "basket_dump_count": 48,
  
  "basket_cycle_count": 24,
  "anomaly_detected": false,
  
  "first_basket_dump_utc": "2026-03-26T08:09:12Z",
  "last_basket_dump_utc": "2026-03-26T12:10:45Z",
  
  "idle_gaps": [
    {
      "start_utc": "2026-03-26T10:00:00Z",
      "end_utc": "2026-03-26T12:00:00Z",
      "duration_minutes": 120
    }
  ],
  
  "avg_hopper_load_time_ms": 23000,
  "hopper_load_times": [22000, 24000, 23000, 21000],
  
  "avg_dump_time_ms": 5000,
  "total_cycle_duration_ms": 28000,
  
  "total_processed_lbs": 7800.0,
  "avg_weight_lbs": 325.0
}
```

---

## Performance Notes

- All queries are filtered by job time window (indexed on `timestamp_utc`)
- For a typical job with 24 baskets: ~24 dump events, ~24 cycle events
- Estimated computation time: <100ms
- Talos confirmed Pi CPU can handle this easily

---

## Deployment Strategy

**Phase 1: PLP6 Only**
- This machine is the only one with the smart scale and opto input wired
- Other machines (PLP7, etc.) may be added later but will require different configurations due to legacy equipment differences

## ✅ PREREQUISITE: Threshold Calibration — RESOLVED

`HANDOFF-THRESHOLD-FIX.md` is marked RESOLVED (2026-03-26). Live DB confirmed 4,725 throughput_events rows, 143 webhooks sent. Thresholds are correctly calibrated.

**Once verified, proceed with the changes below.**

---

## Implementation Checklist

- [x] `throughput_cycle.py` — `fill_time_ms` + `dump_time_ms` added to `ThroughputCycleEvent`; `_full_stable_started_s` + `_dumping_started_s` tracked in detector
- [x] `schema.py` — `SCHEMA_VERSION = 8`, `DDL_V8` adds `fill_time_ms` / `dump_time_ms` indexes
- [x] `migrate.py` — v8 migration block with `ALTER TABLE` guards
- [x] `repo.py` — `add_throughput_event` updated; `get_job_window_throughput_summary` returns `avg_fill_time_ms` + `avg_dump_time_ms`; new `get_job_window_hopper_load_times` and `get_counted_events_in_window` methods added
- [x] `acquisition.py` — 30s basket_dump cooldown; `_persist_throughput_cycle_event` passes new timing fields; `_build_completed_job_payload` updated with all new fields, `schema_version: 2`
- [x] Tests — 141 passing; new cooldown test + payload field assertions added
- [x] Staged to Pi — 5 files copied, takes effect on next approved-window restart

## Post-Restart Verification

- [ ] Confirm `throughput_events` rows have non-null `fill_time_ms` and `dump_time_ms` values after first job
- [ ] Confirm next completed-job webhook has `schema_version: 2`, non-zero `basket_dump_count_raw`, correct `basket_cycle_count`
- [ ] Confirm `first_basket_dump_utc` and `last_basket_dump_utc` are populated
- [ ] Confirm `hopper_load_times` array has one entry per qualifying dump cycle
- [ ] Run for 1 week on PLP6, verify accuracy before considering other machines

---

## Questions?

If any field names or event types don't match what's actually in the code/database, adjust accordingly. The core logic is sound — just map it to your actual schema.

**Next:** After this is implemented and tested, move to `Supabase/HANDOFF-EMPLOYEE-EFFICIENCY.md` for the calculation engine.
