# ZERO vs TARE Fix - Weight Drift Solution

## Problem Identified

The scale was showing **7 lbs drift overnight** even after calibration. This happened because the ZERO button was incorrectly implemented as a TARE operation.

### Root Cause

**What SHOULD happen with proper calibration:**
- When you calibrate: `5.61 mV = 0 lbs`, `6.37 mV = 25 lbs`
- The calibration factor: `(6.37 - 5.61) / 25 = 0.0304 mV/lb`
- If signal drifts to `5.85 mV` overnight, it shows ~8 lbs (drift!)

**What WAS happening (the bug):**
1. Calibration: `5.61 mV = 0 lbs`
2. Overnight drift: signal → `5.85 mV`
3. Calibration says: `5.85 mV ≈ 8 lbs`
4. You hit ZERO → it was ADDING to the zero offset (0 + 5.85 = 5.85)
5. Multiple ZERO presses compounded: 0 → 5.85 → 11.7 → 17.5 → 23.4 mV!
6. With offset of 23.4 mV, calibrated signal becomes negative → **-376 lbs!**

---

## Solution Implemented

### 1. Fixed ZERO Button (Calculates DRIFT from Calibration Zero)

**File: `src/app/routes.py`**

The ZERO button now:
1. **Finds the calibration zero point** (signal that = 0 lbs in your calibration)
2. **Calculates drift** = current_signal - calibration_zero_signal
3. **Sets zero offset** = drift (NOT adds to old offset!)

```python
# Find calibration zero point (signal value that = 0 lbs)
cal_points = repo.get_calibration_points(limit=200)
zero_point = min(matching_points, key=lambda p: abs(float(p.known_weight_lbs)))
cal_zero_signal = float(zero_point.signal)  # e.g., 5.61 mV

# Calculate drift
drift = current_signal - cal_zero_signal  # e.g., 5.85 - 5.61 = 0.24 mV

# Set (not add!) the offset
new_offset = drift  # 0.24 mV
scale["zero_offset_signal"] = new_offset
```

### 2. Applied Zero Offset in Acquisition Loop

**File: `src/services/acquisition.py`**

Before calibration is applied:
```python
# Apply zero offset (signal domain) - this shifts the calibration baseline
calibrated_signal = float(total_signal) - float(cfg.zero_offset_signal)

# THEN apply calibration curve
raw_weight = curve.weight_from_signal(float(calibrated_signal))
```

**Example:**
- Raw signal: 5.85 mV (drifted)
- Zero offset: 0.24 mV (drift amount)
- Calibrated signal: 5.85 - 0.24 = 5.61 mV
- Calibration says: 5.61 mV = **0 lbs** ✓

### 3. Implemented Robust Zero Tracking (Automatic Drift Compensation)

**Files: `src/services/acquisition.py`, `src/core/zero_tracking.py`**

Zero tracking automatically adjusts the zero offset when ALL conditions are met:
- The scale is **stable** (not moving/settling)
- Weight reading is within the **zero tracking range** (e.g., ±1.0 lbs)
- Scale has been **unloaded + stable** for the hold time (6 seconds)
- No tare is active (container weight)
- Weight error is **outside deadband** (>0.1 lb)
- Calibration exists (has lbs/mV slope)

**Settings in UI (Settings → Zero & Scale):**
- **Enable Zero Tracking:** ON/OFF (recommended ON)
- **Zero Tracking Range:** 1.0 lb (only tracks when within ±1.0 lbs of zero)
- **Zero Tracking Deadband:** 0.1 lb (stops correcting when close enough)
- **Zero Tracking Hold Time:** 6.0 s (wait period before tracking starts)
- **Zero Tracking Rate:** 0.1 lb/s (max correction speed, smooth and gradual)
- **Persist Interval:** 1.0 s (how often to save offset to disk)

---

## Key Concepts

### ZERO (Calibration Baseline) ✓ FIXED
| Aspect | Description |
|--------|-------------|
| **Purpose** | Fix drift caused by temperature, aging, electronic drift |
| **Domain** | Signal (mV) - adjusts before calibration |
| **When to use** | When scale shows weight when empty (drift) |
| **Effect** | Shifts the entire calibration curve back to baseline |
| **Formula** | `offset = current_signal - calibration_zero_signal` |

### TARE (Weight Offset)
| Aspect | Description |
|--------|-------------|
| **Purpose** | Subtract container weight, known loads |
| **Domain** | Weight (lbs) - adjusts after calibration |
| **When to use** | When you want to zero out a container on the scale |
| **Effect** | Just subtracts weight, doesn't fix drift |

### Zero Tracking (Automatic)
| Aspect | Description |
|--------|-------------|
| **Purpose** | Continuously compensate for drift without manual intervention |
| **How** | Monitors empty scale, slowly adjusts ZERO offset |
| **When** | Always active when enabled and scale is near zero |
| **Effect** | Prevents the overnight drift you experienced |

---

## Signal Flow Diagram

