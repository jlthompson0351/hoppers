# Zero Tracking System - Change Log

**Date:** February 26, 2026  
**Status:** ⏳ Pending Deployment to Pi (172.16.190.25)  
**Version:** 3.3 (Throughput Spike Guard)

---

## v3.3 — Throughput Spike Guard (February 26, 2026)

### Problem Solved

**Before:** The scale was recording impossible dump weights (e.g., 800+ lbs on a 300 lb machine). Zero drift was inflating the `prev_stable_lbs` reading before the dump. The post-dump rezero logic successfully corrected the baseline, but it applied *after* the cycle was already saved to the database. Additionally, transient mechanical spikes were latching as the `full_lbs` peak. This caused production totals to be artificially inflated (e.g., 30k lbs instead of 11k lbs).

**After:** Throughput counting is now hardened with a strict plausibility guard. Any cycle where `processed_lbs` exceeds the configured physical limit of the machine (`range.max_lb`) is rejected. It is not written to `throughput_events`, `production_dumps`, or `production_totals`. Instead, it emits a structured anomaly event for diagnostics.

### What Changed

#### 1. Hard Plausibility Guard
- The system now reads `range.max_lb` from the configuration.
- If a cycle exceeds this limit, it is dropped from production totals.
- The boundary is deterministic: `processed_lbs == max` is accepted.

#### 2. Structured Anomaly Logging
- Rejected cycles emit a new event: `THROUGHPUT_CYCLE_REJECTED_MAX_WEIGHT`.
- The event includes detailed diagnostics to determine if the spike was a real mV event or transient noise:
  - `processed_lbs`, `full_lbs`, `empty_lbs`, `max_allowed_lbs`
  - `raw_signal_mv`, `adjusted_signal_mv`, `zero_offset_mv`, `zero_offset_lbs`
  - `filtered_lbs`, `target_relative_lbs`, `confidence`, `duration_ms`

#### 3. Operator Control
- The `range.max_lb` setting is now exposed on the main Settings page UI as "Max Cycle Weight (Throughput Guard)" so operators can easily adjust the machine's physical limit.

### Files Modified

**Core Logic:**
- `src/services/acquisition.py` — Added `_persist_throughput_cycle_event` with the max-weight guard and anomaly logging.

**Backend/API:**
- `src/app/routes.py` — Wired `max_lb` persistence from the settings form.

**Frontend:**
- `src/app/templates/settings.html` — Added "Max Cycle Weight (Throughput Guard)" input field.

**Tests:**
- `tests/test_throughput_guard.py` — New test suite verifying rejection logic and anomaly logging.

### Deployment Status
- ⏳ **Pending:** Code is written and tested locally. It needs to be deployed to the Pi when the line is down and it is safe to restart the `loadcell-transmitter` service.

---

## v3.1 — Canonical mV Zeroing & Persistence Fix (February 15, 2026)

### Problem Solved

**Before:** Zero offset was being stored as Pounds (lbs) in a Millivolt (mV) field, causing zeroing operations to fail or behave incorrectly. The system would read `zero_offset_mv` from the database (which contained lbs values), apply it as mV correction to the raw signal, resulting in massive errors (e.g., 100 lb stored as mV would shift the signal by 100 mV instead of the correct ~0.8 mV).

**After:** Complete refactoring to make `zero_offset_mv` the canonical source of truth. All zero operations now work in the signal domain (mV) before calibration, preserving calibration slope integrity.

### What Changed

#### 1. Canonical mV Storage Architecture

**New data flow:**
```
Raw Signal (mV) 
  → Apply zero_offset_mv (signal domain correction)
  → Apply Calibration (mV → lbs conversion)
  → Apply tare_offset_lbs (weight domain offset)
  → Final Weight
```

**Storage changes:**
- `zero_offset_mv` — **CANONICAL** field (always in mV, applied to signal)
- `zero_offset_lbs` — **DERIVED** field for display (`zero_offset_mv * lbs_per_mv`)
- All zero operations calculate in their domain, convert to mV for persistence

#### 2. Manual ZERO Button Fixed

**Old behavior (broken):**
```python
# Incorrectly stored lbs as mV
zero_offset_mv = current_gross_lbs  # WRONG
```

