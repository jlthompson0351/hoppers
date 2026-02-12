# PLC Output Verification Runbook

**Purpose**: Verify that the analog output to the PLC is accurate and matches expected values.

---

## Prerequisites

Before running this verification:

1. **I/O must be LIVE**
   - Go to `/settings` → System tab
   - Confirm banner shows **I/O LIVE** (green)
   - Both DAQ and MegaIND should show **ONLINE**

2. **Equipment needed**
   - Multimeter capable of measuring 0-10V DC or 4-20mA
   - Known test weights (optional, for full-system test)

3. **Channel Configuration**
   - Verify only channels with load cells are enabled in Settings → DAQ Channels
   - Disable all unused channels to prevent ghost signals

---

## Bench Test: Signal Stability Check (Recommended Before Field Deployment)

Before connecting to your PLC, verify the output signal is rock-solid and won't cause the PLC display to bounce.

### Test Procedure

1. **Configure System**
   - Calibrate with at least 1 point (2+ points recommended for production accuracy)
   - Enable deadband (Settings → Output Control)
     - Recommended: 0.5 lb deadband
   - ARM the output

2. **Apply Stable Load**
   - Place weight on scale (doesn't need to be precisely known)
   - Wait for STABLE indicator
   - Leave undisturbed for test

3. **Monitor Voltage Stability**
   - Connect multimeter to MegaIND analog output terminals
   - Observe voltage for 10-30 seconds
   - Record any variation

### Pass Criteria

| Metric | Expected | Acceptable | Fail |
|--------|----------|------------|------|
| **Voltage Variation** | 0.000V | <0.001V | >0.005V |
| **Weight Jitter** | ±0.1 lb | ±0.5 lb | >1.0 lb |

**Example Good Result:**
```
Sample readings over 30 seconds:
2.456V, 2.456V, 2.456V, 2.456V, 2.456V
Weight: 245.6 lb ±0.2 lb
✅ PASS - Signal is rock solid
```

**Example Poor Result:**
```
Sample readings over 30 seconds:
2.450V, 2.465V, 2.458V, 2.472V, 2.443V
Weight: 245 lb ±2 lb
❌ FAIL - Check channel config, filtering, mechanical vibration
```

### Troubleshooting Unstable Signals

If voltage bounces:
1. Verify only load cell channels enabled (Settings → DAQ Channels)
2. Check deadband is enabled (0.5 lb minimum)
3. Review Kalman filter settings (increase R if too sensitive)
4. Look for mechanical vibration sources
5. Verify load cell cable shielding and grounding

---

## Quick Test: Calibration Hub Nudge (Fastest)

Use the UI's built-in nudge controls to command specific output values without needing weights.

### Steps

1. Navigate to **Calibration Hub** (`/calibration`)
2. Scroll to **PLC Output Mapping**:
   - Confirm **ARM OUTPUTS** toggle is ON (defaults to armed on startup)
   - Use the **Live Slider** or **+/- buttons** to nudge the output value
   - Verify the value displayed matches your multimeter
3. Measure at MegaIND AO terminals with multimeter
4. Repeat for key points:

| Test Point | Set Value | Expected Reading |
|------------|-----------|------------------|
| 0%         | 0.0V      | 0.00 ±0.10V      |
| 25%        | 2.5V      | 2.50 ±0.10V      |
| 50%        | 5.0V      | 5.00 ±0.10V      |
| 75%        | 7.5V      | 7.50 ±0.10V      |
| 100%       | 10.0V     | 10.00 ±0.10V     |

5. **Disable Test Mode when done!**

### Half-Scale Decision Gate (1.0V / 2.0V)

Use this when outputs appear exactly half of expected.

1. Go to **Calibration Hub** (`/calibration`) and confirm outputs are armed (default).
2. Use quick buttons:
   - `SET 1.000`
   - `SET 2.000`
3. Measure at MegaIND AO terminals with a multimeter.

Interpretation:

| Commanded | Measured | Likely Cause |
|-----------|----------|--------------|
| 1.000V / 2.000V | ~1.000V / ~2.000V | Hardware path is correct. Issue is weight->output mapping (range/profile config). |
| 1.000V / 2.000V | ~0.500V / ~1.000V | Hardware/board calibration path issue (MegaIND output calibration, wiring, or meter point). |

If mapping is the issue:
- Confirm **Runtime Mapping** on Calibration Hub:
  - `Profile Curve (active)` uses saved mapping points.
  - `Linear Range (active)` uses Settings min/max.
- For quick linear recovery, click **SYNC RANGE FROM PROFILE** (requires 2+ saved mapping points).

### For 4-20mA Output

| Test Point | Set Value | Expected Reading |
|------------|-----------|------------------|
| 0%         | 4.0mA     | 4.0 ±0.2mA       |
| 25%        | 8.0mA     | 8.0 ±0.2mA       |
| 50%        | 12.0mA    | 12.0 ±0.2mA      |
| 75%        | 16.0mA    | 16.0 ±0.2mA      |
| 100%       | 20.0mA    | 20.0 ±0.2mA      |

---

## Full System Test: Weight-to-Output

Verify the complete signal path: load cells → DAQ → weight calculation → analog output.

### Steps

1. **Ensure system is calibrated** (at least 1 point; 2+ strongly recommended)
2. **ARM the output** (`/settings` or dashboard output controls)
3. Place known weights on scale
4. Wait for **STABLE** indicator
5. Note dashboard weight reading
6. Measure analog output with multimeter
7. Verify output matches expected curve:

```
Expected output = (weight / max_weight) × (10.0V - 0.0V) + 0.0V
```

### Example (0-150 lb → 0-10V)

| Weight (lb) | Expected Output |
|-------------|-----------------|
| 0           | 0.00V           |
| 37.5        | 2.50V           |
| 75          | 5.00V           |
| 112.5       | 7.50V           |
| 150         | 10.00V          |

---

## Automated Test Script

For detailed logging and pass/fail report:

```bash
# From project root (on Pi)
python scripts/analog_output_test_log.py
```

This interactive script will:
- Guide you through each test point
- Capture dashboard readings
- Calculate expected vs measured error
- Generate a pass/fail report

---

## Manual CLI Test (Low-Level)

For direct hardware verification without the app:

```bash
# Voltage output (0-10V)
megaind 0 uoutwr 1 5.0    # Set channel 1 to 5.0V

# Current output (4-20mA)
megaind 0 ioutwr 1 12.0   # Set channel 1 to 12.0mA

# Read back (if supported)
megaind 0 uoutrd 1      # Read voltage output
```

Or use the shell script:
```bash
./scripts/test_megaind_output.sh 0    # Stack ID 0
```

---

## Manual Output Verification/Nudge

If measured output doesn't match expected due to PLC-side scaling or wiring:

1. Go to **Calibration Hub** (`/calibration`).
2. Use **Test Output** or **Live Slider (Nudge)** to command a known analog value.
3. Verify the PLC reads the same commanded signal.
4. Correct PLC analog scaling/wiring so commanded signal and PLC reading agree.

---

## Troubleshooting

### Output stuck at 0V / 4mA
- Check **Armed** toggle is ON (should default to armed on startup)
- Check for **Fault** state (I/O offline, or excitation if excitation monitoring is enabled)
- Verify MegaIND is **ONLINE** in settings

### Output incorrect but consistent
- Check calibration points are correct
- Verify output mode matches wiring (0-10V vs 4-20mA)
- Verify PLC analog input scaling and engineering units configuration

### Output erratic
- Check stability settings (may need adjustment)
- Verify DAQ readings are stable
- Check for electrical noise

---

## Acceptance Criteria

✅ All 5 test points within tolerance:
- **0-10V mode**: ±0.1V (or ±1% of span)
- **4-20mA mode**: ±0.2mA (or ±1.25% of span)

✅ Output responds within 1-2 seconds of weight change (with ramp disabled)

✅ Output holds stable when weight is stable

---

## Related Documents

- `docs/TODAY_SUMMARY.md` - Full testing workflow and commissioning
- `docs/SCALE_SETTINGS.md` - PLC output configuration options
- `scripts/analog_output_test_log.py` - Automated test script