```
SIGNAL PROCESSING FLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Load Cells     Raw          Zero Offset     Calibrated      Calibration      Raw         Tare        Final
(mV each)  →  Signal   →    Applied     →   Signal      →   Curve       →  Weight   →  Applied  →  Weight
              (sum)         (-offset)                       (mV→lbs)                   (-tare)

Example:
[1.5+2.2+1.1+1.05] → [5.85 mV] → [5.85-0.24] → [5.61 mV] → [0 lbs] → [0 lbs] → [0 lbs]
                         ↑                          ↑
                    Drifted!                  Back to normal!
```

---

## Real-World Example

```
CALIBRATION POINTS (your training data)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Signal: 5.610181 mV = 0 lbs   ← calibration zero point
Signal: 6.374191 mV = 25 lbs

Slope: (6.374191 - 5.610181) / 25 = 0.0305 mV/lb


AFTER OVERNIGHT DRIFT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Current signal: 5.85 mV (empty scale, but drifted)
Calibration zero: 5.61 mV
Drift: 5.85 - 5.61 = 0.24 mV

Without fix:
  5.85 mV → calibration → ~8 lbs  ✗ WRONG

After pressing ZERO:
  zero_offset = 0.24 mV (stored)
  5.85 - 0.24 = 5.61 mV → calibration → 0 lbs  ✓ CORRECT

Adding 100 lbs:
  Signal: 5.85 + (100 × 0.0305) = 8.90 mV
  After offset: 8.90 - 0.24 = 8.66 mV
  Calibration: (8.66 - 5.61) / 0.0305 = 100 lbs  ✓ CORRECT
```

---

## Testing Checklist

### Test ZERO Button
- [ ] Calibrate your scale normally
- [ ] Let it drift (or simulate by adjusting hardware)
- [ ] Note the "false" weight shown (e.g., 8 lbs)
- [ ] Hit ZERO when scale is empty and stable
- [ ] Verify it now reads 0 lbs
- [ ] Check Zero Offset shows a small value (~0.2, not 23!)
- [ ] Add a known weight → verify calibration factor is still correct

### Test Zero Tracking
- [ ] Press ZERO button first to fix current drift
- [ ] Enable zero tracking in Settings → Zero & Scale
- [ ] Set range to 1.0 lb, deadband to 0.1 lb, hold to 6-10 sec
- [ ] Let scale sit empty - should show "ACTIVE" status after hold time
- [ ] Add weight (>1 lb) - should lock immediately
- [ ] Remove weight - should resume after 6 sec
- [ ] Monitor logs for "ZERO_TRACKING_STATE" and "ZERO_TRACKING_APPLIED" events
- [ ] Let scale drift overnight - verify it auto-corrects within ±0.1 lb

### Test TARE Still Works
- [ ] Place a container on scale (e.g., 10 lbs)
- [ ] Hit TARE button
- [ ] Verify scale shows 0 lbs
- [ ] Add more weight → verify it shows net weight only

---

## Configuration Fields

| Field | Location | Description |
|-------|----------|-------------|
| `zero_offset_mv` / `zero_offset_signal` | `scale` config | Signal offset applied before calibration (mV) |
| `zero_offset_updated_utc` | `scale` config | Timestamp of last zero update |
| `tare_offset_lbs` | `scale` config | Weight offset applied after calibration (lbs) |
| `zero_tracking.enabled` | config | Enable automatic drift compensation (default: true) |
| `zero_tracking.range_lb` | config | Weight range for activation (default: 1.0 lb) |
| `zero_tracking.deadband_lb` | config | Stop correcting when inside this band (default: 0.1 lb) |
| `zero_tracking.hold_s` | config | Wait time before tracking starts (default: 6.0 s) |
| `zero_tracking.rate_lbs` | config | Maximum correction rate (default: 0.1 lb/s) |
| `zero_tracking.persist_interval_s` | config | How often to save offset during tracking (default: 1.0 s) |

---

## Summary

| Button | What it does | When to use | Fixes drift? |
|--------|--------------|-------------|--------------|
| **ZERO** | Adjusts signal offset to compensate for drift | Scale shows weight when empty | ✅ Yes (instant) |
| **TARE** | Subtracts weight offset | Container on scale | ❌ No |
| **Zero Tracking** | Automatically adjusts ZERO offset when conditions met | Always (when enabled) | ✅ Yes (gradual, automatic) |

**Zero Tracking Status (visible on dashboard):**
- **ACTIVE (tracking):** Corrections happening now
- **ACTIVE (deadband):** Close enough, no correction needed
- **LOCKED (holdoff):** Waiting for hold timer (6 sec)
- **LOCKED (load_present):** Weight on scale, won't adjust
- **LOCKED (unstable):** Scale bouncing, won't adjust
- **LOCKED (tare_active):** Container weight set, won't adjust
- **DISABLED:** Feature turned off in settings

The 4+ lb overnight drift is now handled correctly - either automatically by zero tracking (if enabled and within range), or manually with the ZERO button. The calibration slope (mV per pound) is always preserved!
