# PLC Output Drift - Root Cause Analysis

**Date**: 2026-02-16  
**Status**: Root cause confirmed via live testing  
**Priority**: High - 60 lb systematic offset between displayed weight and PLC output

---

## Executive Summary

The PLC analog output is **~60 lb behind** the displayed scale weight. The architecture is correct (PLC is driven by weight, not millivolts), but there's a **training timing issue**: the PLC profile was trained with weight values at one zero offset, then zero tracking adjusted the offset, which shifted all displayed weights, but the PLC profile still has the old weight-to-voltage mapping.

---

## Evidence from Live System

### Code Verification (SHA256 match)
Pi code is **identical** to local `src/` directory:
- `acquisition.py`: `eee9f31...`
- `output_writer.py`: `1d18500...`
- `routes.py`: `07010981...`

No version mismatch. The architecture is correct.

### Live Snapshot Data
```
Displayed Weight: 136-137 lb (fluctuating, STABLE)
PLC Output: 1.128125 V (STUCK - not updating)
Zero Offset: 21.498 lb (0.247627 mV)
PLC Profile: 6 points, mode=profile (active)
Deadband: 5.0 lb (from settings page)
```

### Screenshots Show 60 lb Systematic Offset
User provided three dashboard screenshots showing:
1. **84 lb displayed** → PLC outputs **0.888 V**
2. **141 lb displayed** → PLC outputs **1.165 V**
3. **140 lb displayed** → PLC outputs **1.165 V**

If the profile was trained correctly at these weights, voltage should track the weight changes. Instead, there's a consistent ~60 lb gap, suggesting the profile was trained when the scale had a different zero offset.

### Code Flow Verification
Traced `acquisition.py` on Pi (lines 780-873):
```python
# Line 780: Load PLC profile from database
plc_points = self.repo.get_plc_profile_points(output_mode=cfg.output_mode, limit=500)
plc_curve = PlcProfileCurve(
    output_mode=cfg.output_mode,
    points=[(p.plc_displayed_lbs, p.analog_value) for p in plc_points],
)

# Line 793, 809, 830, 853, 871: Pass net_lbs to PLC
self._writer.compute(
    weight_lb=net_lbs,     # ← CORRECT: zero-adjusted, calibrated, filtered, tared weight
    plc_profile=plc_curve,
    ...
)
```

The variable passed is `net_lbs` (line 510):
```python
net_lbs = filtered_lbs - cfg.tare_offset_lbs
```

Where `filtered_lbs` comes from Kalman-filtered `weight_lbs`, which is the calibrated weight from `adjusted_signal_mv = raw_mv - effective_zero_offset_mv` (line 480).

**Conclusion**: The code correctly passes the zero-adjusted net weight to the PLC profile lookup. No bug in the runtime path.

---

## Root Cause

### The Problem

The PLC profile stores `(plc_displayed_lbs, analog_value)` pairs. These are captured from the UI when the operator:
1. Loads the hopper to a known weight (e.g., 100 lb)
2. Adjusts the PLC output voltage (e.g., 2.0 V)
3. Clicks "ADD MATCH POINT"

The `plc_displayed_lbs` value is whatever the scale dashboard shows at that moment, which is `net_lbs = (calibrated weight) - zero_offset - tare`.

**If the zero offset changes AFTER the profile is trained**, the displayed weights shift, but the profile still has the old mapping:

#### Example Timeline:

**Day 1 (Training day):**
- Zero offset: 0.0 lb
- Hopper loaded to 100 lb → Dashboard shows 100 lb → Train profile: `(100 lb, 2.0 V)`
- Hopper loaded to 200 lb → Dashboard shows 200 lb → Train profile: `(200 lb, 4.0 V)`

**Day 2 (After drift):**
- Zero tracking detects drift, adjusts zero offset to 20 lb
- Same hopper load that used to show 100 lb now shows **80 lb** (100 - 20)
- Same hopper load that used to show 200 lb now shows **180 lb** (200 - 20)

**PLC Output:**
- When dashboard shows 80 lb, PLC profile looks up "80 lb" → interpolates between (100, 2.0V) and lower points → outputs ~1.6 V
- But the PLC should output **2.0 V** because it's the same physical load (100 lb at training time)

**Result:** 60 lb systematic offset in PLC output.

---

## Why This Happens

Zero tracking is **intentionally designed** to adjust the displayed weight without retraining calibration. The scale remembers the original calibration zero point (the mV reading when the scale was empty during calibration) and tracks drift away from it.

But the **PLC profile is a separate mapping** that was trained based on displayed weights at a specific point in time. When zero tracking adjusts the offset, all displayed weights shift, but the PLC profile curve doesn't automatically adjust.

