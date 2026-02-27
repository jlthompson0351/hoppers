# Pre-Retrain Data Backup - February 18, 2026

**Purpose:** Saved before the Feb 18/19 retrain session for later study.  
**Pi:** 172.16.190.25 (Hoppers)  
**Captured:** 2026-02-18 ~12:08 UTC (07:08 EST)  
**Last Calibration Session:** 2026-02-16 16:52–17:52 UTC

---

## Live Snapshot at Capture Time

- **Weight:** -21.79 lbs (empty hopper, uncorrected drift)
- **Raw Signal:** 5.8896 mV (cal zero was 6.0935 mV → drifted -0.204 mV)
- **Zero Offset:** 0.0 mV / 0.0 lbs (no correction applied)
- **Zero Tracking:** DISABLED
- **PLC Output:** 0.0144 V (clamped near 0, weight is negative)
- **Boards:** 2/2 online, no faults
- **Loop Rate:** 19.96 Hz
- **Stable:** Yes

### Production Stats
- Shift total: 55,747 lbs
- Day total: 13,940 lbs
- Dump count today: 117
- Avg dump: 119 lbs

---

## Calibration Points (Load Cell → Weight)

All captured 2026-02-16. Overall slope: ~107.95 lbs/mV.

| ID  | Weight (lbs) | Signal (mV) | Captured (UTC)       | Notes |
|-----|-------------|-------------|----------------------|-------|
| 99  | 0.0         | 6.093469    | 16:52:12             | Zero reference |
| 101 | 10.0        | 6.186107    | 16:57:08             | |
| 102 | 25.0        | 6.288033    | 16:59:50             | |
| 103 | 35.0        | 6.375157    | 17:01:37             | |
| 104 | 50.0        | 6.561408    | 17:03:05             | **DUPLICATE** - first 50 lb capture |
| 105 | 50.0        | 6.494306    | 17:05:34             | **DUPLICATE** - second 50 lb capture (lower signal) |
| 106 | 75.0        | 6.772071    | 17:07:24             | |
| 107 | 100.0       | 6.956741    | 17:08:55             | |
| 108 | 150.0       | 7.294930    | 17:10:20             | |
| 109 | 170.0       | 7.659297    | 17:51:21             | **41 min gap** - slope 2-3x steeper (drift contamination) |

### Segment Slopes

| Segment        | Slope (mV/lb) | Notes |
|----------------|---------------|-------|
| 0 → 10 lb      | 0.00926       | Normal |
| 10 → 25 lb     | 0.00679       | Normal |
| 25 → 35 lb     | 0.00872       | Normal |
| 35 → 50 lb     | 0.00795       | Using ID 105 (second capture) |
| 50 → 75 lb     | 0.01112       | Slightly high |
| 75 → 100 lb    | 0.00739       | Normal |
| 100 → 150 lb   | 0.00676       | Normal |
| 150 → 170 lb   | **0.01822**   | **Abnormal** - 41 min gap caused drift inflation |

### Known Issues
1. Duplicate 50 lb point (IDs 104 and 105) creates flat spot in curve
2. 170 lb point captured 41 min after 150 lb - signal drifted during gap
3. No 200 lb point exists (user intended to add but not saved)

---

## PLC Profile Points (Weight → Output Voltage)

All captured 2026-02-16. PLC mode: 0-10V.

| ID | PLC Weight (lbs) | Output (V) | Captured (UTC) | Notes |
|----|-----------------|-----------|----------------|-------|
| 69 | 1.0             | 0.100     | 16:53:14       | PLC floor (gets PLC out of negative) |
| 70 | 10.0            | 0.134     | 16:57:51       | |
| 71 | 25.0            | 0.217     | 17:00:38       | |
| 72 | 36.0            | 0.268     | 17:02:06       | **Last point before PLC zero change** |
| 74 | 51.0            | 0.664     | 17:06:12       | **First point after PLC zero change** |
| 75 | 76.0            | 0.787     | 17:07:58       | |
| 76 | 101.0           | 0.908     | 17:09:26       | |
| 77 | 150.0           | 1.158     | 17:10:41       | |
| 78 | 171.0           | 1.246     | 17:52:06       | |

### PLC Profile Slope Analysis