**New behavior (correct):**
```python
# Calculate signal-domain correction
drift_mv = current_raw_mv - calibration_zero_mv
new_zero_offset_mv = old_zero_offset_mv + drift_mv
# Derive display value
zero_offset_lbs = zero_offset_mv * lbs_per_mv
```

#### 3. Zero Tracking Fixed

**Old behavior (broken):**
```python
# Mixed units - stored lbs in mV field
correction_lbs = weight_error
offset_mv = correction_lbs  # WRONG: units mismatch
```

**New behavior (correct):**
```python
# Calculate in lbs, convert to mV for storage
correction_lbs = current_gross_lbs * correction_rate
correction_mv = correction_lbs / lbs_per_mv
new_zero_offset_mv = old_zero_offset_mv + correction_mv
# Derive for display
zero_offset_lbs = zero_offset_mv * lbs_per_mv
```

#### 4. Persistence Race Condition Fixed

**Problem:** Multiple code paths were updating config simultaneously:
- Zero tracking persistence timer (every 1 second)
- Manual ZERO button (immediate)
- Config refresh (every 2-30 seconds)

**Solution:** 
- Centralized zero offset updates through single persistence path
- Throttled zero tracking writes (max once per persist interval)
- Atomic read-modify-write for config updates

#### 5. Database Schema Clarity

**Config JSON structure (now explicit):**
```json
{
  "scale": {
    "zero_offset_mv": -0.145560,        // CANONICAL (signal correction)
    "zero_offset_signal": -0.145560,    // Legacy alias (same as zero_offset_mv)
    "zero_offset_lbs": -0.123,          // DERIVED (for display)
    "zero_offset_updated_utc": "2026-02-15T10:30:00Z",
    "tare_offset_lbs": 0.0              // Independent weight offset
  }
}
```

### Files Modified

**Core Logic:**
- `src/app/routes.py` — Manual ZERO fixed, now calculates drift_mv correctly
- `src/services/acquisition.py` — Zero tracking persistence, unit conversions
- `src/core/zero_tracking.py` — Converts corrections to mV before storage
- `src/db/repo.py` — Config persistence with atomic updates

**Deploy:**
- `deploy_to_pi/routes.py` — Manual ZERO fixed
- `deploy_to_pi/acquisition.py` — Zero tracking persistence fixed
- `deploy_to_pi/repo.py` — Config updates aligned

### Live Verification (Pi at 172.16.190.25)

**User Confirmation:** "Working like a champ"

```
Before deployment:
  Zero operations would fail or produce incorrect results
  Zero offset showed nonsensical values (lbs stored in mV field)
  
After deployment:
  Manual ZERO forces display to 0.0 lb instantly
  Zero tracking converges correctly (negative and positive drift)
  Zero offset displays correct mV and derived lbs values
  System maintains zero across restarts
```

### Key Insights

**Why this bug was critical:**
1. **Unit mismatch:** Storing lbs in a mV field caused 100x+ magnitude errors
2. **Cascade failure:** Broken zero made calibration verification impossible
3. **User impact:** Scale appeared to drift wildly, couldn't maintain zero

**Why the refactor works:**
1. **Single source of truth:** `zero_offset_mv` is always in correct units
2. **Domain separation:** Signal corrections in mV, weight corrections in lbs
3. **Explicit derivation:** `zero_offset_lbs` calculated from canonical value
4. **Calibration integrity:** Slope/gain never modified by zero operations

---

## v3.0 — Fast Negative Auto-Zero (February 13, 2026)

### Problem Solved

**Before:** After a hopper dump, the scale would read -8 lb. The auto-zero holdoff timer (6 seconds) kept resetting because the hopper door bounce caused the stability detector to toggle between `stable` and `unstable` every fraction of a second (`hold_elapsed_s` never exceeded 0.15s). By the time the bouncing settled, material was already loading again. Auto-zero never fired.

**After:** Negative weight is now handled on a dedicated fast path. On hopper scales, negative weight is *always* drift — the scale physically cannot weigh less than the empty hopper. The fast path relaxes stability, shortens the holdoff, and corrects the full error in a single shot.

### What Changed

#### 1. New Dual-Path Zero Tracker (`src/core/zero_tracking.py`)
The `ZeroTracker.step()` method now has two distinct paths:

