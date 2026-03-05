# Prompt: Audit Dump Detection & Weight Storage Pipeline

## CRITICAL SAFETY RULE
**DO NOT restart, redeploy, or update anything on the Pi (172.16.190.25). It is in PRODUCTION. All changes are code-only in the local repo and tested locally. Nothing gets pushed to the Pi without explicit operator approval.**

## Background

The scale system reads weight correctly - if you put 50 lb in the hopper, it reads 50 lb. Calibration is good. But the data being stored in the database during dump cycles is wrong. Example:

- Job set weight target is 190 lb, but `production_dumps.prev_stable_lbs` records 267 lb
- Job set weight target is 100 lb, but `production_dumps.prev_stable_lbs` records 155 lb
- Every dump is recording 40-70% more weight than the actual target
- The baskets are NOT overflowing on the floor, so the hopper is NOT actually dumping 270 lb when the target is 190 lb
- `time_to_fill_resume_s` is null in every single event record - fill detection is not working

This means the dump detection state machine is capturing the wrong readings and storing bad data.

## What You Need To Do

### 1. Trace the dump detection state machine
- Find where the code decides "a dump just happened" (look in `src/services/` for the acquisition loop, throughput tracker, or dump detector)
- Map out the full state machine: IDLE → FILLING → FULL → DUMPING → EMPTY → IDLE (or however it's structured)
- Document what triggers each state transition and what weight thresholds are used

### 2. Find where `prev_stable_lbs` is captured
- This is the "full weight before dump" stored in `production_dumps`
- Determine: at what exact moment is this value grabbed? Is it the peak weight? The last stable reading before the weight drops? An average?
- **This is likely the bug.** If it grabs the reading too late (during refill) or accumulates incorrectly, it will be inflated

### 3. Find where `new_stable_lbs` is captured
- This is the "empty weight after dump"
- Same question: when exactly is this grabbed? Is it reading before the hopper is fully empty?

### 4. Trace the `processed_lbs` calculation
- Currently: `processed_lbs = prev_stable_lbs - new_stable_lbs`
- If either input is wrong, the output is wrong
- Check if there's any offset, tare, or zero-tracking adjustment that should be applied but isn't (or is being double-applied)

### 5. Fix `time_to_fill_resume_s` - it's always null
- Find the code path that's supposed to populate this
- Determine why it never fires
- This is important for accurate cycle time tracking

### 6. Add set weight cross-reference to dump records
- When a dump is recorded, also log the active set weight target at that moment
- Add a column like `target_set_weight_lbs` to `production_dumps` or `throughput_events` (use a migration, don't alter existing data)
- This lets us compare "target was 190, captured 195" to validate accuracy going forward

### 7. Write regression tests
- Test that when weight goes from 0 → 190 → 5 (a dump cycle), the recorded `prev_stable_lbs` is ~190, not 270
- Test that `processed_lbs` matches the actual weight delta
- Test that `time_to_fill_resume_s` gets populated
- Test dump detection at various set weight targets (75, 100, 150, 190, 250 lb)

## Key Files to Investigate
- `src/services/` - acquisition loop, dump detection, throughput tracking
- `src/db/` - database models and insert logic
- `src/core/` - core domain logic
- Database tables: `production_dumps`, `throughput_events`, `events`
- Database: `/var/lib/loadcell-transmitter/data/app.sqlite3` (READ ONLY - do not modify production data)

## Database Schema Reference

```
production_dumps: id, ts, prev_stable_lbs, new_stable_lbs, processed_lbs
throughput_events: id, timestamp_utc, processed_lbs, full_lbs, empty_lbs, duration_ms, confidence, device_id, hopper_id, created_at
events: id, ts, level, code, message, details_json
set_weight_current: line_id, machine_id, set_weight_value, set_weight_unit, set_weight_lbs, source, ...
set_weight_history: id, received_at_utc, line_id, machine_id, set_weight_value, set_weight_unit, set_weight_lbs, source, ...
```

## Evidence From Production Data

| Set Weight Target | Avg `prev_stable_lbs` | Avg `processed_lbs` | Over By |
|---|---|---|---|
| 75 lb | ~130 lb | 127 lb | +69% |
| 100 lb | ~160 lb | 155 lb | +55% |
| 150 lb | ~220 lb | 216 lb | +44% |
| 175 lb | ~250 lb | 246 lb | +41% |
| 190 lb | ~272 lb | 267 lb | +41% |

## Rules
- **DO NOT deploy to the Pi or restart any services**
- Do not delete or modify existing production data
- All fixes should be backward-compatible
- Add new columns via migrations, don't alter existing columns
- Run all tests locally with `pytest`
- Update `docs/TODO_BACKLOG.md` when items are resolved
