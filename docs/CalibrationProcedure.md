# Calibration Procedure

> **🚀 For complete hardware test and calibration deployment, see:**
> - **`docs/HardwareTestReadiness_TODAY.md`** — Complete runbook with calibration steps
> - **`scripts/verify_calibration.py`** — Interactive calibration verification helper

This document describes the calibration procedure in detail. For a complete step-by-step deployment including bootstrap, hardware verification, calibration, and analog output testing, use the Hardware Test Readiness runbook.

---

## 1. Preconditions
- Mechanical installation complete and load cells properly mounted.
- All load cells wired to DAQ inputs (SIG+/SIG−) and excitation provided by SlimPak Ultra.
- Optional (recommended): excitation measurement wired **EXC+ → MegaIND 0–10V AI**, **EXC− → reference**.
- System has warmed up (recommend 10–20 minutes in production temperature).
- The scale is free of debris and mechanically stable.

## 2. Verify Excitation and Health
1. Open Dashboard.
2. If excitation monitoring is enabled, confirm **excitation voltage** reads near nominal (target ~10V).
3. If excitation monitoring is enabled, confirm no excitation warnings/faults.
4. Confirm per-channel raw readings are not saturated and are plausible.

If excitation is low:
- Check SlimPak supply and wiring.
- Check MegaIND AI wiring reference (EXC− must be the reference).
- If excitation is intentionally not wired yet, disable **Enable Excitation Monitoring** in Settings.

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
3. Apply **ZERO** from the dashboard/operator UI or allow auto-zero tracking if enabled.
4. Confirm the weight reads near 0 lb.

## 6. Weight Calibration (Current Runtime)
The current runtime supports:
- **Single-point** calibration (one known point, zero-crossing assumption)
- **Two-point linear** calibration (recommended for production use)

For code-backed details, see `docs/CALIBRATION_CURRENT_STATE.md`.

### Recommended weekly procedure (same check weight, e.g. 50 lb)
1. Navigate to Calibration.
2. Ensure platform is empty, **CLEAR TARE** if needed, and wait for **STABLE**.
3. Press **ZERO** (baseline correction), then confirm reading is near 0.
4. Add or confirm a **0 lb** point when stable.
5. Apply known check weight (e.g. 50 lb), wait for **STABLE**, add point.
6. Verify reading with the same check weight and at least one secondary spot-check weight if available.
7. If many duplicate legacy points exist for the same weight, clean up stale duplicates in Calibration Hub.

### Calibration Behavior

**Point Persistence / Weekly Recalibration**:
- Existing calibration points are preserved across sessions/weeks.
- Adding a repeated weight appends a new history row; points are not auto-averaged.
- Use the Calibration Hub to remove stale duplicates when needed.

**Minimum Points Required**:
- **1 point**: system uses a single-point zero-crossing slope fallback.
- **2+ points**: system uses two-point linear conversion from endpoint points.

**Current limitation**:
- Weight calibration does not currently run multi-point regression or piecewise interpolation.
- Two-point linear behavior is deterministic for distinct low/high endpoint weights.

Notes:
- If vibration prevents stability, adjust filter/stability thresholds and retry.
- If excitation monitoring is enabled and excitation sags under load, fix excitation wiring/health before accepting calibration results.

## 7. PLC Output Mapping (Hand-in-Hand Calibration)
Use this to ensure the PLC display matches the true scale weight exactly. This process links the Pi output directly to the scale weight.

1. Scroll down to **PLC Output Mapping** on the Calibration Hub.
2. Confirm the **Active Port** (set in Settings) is correct.
3. For multiple weights across the range (e.g., 0, 50, 150, 300 lb):
   - Place the weight on the scale and wait for **STABLE**.
   - Use the **Live Slider** and **+/- buttons** to nudge the Pi's output.
   - Watch the PLC screen. When it matches the scale weight, click **ADD MATCH POINT**.
4. Save match points for commissioning records and repeatability checks.
   - Note: current runtime output command path remains proportional linear mapping from configured range.

**Freeze Mode**: While you are nudging the slider, the Pi "freezes" its normal weight-based logic so the signal stays steady for your meter or PLC.

## 8. Validation
- With calibrated system, apply several test weights and confirm:
  - web UI reads correct weight
  - PLC displayed value matches within tolerance (after PLC profile mapping if used)
- Verify fault-safe output:
  - with excitation monitoring enabled, simulate excitation fault and confirm analog output forces safe value and UI shows fault

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