| Segment          | Slope (V/lb) | Notes |
|------------------|-------------|-------|
| 1 → 10 lb       | 0.00378     | Normal (lower half) |
| 10 → 25 lb      | 0.00553     | Normal (lower half) |
| 25 → 36 lb      | 0.00464     | Normal (lower half) |
| **36 → 51 lb**  | **0.02640** | **5x STEEPER - PLC zero changed mid-session** |
| 51 → 76 lb      | 0.00492     | Normal (upper half) |
| 76 → 101 lb     | 0.00484     | Normal (upper half) |
| 101 → 150 lb    | 0.00510     | Normal (upper half) |
| 150 → 171 lb    | 0.00419     | Normal (upper half) |

### Key Finding: Two Halves with Different Zero Intercepts
- **Lower half (1-36 lbs):** Extrapolate to 0 lbs → ~0.095V base voltage
- **Upper half (51-171 lbs):** Extrapolate to 0 lbs → ~0.417V base voltage
- **Offset between halves:** ~0.32V (PLC zero was changed between 36 and 51 lb training)
- **Consistent slope in both halves:** ~0.005 V/lb

---

## Historic Comparison (Feb 13 Backup)

### Feb 13 Calibration (for reference)

| Weight | Session 1 (old) | Session 2 (new) | Feb 16 (current) | Drift (old→current) |
|--------|----------------|-----------------|------------------|---------------------|
| 0 lb   | 5.776 mV       | 5.958 mV        | 6.093 mV         | +0.317 mV |
| 25 lb  | 6.070 mV       | 6.152 mV        | 6.288 mV         | +0.218 mV |
| 50 lb  | 6.300 mV       | 6.396 mV        | 6.494 mV         | +0.194 mV |
| 100 lb | 6.678 mV       | 6.758 mV        | 6.957 mV         | +0.279 mV |
| 150 lb | 7.116 mV       | 7.197 mV        | 7.295 mV         | +0.179 mV |

### Feb 13 PLC Profile (for reference)

| Weight | Session 1 (old) | Session 2 (new) | Feb 16 lower | Feb 16 upper |
|--------|----------------|-----------------|--------------|--------------|
| 1 lb   | 0.409 V        | 0.380 V         | 0.100 V      | (~0.417 V extrapolated) |
| 25 lb  | 0.523 V        | 0.495 V         | 0.217 V      | -- |
| 50 lb  | 0.636 V        | 0.615 V         | --           | 0.664 V |
| 100 lb | 0.895 V        | 0.861 V         | --           | 0.908 V |
| 150 lb | 1.145 V        | 1.121 V         | --           | 1.158 V |

Feb 16 upper half voltages match Feb 13 old session closely.  
Feb 16 lower half voltages are ~0.3V below Feb 13 (different PLC zero).

---

## Config Snapshot

```json
{
  "zero_tracking": {
    "enabled": false,
    "range_lb": 5.0,
    "deadband_lb": 0.1,
    "hold_s": 6.0,
    "rate_lbs": 0.8,
    "persist_interval_s": 1.0,
    "negative_hold_s": 3.0
  },
  "startup": {
    "delay_s": 5,
    "output_value": 0.0,
    "auto_arm": true,
    "auto_zero": false,
    "require_manual_zero_before_auto_zero": true
  },
  "output": {
    "mode": "0_10V",
    "ao_channel_v": 2,
    "armed": true,
    "deadband_enabled": true,
    "deadband_lb": 0.2,
    "ramp_enabled": false
  },
  "filter": {
    "kalman_q": 7.0,
    "kalman_r": 100.0,
    "stability_window": 15,
    "stability_stddev_lb": 3.0,
    "stability_slope_lbs": 4.0
  },
  "display": {
    "weight_decimals": 0,
    "round_up_enabled": true
  },
  "scale": {
    "zero_offset_mv": 0.0,
    "zero_offset_lbs": 0.0,
    "tare_offset_lbs": 0.0
  }
}
```

---

## Diagnosis Summary (Pre-Retrain)

### Problem 1: Scale Drift (20+ lbs)
- Signal drifting with no zero correction (zero tracking OFF, zero offset = 0)
- At startup: Kalman initialized at -57 to -99 lbs depending on temperature
- Cause: thermal/mechanical load cell drift, no automatic compensation

