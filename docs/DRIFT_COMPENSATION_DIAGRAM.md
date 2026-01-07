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
│ 1. Read current weight: 0.3 lbs                 │
│    (should be 0 lbs, but drifted)               │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 2. Check: Is |weight| < zero_tracking_range?    │
│    (0.3 lbs < 0.5 lbs)  ✓ YES                   │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 3. Check: Is scale stable?                      │
│    ✓ YES (within stability threshold)           │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 4. Calculate signal correction needed:          │
│    0.3 lbs × 0.0305 mV/lb = 0.009 mV            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 5. Apply rate limiting:                         │
│    Max rate: 0.1 lb/s                           │
│    Max per cycle: 0.1 × 0.05s × 0.0305 = 0.0002 │
│    Actual adjustment = min(0.009, 0.0002)       │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 6. Update zero offset:                          │
│    old: 0.240 mV                                │
│    new: 0.240 + 0.0002 = 0.2402 mV              │
│    (saved to config)                            │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│ 7. Next cycle, weight will be slightly closer   │
│    (0.30 lbs → 0.29 lbs → ... → 0.00 lbs)       │
│                                                 │
│    Convergence: ~3 seconds for 0.3 lb error     │
└─────────────────────────────────────────────────┘
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
│                     ZERO TRACKING                              │
├────────────────────────────────────────────────────────────────┤
│  Purpose:     Automatic drift compensation                     │
│  How:         Slowly adjusts zero offset when near 0 lbs       │
│  When:        Scale stable AND weight < 0.5 lbs                │
│  Rate:        0.1 lb/s (configurable)                          │
│  Benefit:     No manual intervention needed!                   │
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