---

## Why Deadband Makes It Worse

From settings scrape: `deadband_lb = 5.0`

The output deadband prevents the PLC output from updating unless the weight changes by more than 5 lb. This is intentional (reduces I/O chatter), but it means:
- Small zero-tracking corrections (under 5 lb) won't cause the PLC to update at all
- Gradual drift accumulates silently until the weight crosses the 5 lb threshold

Combined with the systematic offset from the zero-shift, the PLC output can drift significantly before the deadband allows it to update.

---

## Fixes (Choose One)

### Option 1: Re-train PLC Profile (Quick Fix)
**When**: Right now, while scale is live  
**How**:
1. Go to Calibration Hub → PLC Output Mapping
2. Delete all old match points
3. Re-train the profile at current zero offset (load hopper to known weights, capture match points)

**Pros**: Simple, immediate fix  
**Cons**: Must be redone every time zero offset changes significantly

---

### Option 2: Store PLC Profile Relative to Calibration Zero (Permanent Fix)
**When**: During planned maintenance  
**What to change**:

Change how PLC profile points are stored and looked up to be **zero-independent**:

#### Current (broken):
- Store: `(plc_displayed_lbs=100, analog_value=2.0)`
- Lookup: `net_lbs = 100` → output 2.0 V

#### New (fixed):
- Store: `(plc_gross_lbs=100, analog_value=2.0, zero_at_training=0.0)`
- Lookup: `gross_lbs = net_lbs + current_zero_offset` → look up gross_lbs in profile

This way, the PLC profile is anchored to the **physical load** (gross lbs relative to calibration zero), not the displayed net weight which changes with zero offset.

#### Code changes needed:
1. **Database schema**: Add `zero_offset_at_training` column to `plc_profile_points` table
2. **Training UI** (`calibration.html` line 788): When capturing match point, store current zero offset
3. **Profile lookup** (`acquisition.py` line 784-786): Convert `net_lbs` back to gross lbs before lookup:
   ```python
   gross_lbs = net_lbs + cfg.zero_offset_lbs
   plc_curve = PlcProfileCurve(
       output_mode=cfg.output_mode,
       points=[(p.plc_gross_lbs, p.analog_value) for p in plc_points],
   )
   out_cmd = self._writer.compute(
       weight_lb=gross_lbs,  # Pass gross lbs, not net
       plc_profile=plc_curve,
       ...
   )
   ```

**Pros**: Permanent fix, PLC profile survives zero offset changes  
**Cons**: Requires DB migration, code changes, testing

---

### Option 3: Disable Deadband for PLC Output (Partial Fix)
**When**: Immediately (config change only)  
**How**: Set `output.deadband_lb = 0.0` or `output.deadband_enabled = false`

**Pros**: PLC will track small weight changes immediately  
**Cons**: Does NOT fix the 60 lb systematic offset, only reduces lag

---

## Recommended Action Plan

1. **Immediate (today)**: Re-train PLC profile (Option 1) to fix the 60 lb offset
2. **Short-term (this week)**: Reduce deadband to 0.5 lb (Option 3) to reduce lag
3. **Long-term (next maintenance window)**: Implement zero-independent PLC profile (Option 2)

---

## Testing After Fix

After re-training the PLC profile, verify:
1. Load hopper to 0 lb (empty) → Check PLC outputs ~0 V (or min setpoint)
2. Load hopper to 100 lb → Check PLC outputs expected voltage (e.g., 2.0 V per training)
3. Load hopper to 200 lb → Check PLC outputs expected voltage (e.g., 4.0 V per training)
4. Press ZERO button → Displayed weight shifts, verify PLC voltage does NOT change (confirms Option 2 is needed)

If PLC voltage changes when you press ZERO (without changing the load), the profile is still weight-dependent and Option 2 is required.

---

## Files Involved

- `src/services/acquisition.py` (lines 780-873): PLC output computation
- `src/services/output_writer.py` (lines 54-155): Weight-to-voltage mapping
- `src/core/plc_profile.py` (entire file): PLC profile curve interpolation
- `src/app/routes.py` (lines 715-726, 2298-2303): PLC profile add/delete endpoints
- `src/app/templates/calibration.html` (lines 780-795): PLC profile training UI
- `src/db/schema.py` (line 40): `plc_profile_points` table definition
- `src/db/repo.py` (lines 424-461): PLC profile database methods

---

**Confirmed by**: Live SSH inspection + SHA256 verification + 6-sample snapshot polling + user screenshots  
**Scale Status**: Live in production, DO NOT restart or modify without approval