| | Normal (positive weight) | Fast Negative |
|---|---|---|
| **Stability** | Must be fully stable | Relaxed — only extreme spikes block it |
| **Holdoff** | `hold_s` (default 6s) | `negative_hold_s` (default 1s) |
| **Rate** | `rate_lbs` per second (gradual) | **Full correction in one shot** |
| **Persist** | Throttled (every `persist_interval_s`) | **Immediate** |
| **Reason codes** | `holdoff`, `unstable`, `tracking` | `neg_holdoff`, `neg_spike`, `neg_tracking` |

#### 2. New Configuration Parameter
```python
"zero_tracking": {
    "negative_hold_s": 1.0,   # NEW — holdoff for negative readings (default 1s)
    # ... existing params unchanged ...
}
```

#### 3. Separate Holdoff Gate
The negative path uses its own `_neg_gate_started_s` timer, independent of the normal positive-weight holdoff. This means:
- Negative gate counts even during minor instability
- Normal gate is not disturbed by negative tracking
- When weight transitions from negative to positive, appropriate gate applies

#### 4. New Settings UI Control
Added "Negative Weight Hold Time" in Settings → Zero & Scale:
- `0 s` — Instant correction (no wait)
- `0.5-1.0 s` — Recommended for hopper scales (let bounce settle)
- `up to 10 s` — Conservative

#### 5. New Event Codes
- `ZERO_TRACKING_STATE: neg_holdoff` — Waiting for negative holdoff to complete
- `ZERO_TRACKING_STATE: neg_spike` — Blocked by extreme spike during negative reading
- `ZERO_TRACKING_STATE: neg_tracking` — Actively correcting negative weight
- `ZERO_TRACKING_NEG_FAST` — Fast negative correction applied (deploy_to_pi version)

### Files Modified

**Core Logic:**
- `src/core/zero_tracking.py` — Dual-path ZeroTracker with fast negative logic
- `src/services/acquisition.py` — `negative_hold_s` config field + pass-through

**Backend/API:**
- `src/app/routes.py` — Save `negative_hold_s` from settings form

**Frontend:**
- `src/app/templates/settings.html` — New "Negative Weight Hold Time" control

**Deploy:**
- `deploy_to_pi/acquisition.py` — Matching fast negative logic (inline version)
- `deploy_to_pi/routes.py` — Save `negative_hold_s`
- `deploy_to_pi/settings.html` — New setting control

### Operational Cycle (How It Works)

```
1. LOAD    → Weight increases from 0 to ~120 lb
2. DUMP    → Door opens, material falls, weight drops to ~0 or negative
3. BOUNCE  → Door closes, hopper bounces for 1-2 seconds
4. SETTLE  → Weight at -8 lb (drift from zero)
             ↓
             Fast negative holdoff starts (1 second)
             ↓
5. CORRECT → After 1s: full -8 lb correction applied in ONE SHOT
             Weight reads 0 lb immediately
6. FILL    → Loading starts again from true zero
```

### Live Verification (Pi at 172.16.190.25)

```
Before deployment:
  Weight: -8 lb, Zero Tracking: LOCKED (holdoff), hold_elapsed: 0.15s

After deployment:
  Weight: 2.0 lb, Zero Offset: -8.36 lb applied
  Fast negative auto-zero fired within seconds of restart
```

---

## v2.0 — Robust Zero Tracking (February 11, 2026)

### Problem Solved

**Before:** Scale showed -4 lbs overnight drift. Manual ZERO button existed but auto zero tracking was fragile and didn't work reliably.

**After:** Robust zero tracking with hold timer, deadband, spike guards, and full dashboard visibility.

---

## What Changed

### 1. New Core Modules (Added)
- `src/core/zero_tracking.py` - State machine for auto drift correction
- `src/core/zeroing.py` - Shared helpers for manual ZERO calculation

### 2. Enhanced Configuration (New Defaults)
```python
"zero_tracking": {
    "enabled": True,              # Changed from False
    "range_lb": 1.0,              # Increased from 0.5
    "deadband_lb": 0.1,           # New parameter
    "hold_s": 6.0,                # New parameter  
    "rate_lbs": 0.1,              # Existing
    "persist_interval_s": 1.0,    # New parameter
}

"scale": {
    "zero_offset_mv": 0.0,
    "zero_offset_signal": 0.0,
    "zero_offset_updated_utc": None,  # New field
    "tare_offset_lbs": 0.0,
}
```

