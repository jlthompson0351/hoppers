# Zero Tracking Operator Guide

**Updated:** February 25, 2026  
**For:** Industrial Hopper Scale with Automatic Drift Compensation

---

## Quick Start

### The Problem We're Solving
Scales drift overnight due to temperature changes. You might see **-4 lbs** on an empty scale in the morning even though you zeroed it yesterday.

### The Solution
Two ways to fix drift:

1. **Manual ZERO** (instant fix)
   - Press ZERO button when scale is empty and stable
   - Display jumps to **~3 lb** immediately (zero floor)
   - **Why 3 lb?** Prevents PLC output from dropping into dead zone (< 0.1V)
   
2. **Auto Zero Tracking** (automatic, slow fix)
   - Enable in Settings → Zero & Scale
   - System automatically corrects drift when scale is empty
   - No operator action needed
   - **Currently DISABLED** on this system (manual ZERO preferred)

---

## Understanding Zero Tracking

### What It Does
Watches the scale when empty and slowly adjusts the baseline to keep it at 0 lb (or the configured 3 lb target).

### When It Works
ALL conditions must be true:
- ✅ Scale is empty (weight < 1 lb)
- ✅ Scale is stable (not bouncing)
- ✅ Been empty for 6+ seconds
- ✅ Error is > 0.1 lb (outside "good enough" zone)
- ✅ No container/tare weight set

### When It Stops
ANY of these happens:
- ❌ Weight added to scale (locks immediately)
- ❌ Within ±0.1 lb (deadband - close enough!)
- ❌ Scale becomes unstable
- ❌ Tare button pressed (container weight)

---

## Zero Floor Feature (New Feb 20, 2026)

### What Is Zero Floor?
The ZERO button now targets **3 lbs** instead of 0 lbs.

### Why?
- When empty weight was set to 0 lb, PLC output dropped below 0.1V
- PLCs have a "dead zone" below ~0.1V where they can't read accurately
- Setting zero floor to 3 lb keeps PLC output at ~0.19V (safely above dead zone)

### How It Works
1. Press ZERO button when scale is empty
2. Scale reads **3 lb** (not 0 lb)
3. PLC receives ~0.19V (safely above dead zone)
4. **The 3 lb offset is baked into the calibration** - the scale is calibrated with empty = 3 lb

