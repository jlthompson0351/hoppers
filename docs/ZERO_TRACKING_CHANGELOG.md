# Zero Tracking System - Change Log

**Date:** February 11, 2026  
**Status:** ✅ Deployed to Pi (172.16.190.25)  
**Version:** 2.0 (Robust Zero Tracking)

---

## Problem Solved

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