### 3. Manual ZERO Algorithm Improved
**Old:** Looked up calibration zero point, subtracted from current signal  
**New:** Uses current gross weight + calibration slope to force true zero

```python
# Old (calibration-zero lookup):
drift = current_signal - cal_zero_signal
offset = drift

# New (weight-based):
correction_signal = current_gross_lbs / lbs_per_mv
new_offset = old_offset + correction_signal
```

**Result:** ZERO button now forces display to 0.0 lb even when span calibration is imperfect.

### 4. Hardware Button ZERO Fixed
**Old:** Cleared tare when pressed (blurred ZERO vs TARE behavior)  
**New:** Only updates baseline offset; tare remains independent

### 5. Dashboard Visibility Enhanced
**Added:**
- Zero offset display in lb + mV
- Last updated timestamp
- Zero tracking status (ACTIVE/LOCKED + reason)
- Real-time hold timer progress

### 6. API Expansion (`/api/snapshot`)
**New fields in `weight` object:**
```json
{
  "zero_offset_mv": -0.145560,
  "zero_offset_lbs": -0.123,
  "zero_offset_updated_utc": "2026-02-11T14:23:45+00:00",
  "zero_tracking_enabled": true,
  "zero_tracking_active": true,
  "zero_tracking_locked": false,
  "zero_tracking_reason": "tracking",
  "zero_tracking_hold_elapsed_s": 7.2
}
```

### 7. Settings UI Updates
**Added controls for:**
- Zero Tracking Deadband
- Zero Tracking Hold Time
- Zero Tracking Persist Interval

**Simplified descriptions** - less technical jargon

### 8. Safety Guards Added
- **Hold timer:** Must be empty for 6 sec before tracking
- **Deadband:** Stops at ±0.1 lb (prevents zero hunting)
- **Spike rejection:** Ignores sudden motion via slope threshold
- **Load threshold:** Locks when |weight| > range
- **Tare block:** Locks when tare active
- **Stability gate:** Locks when scale bouncing
- **Persistence throttling:** Saves every 1 sec (not every 50ms cycle)

### 9. Event Logging Enhanced
**New events:**
- `ZERO_TRACKING_STATE` - when status changes (active/locked/reason)
- `ZERO_TRACKING_APPLIED` - when offset is persisted
- `SCALE_ZEROED` - enhanced with method, gross weight, slope

### 10. Unit Tests Added
**New test file:** `tests/test_zero_tracking.py`
- Baseline remains stable with load
- Gradual drift correction when unloaded
- Manual ZERO baseline math correctness

---

## Files Modified

### Core Logic
- ✅ `src/core/zero_tracking.py` (new)
- ✅ `src/core/zeroing.py` (new)
- ✅ `src/services/acquisition.py` (+150 lines, zero tracker integration)
- ✅ `src/services/output_writer.py` (no changes, just copied to Pi)

### Backend/API
- ✅ `src/app/routes.py` (+80 lines, enhanced manual ZERO + expanded snapshot)
- ✅ `src/db/repo.py` (+6 fields in default config)

### Frontend
- ✅ `src/app/templates/dashboard.html` (3 new info lines + bindings)
- ✅ `src/app/templates/settings.html` (4 new controls, simplified help text)

### Tests
- ✅ `tests/test_zero_tracking.py` (new, 3 deterministic tests)

### Documentation
- ✅ `docs/ZERO_VS_TARE_FIX.md` (updated parameters + status table)
- ✅ `docs/DRIFT_COMPENSATION_DIAGRAM.md` (updated algorithm flow)
- ✅ `docs/CURRENT_IMPLEMENTATION.md` (updated config table + flow)
- ✅ `docs/Architecture.md` (added core modules + signal flow)
- ✅ `docs/ZERO_TRACKING_OPERATOR_GUIDE.md` (new, complete operator reference)
- ✅ `docs/MaintenanceAndTroubleshooting.md` (added zero tracking troubleshooting)
- ✅ `docs/README_DOCS.md` (added new guide to index)

### Deployment
- ✅ `deploy_to_pi/deploy.ps1` (added core files, changed default IP to .25)
- ✅ `deploy_to_pi/deploy_with_password.ps1` (added core files, changed default IP to .25)
- ✅ `deploy_to_pi/dashboard.html` (synced with src/)
- ✅ `deploy_to_pi/routes.py` (synced with src/)
- ✅ `deploy_to_pi/repo.py` (synced with src/)

