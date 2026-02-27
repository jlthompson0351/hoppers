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

## 3. Resolved Issues (Fixed in Recent Versions)

### 3.0 Scale Zeroing Not Working / Drifting (FIXED in v3.1)

**Symptom**: 
- Pressing ZERO button does not set display to 0.0 lb
- Weight readings wildly incorrect after zeroing
- Zero offset values appear correct in UI but don't affect weight
- Scale appears unusable, can't maintain zero baseline

**Root Cause (v3.0 and earlier)**:
Critical architectural bug where **pounds were being stored in millivolt fields**. When the system read `zero_offset_mv` from the database (which incorrectly contained lbs values like 100.0), it applied that value as a millivolt correction to the raw signal, causing massive errors (e.g., 100 lb applied as 100 mV instead of ~0.8 mV).

**Solution (Deployed in v3.1 - February 15, 2026)**:
Complete architectural refactoring to establish `zero_offset_mv` as the **canonical source of truth**:
- Manual ZERO now calculates signal drift correctly: `drift_mv = raw_mv - cal_zero_mv`
- Zero Tracking measures drift in lbs, then converts to mV for storage (preserves calibration slope)
- Fixed race conditions with atomic config updates
- `zero_offset_mv` is canonical; `zero_offset_lbs` is derived for display only

**Verification**:
- ✅ Manual ZERO forces display to 0.0 lb instantly
- ✅ Zero tracking converges on positive and negative drift
- ✅ Zero offset displays correct mV and derived lbs values
- ✅ System maintains zero across restarts

**If you're on v3.0 or earlier**: Upgrade to v3.1 immediately. Perform a manual ZERO after upgrade to reset baseline.

---

## 4. Common Issues
### 4.1 Excitation Low Warning / Fault
Symptoms:
- UI shows excitation low or fault; output forced safe on fault (only when excitation monitoring is enabled).

Checks:
- Confirm **Settings -> Quick Setup -> Enable Excitation Monitoring** is ON if you expect excitation-based safety.
- Measure SlimPak EXC+ to EXC− with DMM.
- Verify MegaIND AI wiring:
  - EXC+ into 0–10V AI
  - EXC− into AI reference/return
- Inspect SlimPak supply, terminals, and any series protection devices.
- If excitation is intentionally not wired yet, disable excitation monitoring so output is not clamped by excitation faults.

### 4.2 Unstable Reading / Can’t Accept Calibration Points
Symptoms:
- UI stays UNSTABLE; calibration points rejected.

Checks:
- Inspect vibration sources (conveyors, nearby motors, contactors).
- Verify shielding and separation from power wiring.
- Increase filter strength (lower cutoff / alpha) and adjust stability threshold/window.
- Verify mechanical settling time and rigid mounting.

### 4.2.1 Calibration Signal Stuck at 0.000000
Symptoms:
- Calibration page shows signal `0.000000` even though raw DAQ readings exist.

Cause:
- Usually a DAQ channel/configuration issue (wrong active channel, disabled channel, wiring/open circuit, or saturated signal).

Fix / Workaround:
- Verify the active DAQ channel is enabled and wired correctly, then confirm raw mV changes when load changes.
- If excitation is not wired in this installation phase, disable **Enable Excitation Monitoring** in Settings so excitation faults do not mask output behavior.

### 4.2.2 Calibration Points Look Correct but Weight Reading is Wrong
Symptoms:
- Calibration table points appear correct (signal increases with weight), but displayed weight does not match expected.

Status:
- **Known issue** in current build; to be debugged next (suspected filter/application-order issue in acquisition loop).

### 4.3 Ghost Signals on Unused Channels
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

### 4.4 Drift Warning (Per-cell ratio deviation)
Symptoms:
- Drift warning events; per-cell ratio deviates persistently.

Checks:
- Inspect load cell mounting and mechanical binding.
- Inspect load cell cable damage or moisture ingress.
- Verify excitation is stable and correctly wired to the configured MegaIND AI channel (when monitoring is enabled).
- Re-calibrate if needed after resolving mechanical issue.

### 4.5 PLC Display Doesn't Match UI Weight
Symptoms:
- UI weight correct, PLC displayed lbs incorrect.

Checks:
- Verify output mode matches wiring (0–10V vs 4–20mA).
- Verify PLC input channel configured for correct mode.
- Use PLC Profile wizard to build correction curve.
- Confirm output scaling range (Weight at 10V) and PLC scaling range.

