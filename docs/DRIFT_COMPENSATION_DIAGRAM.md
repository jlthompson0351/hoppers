# Load Cell Drift Compensation - Visual Explanation

## The Calibration Curve

```
CALIBRATION CURVE (Your Training Data)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Weight (lbs)
    ^
    |
100 |                              ●  (6.37 mV, 25 lbs)
    |                           /
 75 |                        /
    |                     /
 50 |                  /
    |               /
 25 |            ●  
    |         /
  0 |------●----------------------→ Signal (mV)
         5.61                6.37
    (calibration zero)

Calibration Factor: (6.37 - 5.61) / 25 = 0.0305 mV per pound
```

---

## What Happens with Drift

### Scenario: Overnight Temperature Change

```
DAY 1 - After Calibration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Load Cell Output:  5.61 mV
Zero Offset:       0.00 mV
Calibrated Signal: 5.61 - 0.00 = 5.61 mV
Scale Reading:     0 lbs  ✓ Correct!


DAY 2 - Temperature Changed Overnight
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Load Cell Output:  5.85 mV  (drifted up by 0.24 mV)
Zero Offset:       0.00 mV  (not updated yet)
Calibrated Signal: 5.85 - 0.00 = 5.85 mV
Scale Reading:     8 lbs   ✗ Wrong! (empty scale shows weight)

Drift = 5.85 - 5.61 = 0.24 mV = ~8 lbs
```

---

## The OLD (WRONG) Approach - Just TARE

```
TARE (Weight Domain Offset) - WRONG APPROACH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Raw Signal:       5.85 mV (drifted)
2. Zero Offset:      0.00 mV (nothing)
3. Calibrated:       5.85 mV
4. Calibration:      5.85 mV → 8 lbs
5. Tare Offset:      -8 lbs
6. Display:          8 - 8 = 0 lbs ✓ (looks right...)

BUT add 25 lbs of material:
1. Raw Signal:       6.61 mV (5.85 + 25×0.0305)
2. Zero Offset:      0.00 mV
3. Calibrated:       6.61 mV  
4. Calibration:      6.61 mV → 33 lbs (wrong baseline!)
5. Tare Offset:      -8 lbs
6. Display:          33 - 8 = 25 lbs ✓ (coincidence!)

PROBLEM: If drift CONTINUES...
1. Day 3: signal drifts to 6.00 mV empty
2. Calibration:      6.00 mV → 13 lbs
3. Tare Offset:      -8 lbs (old value)
4. Display:          13 - 8 = 5 lbs ✗ Still wrong!

TARE doesn't track changing drift!
```

---

## The NEW (CORRECT) Approach - ZERO

```
ZERO (Signal Domain Offset) - CORRECT APPROACH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When you press ZERO:
1. Read current signal:        5.85 mV
2. Look up calibration zero:   5.61 mV (from calibration points)
3. Calculate drift:            5.85 - 5.61 = 0.24 mV
4. Set zero offset:            0.24 mV (stored in config)

Now every reading:
1. Raw Signal:       5.85 mV (drifted)
2. Zero Offset:      -0.24 mV (subtract drift)
3. Calibrated:       5.85 - 0.24 = 5.61 mV ← back to baseline!
4. Calibration:      5.61 mV → 0 lbs ✓ Correct!
5. Display:          0 lbs ✓

Add 25 lbs of material:
1. Raw Signal:       6.61 mV (5.85 + 25×0.0305)
2. Zero Offset:      -0.24 mV
3. Calibrated:       6.61 - 0.24 = 6.37 mV ← correct!
4. Calibration:      6.37 mV → 25 lbs ✓ Correct!
5. Display:          25 lbs ✓

Even if drift continues:
1. Day 3: signal drifts to 6.00 mV empty
2. Press ZERO again or zero tracking adjusts
3. New drift: 6.00 - 5.61 = 0.39 mV
4. Zero offset updated: 0.39 mV
5. Calibrated: 6.00 - 0.39 = 5.61 mV → 0 lbs ✓
```

---