### Problem 2: PLC/Scale Divergence (15-20 lbs)
- PLC profile has a 5x slope kink between 36-51 lbs from mid-session PLC zero change
- Scale and PLC ARE driven by the same value (net_lbs) in code
- Divergence comes from PLC interpreting the distorted voltage curve differently

### Problem 3: 170 lb Calibration Point Drift
- 41-minute gap before capturing 170 lb point
- Signal drifted during gap, inflating the slope in that segment

### Retrain Plan
1. Clear all cal + PLC profile points
2. Set PLC zero FIRST, don't touch again
3. Zero the Pi scale with empty hopper
4. Train 1 lb floor, then go up in one quick pass
5. Enable zero tracking + smart zero clear after training

---

## Post-Session Fixes Applied (Feb 18 ~12:25 UTC)

### 1. Calibration Retrained (5 new points)
Old calibration cleared. New points captured in 5-minute quick pass:

| Weight | Signal (mV) | Slope (mV/lb) |
|--------|------------|---------------|
| 1 lb | 5.888633 | -- |
| 25 lb | 6.095272 | 0.0086 |
| 50 lb | 6.391172 | 0.0118 |
| 100 lb | 6.799229 | 0.0082 |
| 150 lb | 7.243006 | 0.0089 |

Much more consistent slopes than the old data (no drift-contaminated points).

### 2. PLC Profile Fixed (10 clean points)
Updated old bad points (1 lb, 10 lb) and added real nudge measurements. Removed stale 101 lb point.

**PLC Formula verified:** `voltage = 0.412 + (weight x 0.00503)`

| Weight | Voltage | Source |
|--------|---------|--------|
| 1 lb | 0.417 V | Calculated (formula) |
| 10 lb | 0.462 V | Calculated (formula) |
| 27 lb | 0.546 V | Real nudge (Feb 18) |
| 51 lb | 0.675 V | Real nudge (Feb 18) |
| 76 lb | 0.787 V | Real nudge (Feb 16 - on correct PLC zero) |
| 100 lb | 0.915 V | **Real nudge measurement (Feb 18)** |
| 150 lb | 1.158 V | Real nudge (Feb 16 - on correct PLC zero) |
| 171 lb | 1.246 V | Real nudge (Feb 16) |
| 200 lb | 1.418 V | **Real nudge measurement (Feb 18)** |
| 250 lb | 1.663 V | **Real nudge measurement (Feb 18)** |

All slopes between 0.0042 and 0.0059 V/lb. No kinks, no zigzags.

### 3. Kalman Filter Tuned for Faster Response
- **Before:** Q=7, R=100 (Kalman gain 0.23, ~1.7 lb lag at 10 lbs/sec fill)
- **After:** Q=25, R=25 (Kalman gain 0.62, ~0.3 lb lag at 10 lbs/sec fill)
- Reduces PLC output lag during conveyor filling to prevent hopper overfill

### Still Pending for Retrain
- Zero tracking: still OFF (enable after fresh calibration)
- Smart Zero Clear: still OFF (enable after fresh calibration, set load threshold ~100-120 lb)
- Startup Auto-Zero: still OFF (enable once confirmed empty-at-startup is reliable)

---

## Live Tuning Session (Feb 18 ~12:00-18:00 UTC)

### Problem: Zero Tracking Not Working
Multiple issues discovered and fixed during live production monitoring.

### Issue 1: PLC Profile Wrong (Fixed)
- Old profile had points from wrong PLC zero session (0.1V at 1 lb instead of ~0.42V)
- PLC formula discovered: `weight = (raw / 16384) * 1000` (changed from *500 to *1000)
- Rebuilt profile from 4 real nudge measurements:
  - 17 lbs = 0.406V (live), 100 lbs = 0.915V, 200 lbs = 1.418V, 250 lbs = 1.663V
- Low-end slope (17→100): 0.00613 V/lb
- Upper slope (100→250): 0.00503 V/lb
- 9 new points deployed to database

### Issue 2: Kalman Filter Lag (Fixed)
- Q=7/R=100 → Q=10/R=25 (later user adjusted from our initial Q=25)
- Reduces PLC output lag during filling