---

## Deployment Status

### Pi at 172.16.190.25 (Primary)
- ✅ Core modules deployed
- ✅ Acquisition + routes updated
- ✅ Dashboard updated
- ✅ Service restarted successfully
- ✅ Running with new zero tracking engine

### Verification
```bash
# Check service status:
systemctl status loadcell-transmitter

# View recent logs:
journalctl -u loadcell-transmitter -n 50

# Test API:
curl http://localhost:8080/api/snapshot | jq '.weight'
```

---

## Behavioral Changes

### Manual ZERO Button
**Old behavior:**
- Used calibration-zero lookup
- Cleared tare (blurred semantics)

**New behavior:**
- Uses current gross weight + slope (more accurate)
- Keeps tare independent
- Updates timestamp

### Auto Zero Tracking
**Old behavior:**
- Triggered immediately when stable + near zero
- Wrote config every cycle (SD card wear)
- No hold timer or deadband

**New behavior:**
- 6-second hold timer before starting
- ±0.1 lb deadband (stops when close enough)
- Throttled persistence (1 sec intervals)
- Explicit active/locked states
- Full telemetry logging

### Dashboard
**Old behavior:**
- Single line: "Zero Offset: 0.000000 signal"
- No tracking status
- No timestamp

**New behavior:**
- Three lines with full detail:
  - `Zero Offset: X.XXX lb (Y.YYYYYY mV)`
  - `Zero Tracking: ACTIVE (tracking)` or `LOCKED (reason)`
  - `Zero Updated: HH:MM:SS`

---

## Migration Notes

### Existing Deployments
- Old configs are auto-upgraded via `_deep_merge()`
- New fields get safe defaults
- `zero_tracking.enabled` stays `false` for existing installs (preserved)
- New installs default to `enabled: true`

### No Database Migration Required
- New fields use existing `config_versions.config_json`
- Timestamp stored as string in scale object
- Backward compatible

---

## Testing Results

### Unit Tests
```
Ran 8 tests in 0.005s
OK
```

**Coverage:**
- ✅ Baseline unchanged with load
- ✅ Gradual drift correction when unloaded
- ✅ Manual ZERO baseline math
- ✅ Output writer still works (no regressions)

### Live Testing (Pi)
- ✅ Service starts without errors
- ✅ Dashboard loads and polls successfully
- ✅ API returns all new fields
- ✅ Manual ZERO tested: -4 lb → 0 lb instant
- ✅ Zero tracking status updates in real-time

---

## Operator Training Notes

### Key Points to Communicate
1. **ZERO button fixes drift instantly** - use when scale shows weight but is empty
2. **Auto tracking prevents daily re-zeroing** - enable it once, forget about it
3. **It can't over-zero** - stops at ±0.1 lb (close enough)
4. **Works for negative drift too** - math handles both directions
5. **Calibration never changes** - only baseline offset adjusts

### Common Misconceptions
❌ "Tracking will mess up during active weighing"  
✅ It locks when weight > 1 lb, resumes when empty

❌ "Need to wait 30 minutes for it to work"  
✅ Waits 6 seconds after scale empties, then corrects in ~3-5 sec

❌ "It will keep adjusting forever"  
✅ Stops at ±0.1 lb deadband (good enough zone)

---

## Next Steps

### Recommended Actions
1. ✅ **Enable zero tracking** on all deployed scales
2. ✅ Monitor logs for "ZERO_TRACKING_APPLIED" events
3. ✅ Verify overnight drift stays within ±0.1 lb
4. 📋 Document baseline behavior in production logs
5. 📋 Train operators on manual ZERO vs auto tracking

### Future Enhancements (Optional)
- [ ] Adaptive deadband based on calibration accuracy class
- [ ] Email/alert when drift exceeds threshold
- [ ] Historical zero offset trending/charting
- [ ] Multi-scale zero synchronization for summing applications

---

## Support References

- **Operator Guide:** `ZERO_TRACKING_OPERATOR_GUIDE.md`
- **Technical Details:** `ZERO_VS_TARE_FIX.md`
- **Visual Explanation:** `DRIFT_COMPENSATION_DIAGRAM.md`
- **Troubleshooting:** `MaintenanceAndTroubleshooting.md` (Section 3.6)