## Signal Flow Diagram

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ZERO OFFSET                      TARE OFFSET
                    (signal domain)                  (weight domain)
                         ↓                                ↓
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Load    │    │    Raw       │    │  Calibrated  │    │   Filtered   │
│  Cells   │ →  │   Signal     │ →  │   Signal     │ →  │    Weight    │
│ (4 ch)   │    │  (summed)    │    │ (- offset)   │    │    (lbs)     │
└──────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                     │                     │                    │
                     │                     ↓                    │
                     │              ┌──────────────┐            │
                     │              │ Calibration  │            ↓
                     │              │    Curve     │     ┌──────────────┐
                     │              │  (mV → lbs)  │     │   Display    │
                     │              └──────────────┘     │   Weight     │
                     │                     ↓             │  (- tare)    │
                     │              ┌──────────────┐     └──────────────┘
                     │              │  Raw Weight  │
                     │              └──────────────┘
                     │
Example values:      │
                     ↓
            5.85 mV (drifted)
                     │
                     ↓ subtract zero_offset (0.24 mV)
                     │
            5.61 mV (corrected)
                     │
                     ↓ apply calibration curve
                     │
            0 lbs ✓ (correct!)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Zero Tracking (Automatic Mode)

```
ZERO TRACKING ALGORITHM (runs every acquisition cycle ~20Hz)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────┐
│ 1. Read current weight: 0.4 lbs                 │
│    (should be 0 lbs, but drifted)               │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 2. Check: Is |weight| < zero_tracking_range?    │
│    (0.4 lbs < 1.0 lbs)  ✓ YES                   │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 3. Check: Is scale stable?                      │
│    ✓ YES (stddev + slope within thresholds)     │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 4. Check: Has it been stable for hold_s?        │
│    Elapsed: 7.2 sec > 6.0 sec hold  ✓ YES       │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 5. Check: Is error > deadband?                  │
│    0.4 lbs > 0.1 lb deadband  ✓ YES             │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 6. Calculate signal correction:                 │
│    weight_correction = min(0.4, rate × dt)      │
│                      = min(0.4, 0.1 × 0.05)     │
│                      = 0.005 lb this cycle      │
│    signal_correction = 0.005 / lbs_per_mv       │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 7. Update zero offset (throttled persist):      │
│    old: -0.145 mV                               │
│    new: -0.145 + correction                     │
│    Save to config every 1.0 sec                 │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 8. Next cycles gradually converge:              │
│    0.40 → 0.39 → 0.38 → ... → 0.10 lb           │
│    STOPS at 0.10 lb (inside deadband)           │
│    Status: ACTIVE (deadband)                    │
│    Convergence: ~4 seconds for 0.4 lb error     │
└─────────────────────────────────────────────────┘
```

**Key Features (Normal Positive Path):**
- **Hold timer:** Prevents tracking during transient settle periods
- **Deadband:** Stops at ±0.1 lb (prevents zero hunting)
- **Rate limited:** Smooth 0.1 lb/s max (no sudden jumps)
- **Load locked:** Stops immediately when weight added
- **Spike rejection:** Ignores sudden motion/vibration
- **Persistence throttled:** Saves every 1 sec (not every cycle)

---

## Fast Negative Auto-Zero (v3.0 — Hopper Scales)

```
NEGATIVE WEIGHT FAST PATH (runs when filtered_lbs < -deadband)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

On hopper scales, negative weight = ALWAYS drift (can't weigh negative).
After a dump, the correction window is tiny (1-2 seconds before fill).

┌─────────────────────────────────────────────────┐
│ 1. Read current weight: -8 lbs                  │
│    (negative = impossible = drift)              │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 2. Check: Is |weight| < zero_tracking_range?    │
│    (8 lbs < 10 lbs)  ✓ YES                      │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 3. Stability: RELAXED for negatives             │
│    Only extreme spikes block correction.        │
│    Post-dump vibration does NOT block it.        │
│    ✓ PASS (normal bouncing tolerated)           │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 4. Holdoff: negative_hold_s (default 1 sec)     │
│    Much shorter than normal 6-sec hold.         │
│    Elapsed: 1.1 sec > 1.0 sec  ✓ YES            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 5. FULL CORRECTION in one shot:                 │
│    weight_correction = -8.0 lb (entire error)   │
│    signal_correction = -8.0 / lbs_per_mv        │
│    NO rate limiting — instant snap to zero       │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 6. Persist IMMEDIATELY (no throttling)          │
│    Weight: -8 lb → 0 lb in one cycle            │
│    Ready for next fill cycle!                   │
└─────────────────────────────────────────────────┘
```