### Important Notes
- This is **NOT** a tare (it's a zero offset)
- Material weight is still accurate (e.g., 50 lb bag reads as 50 lb)
- The 3 lb "floor" is just the baseline empty reading
- Config setting: `scale.zero_target_lb: 3.0`

---

## Settings Explained (Plain English)

### Enable Zero Tracking
**What:** Turns auto-correction on/off  
**Recommended:** **OFF** (for this system - manual ZERO preferred)  
**Why:** Manual ZERO with 3 lb floor is more predictable for operators

---

### Zero Tracking Range (default: 1.0 lb)
**What:** Only corrects when scale reads between -1.0 and +1.0 lb  
**Why:** Safety - won't adjust if real weight is on scale

**Examples:**
- Scale shows **0.5 lb** empty → ✅ Will track (inside range)
- Scale shows **-0.8 lb** empty → ✅ Will track (inside range)  
- Scale shows **5.0 lb** → ❌ Won't track (real load, locked)

**Settings:**
- **1.0 lb:** Good for typical overnight drift
- **2.0 lb:** Handles bigger temperature swings
- **0.5 lb:** More conservative, only tracks small drifts

---

### Zero Tracking Deadband (default: 0.1 lb)
**What:** Stops correcting when reading is within ±0.1 lb  
**Why:** Prevents constant tiny adjustments ("zero hunting")

**Example:**
```
Scale drifts to: 0.4 lb
Tracking corrects: 0.4 → 0.3 → 0.2 → 0.1 lb
STOPS at 0.1 lb (inside deadband - good enough!)
Won't chase perfect 0.000 lb
```

**Settings:**
- **0.05 lb:** Tighter, chases closer to perfect zero
- **0.1 lb:** Balanced (recommended)
- **0.2 lb:** Looser, less aggressive

---

### Zero Tracking Hold Time (default: 6.0 seconds)
**What:** How long scale must be empty before corrections start  
**Why:** Prevents adjusting during transient settle periods

**Example:**
```
10:00:00 - Operator removes bag → Weight: 0.5 lb
10:00:02 - Still settling        → Weight: 0.4 lb
10:00:05 - Stable now            → Weight: 0.4 lb (timer starts)
10:00:11 - Hold complete         → START TRACKING
```

**Settings:**
- **6 sec:** Quick response after operator walks away (recommended)
- **10 sec:** Slower scales or vibration environment
- **30+ sec:** Very slow mechanical settling (rare)

**Note:** You don't need 30 minutes! The system already stops when weight is added, so active weighing naturally locks it.

---

### Zero Tracking Rate (default: 0.1 lb/s)
**What:** Maximum speed of corrections  
**Why:** Smooth gradual changes vs sudden jumps

**Example:**
```
Error: 0.4 lb
Rate: 0.1 lb/s
Time to fix: ~4 seconds (smooth ramp down)

Error: 0.4 lb  
Rate: 0.5 lb/s
Time to fix: <1 second (faster but may be visible)
```

**Settings:**
- **0.05 lb/s:** Very smooth, slow corrections
- **0.1 lb/s:** Balanced (recommended)
- **0.2+ lb/s:** Fast but display may flicker

---

### Negative Weight Hold Time (default: 1.0 second) — NEW v3.0
**What:** How long to wait before auto-zeroing a **negative** reading  
**Why:** Gives the hopper door bounce 1 second to settle, then corrects instantly

**How the hopper cycle works:**
```
1. Hopper fills up (weight: 0 → 120 lb)
2. Dump triggers → door opens → material falls
3. Door closes → hopper bounces for 1-2 seconds
4. Weight settles at -8 lb (zero drift)
   ↓ 1 second holdoff (let bounce settle)
5. FAST AUTO-ZERO fires → corrects all -8 lb in one shot
6. Weight reads 0 lb → ready for next fill
```

**Settings:**
- **0 s:** Instant correction (no wait at all)
- **0.5-1.0 s:** Let the bounce settle first (recommended for hopper scales)
- **2-5 s:** More conservative, for scales with longer settling

**Key difference from normal zero tracking:**
- Normal path (positive weight): requires full stability, 6-second holdoff, gradual rate
- Negative path: tolerates vibration, 1-second holdoff, full correction in one shot

---

### Zero Tracking Persist Interval (default: 1.0 second)
**What:** How often to save offset to disk during tracking  
**Why:** Reduces SD card wear

**Technical:** System adjusts offset every 0.05 sec (20 Hz loop), but only saves to config every 1 second.

**Settings:**
- **0.5 sec:** More frequent saves (slight SD card wear)
- **1.0 sec:** Balanced (recommended)
- **2-5 sec:** Less frequent (lighter disk I/O)

---

## Dashboard Display

### Zero Offset Section
Shows three pieces of info:

**Zero Offset:** `X.XXX lb (Y.YYYYYY mV)`
- Current baseline correction
- Positive or negative values are normal
- Example: `0.123 lb (-0.145560 mV)`

**Zero Tracking:** `ACTIVE (tracking)` or `LOCKED (reason)`
- **ACTIVE (tracking):** Normal positive corrections happening
- **ACTIVE (neg_tracking):** Fast negative correction applied
- **ACTIVE (deadband):** Close enough, no correction needed
- **LOCKED (holdoff):** Waiting for positive holdoff timer (6 sec default)
- **LOCKED (neg_holdoff):** Waiting for negative holdoff timer (1 sec default)
- **LOCKED (load_present):** Weight on scale (above range)
- **LOCKED (unstable):** Scale bouncing (positive weight only)
- **LOCKED (neg_spike):** Extreme spike during negative reading
- **LOCKED (spike):** Extreme spike during positive reading
- **DISABLED:** Feature turned off

**Zero Updated:** `14:23:45`
- Last time offset was changed
- Updates from manual ZERO or auto tracking

---

## Common Questions

### "Will it zero too much?"
**No.** Multiple safety stops:
- Stops at ±0.1 lb deadband (close enough)
- Locks when weight > 1 lb (real load)
- Locks when tare active (container)
- Only adjusts at 0.1 lb/s max (gradual)

### "What if the scale reads negative after a dump?"
**Fixed automatically!** As of v3.0 (Feb 13, 2026), negative weight triggers a **fast auto-zero**:
- Negative weight on a hopper scale is always drift (the scale can't physically weigh negative)
- The system detects the negative reading and corrects the full error in **one shot** after a short 1-second holdoff
- Stability is relaxed — post-dump vibration does NOT block it
- No rate limiting — the entire -8 lb (or whatever it is) is corrected immediately
- Result: weight snaps back to 0 lb before the next fill cycle begins

### "Should I use auto tracking or manual ZERO?"
**Both!**
- **Manual ZERO:** Quick fix for large drift (press button, instant)
- **Auto tracking:** Handles small daily drift automatically

### "Does it mess up my calibration?"
**No.** Zero tracking ONLY adjusts the baseline offset. Your calibration slope (mV per pound) never changes.

```
Calibration slope: 0.0304 mV/lb ← Never touched
Zero offset: varies ← Only this changes
```

---

## Troubleshooting

### "Tracking stays LOCKED (load_present) but scale is empty"
**Cause:** Drift is larger than range setting (e.g., 4 lb drift but range = 1 lb)  
**Fix:** Press ZERO button manually first, then tracking will work for future micro-drifts

### "Tracking won't start"
**Check:**
1. Is it enabled? (Settings → Zero & Scale)
2. Is scale stable? (green STABLE indicator)
3. Is weight < 1 lb? (check dashboard)
4. Has it been empty for 6+ seconds? (check hold_elapsed_s)

### "Display keeps changing slightly"
**Cause:** Tracking is active and correcting  
**Expected:** Should stop once it reaches ±0.1 lb  
**If continuous:** Increase deadband to 0.15 or 0.2 lb

---

## Recommended Settings

### For Hopper Scale (fill/dump cycle) — RECOMMENDED
```
✓ Enable Zero Tracking: ON
✓ Range: 10.0 lb (covers post-dump drift)
✓ Deadband: 0.1 lb  
✓ Hold Time: 6 seconds (normal positive drift)
✓ Negative Hold Time: 1.0 sec (fast negative correction)
✓ Rate: 0.1 lb/s (normal positive drift)
✓ Persist Interval: 1.0 sec
```

### For Typical Industrial Floor Scale (no dump cycle)
```
✓ Enable Zero Tracking: ON
✓ Range: 1.0 lb
✓ Deadband: 0.1 lb  
✓ Hold Time: 6-10 seconds
✓ Negative Hold Time: 1.0 sec
✓ Rate: 0.1 lb/s
✓ Persist Interval: 1.0 sec
```

### For Vibration-Heavy Environment
```
✓ Enable: ON
✓ Range: 1.0 lb
✓ Deadband: 0.15 lb (wider)
✓ Hold Time: 15 seconds (longer)
✓ Rate: 0.08 lb/s (slower)
```

### For Weighing With Long Gaps Between Orders
```
✓ Enable: ON
✓ Range: 1.0 lb
✓ Deadband: 0.1 lb
✓ Hold Time: 10 seconds
✓ Rate: 0.1 lb/s

Don't set hold time to 30 minutes!
The load lock already prevents adjusting during active weighing.
```

---

## Verification Tests

### Test 1: Manual ZERO Works (Zero Floor)
1. Let scale drift (or wait overnight)
2. Note the weight (e.g., -4.0 lb when empty)
3. Press ZERO button
4. ✓ Display should jump to **~3.0 lb** instantly (zero floor)
5. ✓ Zero Offset should show non-zero value
6. ✓ PLC output should be ~0.19V (above dead zone)

### Test 2: Auto Tracking Activates
1. Press ZERO to start clean
2. Enable zero tracking
3. Wait 10 seconds with empty scale
4. ✓ Status should show "ACTIVE (tracking)" or "ACTIVE (deadband)"

### Test 3: Load Locking
1. With tracking active
2. Add >1 lb weight
3. ✓ Status should immediately show "LOCKED (load_present)"
4. Remove weight
5. ✓ After 6 sec, should show "ACTIVE" again

### Test 4: Overnight Drift Correction
1. Enable tracking before leaving
2. Note the zero offset value
3. Next morning, check dashboard
4. ✓ Weight should be within ±0.1 lb
5. ✓ Zero offset may have changed slightly
6. ✓ Events log should show "ZERO_TRACKING_APPLIED"

---

## Events to Monitor

### ZERO_TRACKING_STATE
Logged when tracking status changes:
```json
{
  "active": false,
  "locked": true,
  "reason": "load_present",
  "filtered_lbs": 5.2
}
```

### ZERO_TRACKING_STATE: neg_tracking (NEW v3.0)
Logged when fast negative auto-zero fires:
```json
{
  "active": true,
  "locked": false,
  "reason": "neg_tracking",
  "filtered_lbs": -8.38,
  "hold_elapsed_s": 1.05
}
```

### ZERO_TRACKING_APPLIED
Logged when offset is saved (every ~1 sec during tracking):
```json
{
  "weight_correction_lbs": 0.005,
  "signal_correction_mv": 0.000152,
  "old_zero_offset_mv": -0.145560,
  "new_zero_offset_mv": -0.145408
}
```

### SCALE_ZEROED
Logged when operator presses ZERO:
```json
{
  "method": "weight_based",
  "current_gross_lbs": -4.05,
  "new_zero_offset": -0.145560,
  "drift": -0.145560
}
```