### Issue 3: Zero Range Too Low (Fixed)
- range_lb was 10-20, drift was 20-30+
- Tracker said "load_present" when hopper was actually empty with drift
- Set range_lb = 25 (normal), post-dump window expands to 50

### Issue 4: Smart Clear Fighting Tracking (Fixed)
- Smart Clear was wiping zero offset every fill cycle (100+ lbs triggered clear)
- Post-dump, empty reading was 5-9 lbs (below 10 lb re-zero threshold), so no re-zero
- Net effect: offset destroyed every cycle, drift accumulated
- **Fix: Smart Clear DISABLED**

### Issue 5: Dump Spikes Eating Zero Offset (Fixed)
- Negative fast path (neg_hold_s=1.0) fired during dump transients
- Dump bounce caused erratic corrections: offset went 40.9 → 34.0 → 11.7 → 8.5
- **Fix: neg_hold_s increased to 8.0 seconds** (longer than any dump transient)

### Issue 6: Manual Zero Gate Blocking Auto-Zero (Fixed)
- `require_manual_zero_before_auto_zero` was True
- After service restart, auto-zero locked until operator pressed ZERO
- **Fix: Set to False, enabled startup_auto_zero**

### Issue 7: Stability Flickering (Fixed)
- Hopper vibration caused stability to toggle every 0.5-1 second
- Holdoff timer could never reach required hold time
- **Fix: Loosened stability thresholds**
  - stddev_lb: 3.0 → 10.0
  - slope_lbs: 4.0 → 25.0
  - hold_s: 6.0 → 0.5

### Code Change: Post-Dump Zero Window
Added to `acquisition.py` - when throughput detector fires a dump event,
zero tracking range expands to `max_correction_lb` (50 lbs) for 10 seconds.
After the window closes, range returns to config value (25 lbs).

### Final Settings (deployed on Pi)
```yaml
zero_tracking:
  enabled: true
  range_lb: 25.0          # Normal range (post-dump window: 50)
  hold_s: 0.5             # Fast fire during stable moments
  negative_hold_s: 8.0    # Wait for dump bounce to settle
  rate_lbs: 50.0          # Near-instant correction
  max_correction_lb: 50.0 # Allows large drift correction
  deadband_lb: 0.1
  smart_clear_enabled: false  # Was fighting with tracking

filter:
  stability_stddev_lb: 10.0   # Tolerates hopper vibration
  stability_slope_lbs: 25.0   # Tolerates hopper vibration
  stability_window: 20
  kalman_Q: 10.0
  kalman_R: 25.0

startup:
  auto_zero: true
  require_manual_zero_before_auto_zero: false
```

### Monitoring
- Hour log captured: `docs/hour_log_1151.txt` (50 min, 2959 lines)
  - Confirmed offset held at 26.63 for entire run (neg hold fix worked)
  - Drift grew from 4-5 lbs to 16-18 lbs over 50 min (range was too low to catch)
- 4-hour shift log running: `/tmp/shift_log_20260218_1310.txt` on Pi
  - Pull with: `pscp -pw depor pi@172.16.190.25:/tmp/shift_log_20260218_1310.txt .`

### Monitoring Script (reusable)
To start a new monitoring session on the Pi:
```bash
# SSH to Pi, then run:
nohup bash -c 'for i in $(seq 1 SECONDS); do \
  curl -s http://localhost:8080/api/snapshot | python3 -c "
import sys,json,datetime
d=json.load(sys.stdin);w=d[\"weight\"];p=d[\"plcOutput\"]
print(f\"{datetime.datetime.now().strftime(\"%H:%M:%S\")} wt={w[\"total_lbs\"]:7.1f} raw={w[\"raw_lbs\"]:7.1f} mv={w[\"raw_signal_mv\"]:.4f} stable={str(w[\"stable\"]):5s} reason={w[\"zero_tracking_reason\"]:20s} hold={w[\"zero_tracking_hold_elapsed_s\"]:.1f}s offset={w[\"zero_offset_lbs\"]:7.2f} plc={p[\"command\"]:.4f}V\")
"; sleep 1; done > /tmp/monitor_log.txt 2>&1' &

# Replace SECONDS with duration:
#   3600 = 1 hour
#  14400 = 4 hours
#  28800 = 8 hours (full shift)
```