**Hopper Cycle Timeline:**
```
Time    Event                Weight      Auto-Zero
─────   ─────────────────    ──────      ─────────────────
0.0s    Hopper full          120 lb      LOCKED (load_present)
0.5s    Dump starts          dropping    LOCKED (load_present)
2.0s    Material gone        -5 lb       neg_holdoff starts
2.5s    Door bouncing        -8 lb       neg_holdoff counting
3.0s    Holdoff complete     -8 lb       neg_tracking → CORRECTED!
3.0s    Weight corrected     0 lb        Ready for fill
4.0s    Fill starts          +2 lb       LOCKED (load_present)
```

---

## Why Your Original Thought Was Correct

You said:
> "I thought no matter what when we calibrate it takes the voltage change 
> and breaks it down to say hey this is 0.03 volts a pound and that should 
> be it. So even if I trained it to say hey 3.0 mvolts is 0 lbs and no 
> matter what if you see this 0.03 then its a pound."

**You were absolutely RIGHT!**

| Concept | Description | Stays Same? |
|---------|-------------|-------------|
| **Calibration Factor** | 0.0305 mV per pound | ✓ Yes, always |
| **Calibration Points** | Your training data | ✓ Yes, unchanged |
| **Zero Point** | Signal at 0 lbs | Adjusts for drift |

The ZERO button now properly shifts the baseline without changing your calibration!

---

## ZERO vs TARE - Quick Reference

```
┌────────────────────────────────────────────────────────────────┐
│                        ZERO BUTTON                             │
├────────────────────────────────────────────────────────────────┤
│  Purpose:     Fix drift (temperature, aging, creep)            │
│  Domain:      Signal (mV) - BEFORE calibration                 │
│  Formula:     offset = current_signal - calibration_zero       │
│  When to use: Empty scale shows weight                         │
│  Example:     5.85 mV - 5.61 mV = 0.24 mV offset               │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                        TARE BUTTON                             │
├────────────────────────────────────────────────────────────────┤
│  Purpose:     Subtract container weight                        │
│  Domain:      Weight (lbs) - AFTER calibration                 │
│  Formula:     display = calibrated_weight - tare_offset        │
│  When to use: Container on scale, want net weight              │
│  Example:     15 lbs container → tare = 15, shows 0 lbs        │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                  ZERO TRACKING (Positive Weight)               │
├────────────────────────────────────────────────────────────────┤
│  Purpose:     Automatic drift compensation (no operator action)│
│  How:         Gradually adjusts zero offset when empty         │
│  When:        Scale stable + unloaded for 6+ sec + |wt|<range │
│  Rate:        0.1 lb/s max (smooth, won't see it move)         │
│  Stops:       At ±0.1 lb deadband (close enough!)              │
│  Safety:      Locks when weight > range (real load detected)   │
│  Benefit:     Fixes overnight drift automatically!             │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│            FAST NEGATIVE AUTO-ZERO (v3.0 — Hopper)            │
├────────────────────────────────────────────────────────────────┤
│  Purpose:     Instant correction of negative drift after dump  │
│  How:         Full correction in one shot, no rate limiting    │
│  When:        Weight < -deadband, after 1 sec neg holdoff      │
│  Stability:   Relaxed — tolerates post-dump vibration          │
│  Rate:        UNLIMITED — entire error corrected instantly     │
│  Benefit:     Scale reads 0 lb before next fill begins!        │
└────────────────────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Calibration factor (slope)** = weight per signal unit
   - Comes from your calibration points
   - Remains constant (unless you recalibrate)
   - Example: 0.0305 mV/lb

2. **Zero offset (intercept adjustment)** = drift compensation
   - Calculated as: current_signal - calibration_zero_signal
   - Adjusts for temperature, aging, creep
   - Applied BEFORE calibration curve

3. **ZERO button** = Manual drift correction
   - Use when scale shows weight when empty
   - Shifts calibration baseline back to true zero

4. **TARE button** = Container weight offset
   - Use for buckets, containers, pallets
   - Applied AFTER calibration (weight domain)

5. **Zero Tracking** = Automatic drift correction
   - Continuously monitors and corrects drift
   - No manual intervention needed
   - **The industrial solution to overnight drift!**
