# Task: Fix ThroughputCycleDetector — Scale Weight Events Stopped Recording

**Priority:** CRITICAL — blocks Talos AI efficiency analysis for boss demo next week  
**Repo:** hoppers  
**Files to touch:** `src/core/throughput_cycle.py`, `src/services/acquisition.py`, possibly `src/db/repo.py`

---

## What's Broken

The Pi has two parallel tracking systems:

| System | Table | Status |
|--------|-------|--------|
| Opto sensor (basket counter) | `counted_events` | ✅ Working — firing every ~1:45 min |
| Scale weight tracker | `throughput_events` | ❌ STOPPED — last row: 2026-04-10 21:55 UTC |

The `throughput_events` table stopped recording on April 10th at ~9:55 PM UTC. Since then, 38+ basket dumps have been counted by the opto sensor but **zero** have been recorded with weight data.

**Impact:** Every job completion payload sent to Supabase has:
- `dump_count: 0`
- `total_processed_lbs: 0.0`
- `dump_events: []`
- `hopper_load_times: []`
- `avg_weight_lbs: 0.0`

Talos AI receives these and correctly flags `DATA_ISSUE` — no weight data to analyze.

---

## Root Cause (Diagnosed)

The `ThroughputCycleDetector` in `src/core/throughput_cycle.py` is stuck and never completing cycles.

**Evidence from Pi event log (`events` table, last 15 rows):**
```
ZERO_TRACKING_STATE → unstable
ZERO_TRACKING_STATE → load_present  
ZERO_TRACKING_STATE → unstable
ZERO_TRACKING_STATE → load_present
BUTTON_BASKET_DUMP_COUNTED  (opto fires — basket IS being dumped)
BUTTON_BASKET_DUMP_COUNTED
...
```

The scale is seeing weight changes (`load_present`) but immediately going back to `unstable`. This means the detector enters `FILLING` state when weight rises but **never reaches `FULL_STABLE`** because `full_stability_s: 5.0` requires 5 continuous seconds above `full_min_lb: 15.0 lbs` — and the scale keeps going unstable before that timer completes.

**Current thresholds (from Pi config):**
```json
{
  "empty_threshold_lb": 2.0,
  "rise_trigger_lb": 8.0,
  "full_min_lb": 15.0,
  "dump_drop_lb": 6.0,
  "full_stability_s": 5.0,
  "empty_confirm_s": 2.0,
  "min_processed_lb": 5.0,
  "max_cycle_s": 900.0
}
```

**Last 3 good throughput_events (before it stopped):**
```
2026-04-10 21:55 | 20.2 lbs | fill_time: 551ms  | end_of_lot
2026-04-10 21:49 | 68.9 lbs | fill_time: 450ms  | full
2026-04-10 21:44 | 69.6 lbs | fill_time: 512ms  | full
```

Note: `empty_lbs` is `0.0` on the last two rows — the scale was already drifting near zero at empty. This suggests calibration drift has pushed the empty baseline down, making the scale noisy near the cycle boundaries.

The `max_cycle_s: 900.0` guard in the detector aborts and resets any cycle over 15 minutes. This means if instability keeps the cycle from completing, it resets and tries again — forever.

---

## The Fix

### Option A — Reduce `full_stability_s` (Config Change, Low Risk)
The comment in `throughput_cycle.py` already says:
> "Full detection should not require 'stable' in violent hopper motion. We still require sustained time above threshold via full_stability_s."

The current `full_stability_s: 5.0` is too strict for the current scale noise. The code already handles violent machines — the stability check should be relaxed.

**Change:** Reduce `full_stability_s` from `5.0` → `1.5` seconds in config.

This is a runtime config change — no deploy needed, takes effect immediately. But we should also add a floor in code so it can't be set below 0.5s.

### Option B — Add Fallback: Use Opto Dump as Cycle Completion Trigger (Code Change, Medium Risk)
When `basket_dump` fires in `counted_events` but no `throughput_events` row has been written for that cycle window, synthesize a weight event using whatever the scale last read as `full_lbs`.

This is more robust but more complex. Implement only if Option A doesn't fully solve it.

### Option C — Add Diagnostic Logging (Always Do This)
Regardless of A or B, add a warning log when:
- `basket_dump` counted_event fires
- But `ThroughputCycleDetector` is NOT in `DUMPING` or `EMPTY_STABLE` state

This makes the mismatch visible in the `events` table so it's caught immediately next time.

---

## Implementation Plan

### Step 1 — Config fix (immediate, no restart needed)
In `src/services/acquisition.py` or wherever config is applied to `ThroughputCycleConfig`, change the default for `full_stability_s` from `5.0` to `1.5`. Also update it in `config_versions` migration defaults.

### Step 2 — Add diagnostic log (acquisition.py)
In the `basket_dump` handler (around line 2537 in acquisition.py):
```python
elif action == "basket_dump":
    # ADD: log if scale cycle detector is not in expected state
    detector_state = self._throughput_cycle.state  # expose _state as property
    if detector_state not in ("DUMPING", "EMPTY_STABLE"):
        self.repo.log_event(
            level="WARNING",
            code="BASKET_DUMP_CYCLE_MISMATCH",
            message=f"Opto basket_dump fired but ThroughputCycleDetector is in '{detector_state}' — scale may not record this dump.",
            details={"detector_state": detector_state},
        )
```

You'll need to expose `_state` as a read-only property on `ThroughputCycleDetector`:
```python
@property
def state(self) -> str:
    return self._state
```

### Step 3 — Optional: Opto-assisted cycle completion (acquisition.py)
If the scale detector is stuck in FILLING when a basket_dump fires, force-complete the cycle using the last known peak weight. This is a safety net, not the primary fix.

---

## What NOT to Touch

- **Do NOT change the opto sensor logic** — it's working perfectly
- **Do NOT change `counted_events` schema** — it's correct
- **Do NOT restart the Pi service** — Justin will do this when ready
- **Do NOT change `job_completion_outbox` logic** — delivery to Supabase is fine
- **The DB schema is fine** — no migrations needed

---

## Testing

After the fix is staged:
1. Check `events` table for `BASKET_DUMP_CYCLE_MISMATCH` warnings — should be zero once fixed
2. After Justin restarts the service, verify new `throughput_events` rows appear within 2 cycles
3. Verify the next job completion payload to Supabase has `dump_count > 0` and `dump_events` populated

---

## Context

- Talos AI webhook server receives job completion payloads from the Pi
- It analyzes `dump_count`, `dump_events`, `hopper_load_times` to detect efficiency issues
- Boss demo is next week — Talos needs real weight data to give meaningful verdicts
- The opto counter data (`basket_dump_count_raw`, `first/last_basket_dump_utc`) IS working and IS in Supabase — just no weight detail
