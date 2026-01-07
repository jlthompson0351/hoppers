# Calibration Procedure

> **🚀 For complete hardware test and calibration deployment, see:**
> - **`docs/HardwareTestReadiness_TODAY.md`** — Complete runbook with calibration steps
> - **`scripts/verify_calibration.py`** — Interactive calibration verification helper

This document describes the calibration procedure in detail. For a complete step-by-step deployment including bootstrap, hardware verification, calibration, and analog output testing, use the Hardware Test Readiness runbook.

---

## 1. Preconditions
- Mechanical installation complete and load cells properly mounted.
- All load cells wired to DAQ inputs (SIG+/SIG−) and excitation provided by SlimPak Ultra.
- Excitation measurement wired: **EXC+ → MegaIND 0–10V AI**, **EXC− → reference**.
- System has warmed up (recommend 10–20 minutes in production temperature).
- The scale is free of debris and mechanically stable.

## 2. Verify Excitation and Health
1. Open Dashboard.
2. Confirm **excitation voltage** reads near nominal (target ~10V).
3. Confirm no excitation warnings/faults.
4. Confirm per-channel raw readings are not saturated and are plausible.

If excitation is low:
- Check SlimPak supply and wiring.
- Check MegaIND AI wiring reference (EXC− must be the reference).

## 3. Configure Channels
1. Navigate to **Settings → DAQ Channels**.
2. **Enable only the channels with load cells physically connected** (typically 2-4 channels).
3. **Disable all unused channels** to prevent "ghost signals" from affecting readings.
4. Verify each enabled channel shows reasonable mV readings in the live display.

**Important:** Unused DAQ channels may show non-zero readings due to floating high-impedance inputs picking up electrical noise. This is normal ADC behavior - simply disable those channels in the configuration.

## 4. Set Filter and Stability Parameters (initial)
Goal: stable detection works reliably with acceptable response.

Navigate to **Settings > Signal Tuning** and configure:

### Kalman Filter (Recommended - Zero-Lag)
| Parameter | Static Weighing | Dynamic Filling |
|-----------|-----------------|-----------------|
| Process Noise (Q) | 1.0 | 10.0 |
| Measurement Noise (R) | 50 | 25 |

### Stability Detection
| Parameter | Recommended | Notes |
|-----------|-------------|-------|
| Stability Window | 25 samples | ~1.5 sec at 17Hz |
| Stddev Threshold | 1.5 lb | Higher = more lenient |
| Slope Threshold | 1.5 lb/s | Higher = more lenient |

**Important:** STABLE/UNSTABLE indicator does NOT affect weight reading or PLC output - it only blocks Zero/Tare operations. For dynamic filling applications, showing UNSTABLE during filling is normal and expected.

## 5. Perform Zero / Empty Stability
1. Ensure scale is empty.
2. Wait for the UI to indicate **STABLE**.
3. Apply a “zero” action if provided (future button/UI command) or allow auto-zero feature if enabled.
4. Confirm the weight reads near 0 lb.

## 6. Multi-Point Calibration (Piecewise-Linear)
Recommended: 3–10 points spanning the range used in production.

1. Navigate to Calibration.
2. Ensure **ratiometric mode** is ON unless there is a specific reason to disable it.
3. For each point:
   - Place a known weight on the scale.
   - Wait for **STABLE**.
   - Enter the known weight (lb) and click Add.
   - Confirm an event is logged if a point is rejected as unstable.
4. After collecting points, verify:
   - intermediate readings are accurate within expected tolerance
   - end points behave correctly (0 lb and near max)

### Calibration Behavior

**Minimum Points Required**: At least **2 calibration points** are required for the calibration curve to activate. With only 1 point, the system falls back to a default simulation formula (mV × 10 = lbs).

**Extrapolation**: The calibration curve **extrapolates linearly** beyond the calibrated range:
- Weights **below** the lowest calibration point use the slope from the first two points
- Weights **above** the highest calibration point use the slope from the last two points
- This is standard industrial behavior for scales that may see occasional overload

**Example**: If you calibrate 0-75 lb, and then place 150 lb on the scale, the system will correctly extrapolate to ~150 lb using the slope from your last two calibration points.

Notes:
- If vibration prevents stability, adjust filter/stability thresholds and retry.
- If excitation sags under load, ratiometric calibration is strongly preferred.

## 7. PLC Output Mapping (Hand-in-Hand Calibration)
Use this to ensure the PLC display matches the true scale weight exactly. This process links the Pi output directly to the scale weight.

1. Scroll down to **PLC Output Mapping** on the Calibration Hub.
2. Confirm the **Active Port** (set in Settings) is correct.
3. For multiple weights across the range (e.g., 0, 50, 150, 300 lb):
   - Place the weight on the scale and wait for **STABLE**.
   - Use the **Live Slider** and **+/- buttons** to nudge the Pi's output.
   - Watch the PLC screen. When it matches the scale weight, click **ADD MATCH POINT**.
4. The system will now use piece-wise linear math to "bend" the output signal so the PLC reads correctly across the entire span.

**Freeze Mode**: While you are nudging the slider, the Pi "freezes" its normal weight-based logic so the signal stays steady for your meter or PLC.

## 8. Validation
- With calibrated system, apply several test weights and confirm:
  - web UI reads correct weight
  - PLC displayed value matches within tolerance (after PLC profile mapping if used)
- Verify fault-safe output:
  - simulate excitation fault and confirm analog output forces safe value and UI shows fault

**Automated validation helpers:**
```bash
# Interactive calibration verification
python3 scripts/verify_calibration.py
# Captures live readings, compares to known weights, generates pass/fail report

# Analog output test with logging
python3 scripts/analog_output_test_log.py
# Tests 0%, 25%, 50%, 75%, 100% output points with multimeter verification
```

## 9. Display Settings
Configure weight display precision in **Settings > Signal Tuning > Weight Display**:

| Setting | Display | Use Case |
|---------|---------|----------|
| 0 decimals | 75 lb | Rough measurements, hopper filling |
| 1 decimal | 75.2 lb | Standard precision (default) |
| 2 decimals | 75.24 lb | Precision weighing |

## 11. Documentation and Handover
- Export recent logs and calibration records for commissioning package.
- Record:
  - channel mapping
  - excitation nominal
  - filter/stability parameters (Kalman Q, R, stability thresholds)
  - calibration points set
  - PLC profile points (if used)
  - display precision setting

**Backup database:**
```bash
# Create timestamped backup of calibration data
cp /var/lib/loadcell-transmitter/app.sqlite3 \
   ~/backup-$(date +%Y%m%d-%H%M%S).sqlite3
```

---

## 12. Complete Test Procedure

For a comprehensive procedure that includes:
- Fresh Pi OS installation and bootstrap
- Hardware smoke tests (I2C, board detection)
- This calibration procedure with interactive helpers
- Analog output verification with multimeter
- Final checklist and troubleshooting

**See: `docs/HardwareTestReadiness_TODAY.md`**

Estimated time: 2.5-3.5 hours from fresh Pi to calibrated production system.


