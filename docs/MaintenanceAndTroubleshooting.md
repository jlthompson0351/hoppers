# Maintenance and Troubleshooting

> **🚀 For systematic hardware testing and diagnostics, see:**
> - **`docs/HardwareTestReadiness_TODAY.md`** — Complete test runbook with troubleshooting
> - **`scripts/test_hardware_basic.sh`** — Automated hardware diagnostics
> - **`scripts/test_24b8vin_channels.sh`** — DAQ channel diagnostics
> - **`scripts/test_megaind_output.sh`** — Analog output diagnostics

---

## 1. Routine Maintenance
### 1.1 Weekly
- Review Dashboard for:
  - excitation voltage trends (sag or intermittent drops)
  - drift warnings
  - repeated instability indications
- Export events/logs for archiving.

### 1.2 Monthly
- Verify calibration against one or two known check weights.
- Inspect load cell cables, glands, shielding terminations.
- Verify PLC analog reading matches expected at several points.

### 1.3 After Mechanical Changes
- Re-run calibration and verify drift ratios.

## 2. Log Export
Use the script:
- `python scripts/export_logs.py --db var/data/app.sqlite3 --out var/export/events.json`

Or from the UI:
- Download `events.json` from Logs page.

## 3. Common Issues
### 3.1 Excitation Low Warning / Fault
Symptoms:
- UI shows excitation low or fault; output forced safe on fault.

Checks:
- Measure SlimPak EXC+ to EXC− with DMM.
- Verify MegaIND AI wiring:
  - EXC+ into 0–10V AI
  - EXC− into AI reference/return
- Inspect SlimPak supply, terminals, and any series protection devices.

### 3.2 Unstable Reading / Can’t Accept Calibration Points
Symptoms:
- UI stays UNSTABLE; calibration points rejected.

Checks:
- Inspect vibration sources (conveyors, nearby motors, contactors).
- Verify shielding and separation from power wiring.
- Increase filter strength (lower cutoff / alpha) and adjust stability threshold/window.
- Verify mechanical settling time and rigid mounting.

### 3.2.1 Calibration Signal Stuck at 0.000000
Symptoms:
- Calibration page shows signal `0.000000` even though raw DAQ readings exist.

Cause:
- Ratiometric mode enabled while excitation reads ~0V (missing wiring / wrong MegaIND AI channel), causing signal to collapse to 0.

Fix / Workaround:
- Wire excitation to a MegaIND 0–10V input and configure the correct `excitation.ai_channel`, **or**
- Use the build where the acquisition loop **falls back to raw mV** when excitation is ~0V (so calibration can proceed).

### 3.2.2 Calibration Points Look Correct but Weight Reading is Wrong
Symptoms:
- Calibration table points appear correct (signal increases with weight), but displayed weight does not match expected.

Status:
- **Known issue** in current build; to be debugged next (suspected filter/application-order issue in acquisition loop).

### 3.3 Ghost Signals on Unused Channels
Symptoms:
- Unused DAQ channels show non-zero mV readings (typically 10-50 mV)
- Weight reading incorrect when unused channels are enabled
- Calibration page shows unexpected signal values

Cause:
- High-impedance differential ADC inputs pick up electrical noise when nothing is connected (floating inputs)
- This is **normal behavior** for 24-bit ADCs and not a hardware fault

Fix:
1. Navigate to **Settings → DAQ Channels**
2. **Disable all channels without load cells** (uncheck the "Enabled" box)
3. Verify only channels with actual load cells are enabled
4. Re-calibrate the scale with correct channel configuration
5. Ghost signals from disabled channels will no longer affect weight calculations

**Note:** If a specific channel shows unusually high readings (>100 mV) even when disabled doesn't affect calculations, it may indicate a hardware issue with that ADC channel. Use other channels instead.

### 3.4 Drift Warning (Per-cell ratio deviation)
Symptoms:
- Drift warning events; per-cell ratio deviates persistently.

Checks:
- Inspect load cell mounting and mechanical binding.
- Inspect load cell cable damage or moisture ingress.
- Verify excitation is stable; enable ratiometric mode.
- Re-calibrate if needed after resolving mechanical issue.

### 3.5 PLC Display Doesn't Match UI Weight
Symptoms:
- UI weight correct, PLC displayed lbs incorrect.

Checks:
- Verify output mode matches wiring (0–10V vs 4–20mA).
- Verify PLC input channel configured for correct mode.
- Use PLC Profile wizard to build correction curve.
- Confirm output clamping limits and PLC scaling range.

### 3.6 PLC Output Signal Appears Unstable or Jumpy
Symptoms:
- PLC display shows weight bouncing or flickering
- Output voltage measured on multimeter varies rapidly

Checks:
1. **Verify deadband is enabled** (Settings → Output Control)
   - Recommended: 0.5-1.0 lb deadband
   - This prevents output changes for small weight fluctuations
2. **Check signal stability with multimeter**
   - Measure analog output terminals during stable weight
   - Should see <0.001V variation
3. **Review Kalman filter settings** (Settings → Signal Tuning)
   - Increase Measurement Noise (R) if too sensitive
   - Typical: Q=1.0, R=50 for static weighing
4. **Disable unused DAQ channels**
   - Ghost signals can cause erratic totals
5. **Verify only load cell channels are enabled**
   - Check Settings → DAQ Channels configuration

**Bench Test Recommendation:**
Before field deployment, connect multimeter to analog output and verify rock-solid voltage under stable load. Expected: voltage locks to exact value with zero variation.

### 3.5 Board Offline / I2C Error
Symptoms:
- Dashboard System Status shows "Boards Online: 0/2" or "1/2".
- Red "DAQ" or "IO" pills on Dashboard.
- "I2C scan failed" errors in logs.

Checks:
- Check **Settings → System** for I2C bus / stack-level configuration and confirm it matches the physical board stack.
- Verify physical stack connection and power to 24V supply.
- Run `sudo i2cdetect -y 1` in terminal to confirm OS-level visibility (if command not found: `sudo /usr/sbin/i2cdetect -y 1`).
- Check configured stack level matches the physical DIP/jumper settings on the boards (if applicable).

### 3.6 Settings Page Shows 500 Error
Symptoms:
- Browser shows `GET /settings 500 (INTERNAL SERVER ERROR)`

Cause:
- Older SQLite deployments may have an older config JSON without newer nested keys (`logging`, `zero_tracking`, etc.).

Fix:
- Update the application to a version where `AppRepository.get_latest_config()` deep-merges saved config onto defaults.
- Restart service: `sudo systemctl restart loadcell-transmitter`
- Confirm via logs: `sudo journalctl -u loadcell-transmitter -n 100 --no-pager`

## 4. Service Management (Pi)
### systemd
- Status: `sudo systemctl status loadcell-transmitter`
- Logs: `journalctl -u loadcell-transmitter -f`
- Restart: `sudo systemctl restart loadcell-transmitter`

## 5. Backups / SD Card Care
- Periodically copy `var/data/app.sqlite3` off the device.
- Prefer UPS or controlled shutdown to reduce corruption risk.
- Consider industrial storage media for harsh environments.