### 4.6 PLC Output Signal Appears Unstable or Jumpy
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

### 4.7 Board Offline / I2C Error
Symptoms:
- Dashboard System Status shows "Boards Online: 0/2" or "1/2".
- Red "DAQ" or "IO" pills on Dashboard.
- "I2C scan failed" errors in logs.

Checks:
- Check **Settings → System** for I2C bus / stack-level configuration and confirm it matches the physical board stack.
- Verify physical stack connection and power to 24V supply.
- Run `sudo i2cdetect -y 1` in terminal to confirm OS-level visibility (if command not found: `sudo /usr/sbin/i2cdetect -y 1`).
- Check configured stack level matches the physical DIP/jumper settings on the boards (if applicable).

### 4.8 Settings Page Shows 500 Error
Symptoms:
- Browser shows `GET /settings 500 (INTERNAL SERVER ERROR)`

Cause:
- Older SQLite deployments may have an older config JSON without newer nested keys (`logging`, `zero_tracking`, etc.).

### 4.9 Zero Tracking Issues

**Symptom:** Scale drifts overnight, auto zero tracking not working

**Common Causes:**
1. **Zero tracking disabled** → Enable in Settings → Zero & Scale
2. **Drift too large for range** → Increase range (e.g., 10 lb for hopper scales) or press ZERO manually
3. **Hold time too long** → Default 6 sec is good, don't use 30+ minutes
4. **Scale never stable** → Check stability thresholds (stddev, slope)

**Symptom:** Scale reads negative after hopper dump, auto-zero not correcting

**Common Causes (v3.0+):**
1. **Negative hold time too long** → Default 1.0 sec should work; reduce to 0.5 or 0 for faster response
2. **Range too small** → If scale reads -8 lb but range is 5, it won't fire. Increase range to cover post-dump drift
3. **Extreme spikes** → Even the fast negative path blocks during extreme spikes (material still falling). Wait for the dump to complete.

**Quick Diagnostic:** Check the `zero_tracking_reason` in the API snapshot:
- `neg_holdoff` → Fast negative holdoff counting (will fire soon)
- `neg_spike` → Extreme motion blocking negative correction
- `holdoff` → Normal positive holdoff (not on fast path)
- `unstable` → Only affects positive weight; negative path ignores minor instability

**See:** `ZERO_TRACKING_OPERATOR_GUIDE.md` for complete troubleshooting

**Quick Fix:**
- Press ZERO button when empty and stable (instant correction)
- Enable auto tracking for future drift prevention
- For hopper scales: set range to 10 lb and negative hold to 1.0 sec

Fix:
- Update the application to a version where `AppRepository.get_latest_config()` deep-merges saved config onto defaults.
- Restart service: `sudo systemctl restart loadcell-transmitter`
- Confirm via logs: `sudo journalctl -u loadcell-transmitter -n 100 --no-pager`

### 4.10 HDMI Interface / Kiosk Issues
Symptoms:
- HDMI display is blank or shows desktop instead of app.
- "Lost connection" message on HDMI screen.
- Touch input not working.

Checks:
1. **Verify Kiosk Service**:
   - `sudo -u pi XDG_RUNTIME_DIR=/run/user/1000 systemctl --user status kiosk.service`
   - If inactive, use the **LAUNCH HDMI ON PI** button on the main Dashboard.
2. **Emergency Recovery**:
   - If the browser is stuck or showing old data, use the **FORCE RELAUNCH HDMI** button on the Dashboard. This kills all browser processes and starts a fresh kiosk session.
3. **Hardware Connection**:
   - Verify HDMI cable is secure at both ends.
   - Verify USB cable (for touch) is connected to the Pi.
4. **Manual Launch**:
   - Double-click the **Scale HDMI** icon on the Pi desktop.

## 5. Service Management (Pi)
### systemd
- Status: `sudo systemctl status loadcell-transmitter`
- Logs: `journalctl -u loadcell-transmitter -f`
- Restart: `sudo systemctl restart loadcell-transmitter`

## 6. Backups / SD Card Care
- Periodically copy `var/data/app.sqlite3` off the device.
- Prefer UPS or controlled shutdown to reduce corruption risk.
- Consider industrial storage media for harsh environments.


