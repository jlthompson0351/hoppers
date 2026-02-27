# TODAY: Unified Calibration Hub + Hand-in-Hand PLC Mapping + Conflict Guard

**Date**: January 6, 2026  
**Status**: Historical milestone summary (January 2026)

> Current-behavior note (Feb 2026):
> - Treat this file as historical change-log context.
> - For current calibration behavior in code, use:
>   - `docs/CALIBRATION_CURRENT_STATE.md`
>   - `docs/CalibrationProcedure.md`

---

## 🎉 VICTORY — Canonical mV Zeroing Bug Fix (February 15, 2026)

### The Problem
Zero offset was catastrophically broken: **Pounds were being stored in a Millivolt field**.

When the system read `zero_offset_mv` from the database (which contained lbs values like 100.0), it applied that value as a millivolt correction to the raw signal. This caused massive errors:
- **Example**: 100 lb stored as "mV" would shift the signal by 100 mV instead of ~0.8 mV
- **Result**: Zeroing operations failed, weight readings were wildly incorrect
- **Impact**: Scale appeared unusable, couldn't maintain zero baseline

### The Fix
Complete architectural refactoring to establish `zero_offset_mv` as the **CANONICAL source of truth**.

**New Architecture:**
```
Raw Signal (mV) 
  → Apply zero_offset_mv (signal domain) ← CANONICAL
  → Calibrate (mV → lbs)
  → Apply tare_offset_lbs (weight domain)
  → Final Weight
```

**Key Changes:**
1. **Manual ZERO**: Now calculates signal drift correctly (`drift_mv = raw_mv - cal_zero_mv`)
2. **Zero Tracking**: Measures drift in lbs, converts to mV for storage (preserves calibration slope)
3. **Storage**: `zero_offset_mv` canonical, `zero_offset_lbs` derived for display
4. **Persistence**: Fixed race conditions with atomic config updates

### The Result
Deployed to Pi `172.16.190.25` at 10:30 EST on February 15, 2026.

**User Confirmation:** "Working like a champ"

✅ Manual ZERO forces display to 0.0 lb instantly  
✅ Zero tracking converges on positive and negative drift  
✅ Zero offset displays correct mV and derived lbs values  
✅ System maintains zero across restarts  
✅ Calibration slope integrity preserved  

### Why This Matters
This wasn't just a bug fix — it was fixing a **fundamental architectural flaw** that made the zero system unusable. The refactoring:
- Establishes clear domain boundaries (signal mV vs. weight lbs)
- Preserves calibration integrity (zero never modifies slope/gain)
- Fixes persistence race conditions
- Makes the system mathematically correct

**Impact**: The scale system is now production-ready with reliable, predictable zeroing behavior.

---

## Project Status Summary (v3.1 - February 15, 2026)

### Critical Files Modified for Zeroing Fix

**Core System Files:**
- `src/services/acquisition.py` — Acquisition loop, zero offset application in signal domain
- `src/db/repo.py` — Zero offset persistence with atomic updates
- `src/app/routes.py` — Zero button API endpoint, zero tracking updates

**What Changed:**
1. **Signal Domain**: Zero offset now applied to raw mV signal before calibration
2. **Storage**: `zero_offset_mv` is canonical; `zero_offset_lbs` derived for display
3. **Manual ZERO**: Calculates drift correctly: `drift_mv = raw_mv - cal_zero_mv`
4. **Zero Tracking**: Measures lbs drift, converts to mV for storage
5. **Persistence**: Atomic config updates prevent race conditions

**Test Coverage:**
- `tests/test_api_zero.py` — API endpoint tests (local only, not deployed)
- `tests/test_zero_tracking.py` — Zero tracking behavior validation
- `tests/test_zeroing_calibration.py` — Calibration integration tests

**Deployment Target:** Pi at `172.16.190.25` — Version v3.1 confirmed operational

---

## Major Upgrades (January 6, 2026)

### 1. Unified Calibration Hub (The "One-Stop Shop")
**Problem**: PLC output settings were scattered across hidden pages and fighting with the scale calibration logic.
**Solution**: Merged everything into `calibration.html`.
- **Top**: Live Weight Monitor (0-600 lb visual bar).
- **Middle**: Scale mV Calibration.
- **Bottom**: PLC Output Mapping (The "Training Center").

### 2. Hand-in-Hand PLC Mapping (The "Nudge & Match")
**Problem**: Technicians had to do math to map weight to voltage (e.g. 150lb = 5V).
**Solution**: Interactive nudging.
- Tech puts weight on scale.
- Tech nudges Pi output via UI slider until PLC display matches true weight.
- Tech hits **ADD MATCH POINT**.
- **Math**: System uses Piece-wise Linear (PWL) interpolation to "bend" the signal for perfect accuracy across the entire range.

### 3. Clean Split Logic (Setup vs Training)
**Decision**: Keep setup in Settings and training in Calibration.
- **Settings -> Quick Setup**: Configure physical wiring (Channel 1-4) and Mode (0-10V/4-20mA).
- **Calibration Hub**: Just train the signal. No redundant dropdowns to accidentally change.
- **Status Bar**: Hub displays "Active Port: 0-10V on Channel 1 (Set in Settings)" so the tech knows exactly what they are working on.

### 4. Conflict Guard & Safety
- **Pin Watcher**: UI flashes **RED** if a technician tries to use a pin for PLC Output that is already being used by a Logic Rule.
- **Freeze Mode**: While nudging the slider, normal weight-based logic is suspended to provide a rock-solid steady signal for calibration.
- **Arm Override**: The nudge slider now works immediately on the Calibration page even if the global ARM toggle is off (Maintenance bypass).

### 5. Hardware Driver Extensions
- Added support for **Relays** and **Open-Drain PWM** outputs to the MegaIND driver, preparing for custom ladder logic and buttons.

### 6. HDMI Operator Interface & Kiosk Mode (Feb 2026)
- **Problem**: Operators needed a dedicated, touch-friendly screen on the hopper itself.
- **Solution**: Created a specialized `/hdmi` page with large weight and controls.
- **Auto-Recovery**: Added `LAUNCH` and `FORCE RELAUNCH` buttons to the main dashboard to remotely manage the Pi's display.
- **Persistence**: Configured `kiosk.service` to auto-start the UI at boot.

### 7. Calibration Persistence + Replace-by-Weight (Feb 2026)
- Calibration points are now preserved across weeks unless explicitly deleted.
- Capturing a point at an existing known weight replaces the previous point at that weight (latest capture wins).
- Historical note (Jan 2026): runtime mapping was documented as all-points piecewise interpolation/extrapolation.
- Single-point mode remains supported via zero-crossing slope fallback.

---

## Bug Fixes (December 19, 2025 - Late PM)

### Excitation Monitoring Fix (Dec 19, 2025 Late PM)

**Problem**: Excitation voltage showed **0.00V** on the Dashboard even when correctly wired to MegaIND analog input.

**Root Causes**:
1. **Code issue**: Excitation was only read when `ratiometric` mode was enabled. If ratiometric was OFF, excitation reading was skipped entirely.
2. **Config issue**: User had cycled through channels in Settings and left it on Channel 4, but excitation was wired to Channel 1.

**Fixes Applied**:

1. **`src/services/acquisition.py`**: Reads excitation voltage independent of calibration math and supports monitoring control from settings
   - Excitation monitoring can participate in fault detection while enabled
   - Added try/except with proper error handling for read failures
   - Status values: `OK`, `WARN`, `FAULT`, `NOT_READ`, `READ_ERROR`, `DISABLED`

2. **Config fix**: Changed `excitation.ai_channel` from 4 back to 1

**How Excitation Monitoring Works**:
- Excitation is read for display/fault handling when monitoring is enabled
- Calibration math uses raw mV signal capture
- Users can monitor excitation health independently of calibration math
- Users can disable excitation monitoring during commissioning when excitation AI is not wired yet

**Verification**: Dashboard now shows `Excitation: 10.15V OK`

---

## Bug Fixes (December 19, 2025 - AM/Early PM)

### Calibration Extrapolation Fix (CRITICAL)

**Problem**: When the load cell signal exceeded the highest calibration point, the weight display would **clamp** at the highest calibrated weight instead of extrapolating.

**Example**: User calibrated 0-75 lb range, but stepping on scale (signal ~10.3 mV) only showed 75 lb instead of the actual ~184 lb.

**Root Cause (historical)**: The piecewise-linear interpolation function (`src/core/pwl.py`) was documented as clamping endpoints instead of extrapolating.

**Fix Applied (historical)** (`src/core/pwl.py`):
- Added `extrapolate` parameter (default: `True`)
- When signal is **below** the lowest calibration point: extrapolates using the slope from the first two points
- When signal is **above** the highest calibration point: extrapolates using the slope from the last two points
- Clamping behavior still available via `extrapolate=False` if needed

**Impact**: Both calibration curves and PLC profile curves now extrapolate beyond their defined ranges, which is the expected industrial behavior.

### Multiple Load Cell Signal Handling (Confirmed Working)

**Question**: How does the system handle multiple load cells?

**Answer**: Signals are **summed together** (industry standard for hopper/vessel scales):
- Each load cell channel is read individually (raw mV)
- All load cell signals are added to produce `total_signal`
- Calibration curve converts `total_signal` → weight in lbs

This is correct for multi-point suspension scales where each load cell carries a fraction of the total weight.

### Calibration Signal Mode (Current)

Calibration capture and runtime mapping use raw mV.

**Excitation monitoring is independent of calibration math**:
- Excitation voltage monitoring is independent of calibration math
- Excitation WARN/FAULT protects output safety when excitation monitoring is enabled

**Settings location**:
- **Excitation channel**: Settings > Quick Setup > Excitation Input Channel (1-4)
- **Enable/disable**: Settings > Quick Setup > Enable Excitation Monitoring

### Weight-Side Bulletproofing (Dec 19, 2025)

**Goal**: Make sure nothing in Settings is “UI-only” and that the Pi is truly running real hardware.

✅ **Verified real hardware**:
- `i2cdetect` shows **0x31** (24b8vin) and **0x52** (MegaIND, stack 2)
- `/api/snapshot` reports **hw_mode: real** and **Boards Online: 2/2**

✅ **Settings are now real (no simulation leftovers):**
- **DAQ**: `average_samples` is applied, and per-channel `gain_code` is applied automatically when config changes.
- **Timing**: `loop_rate_hz` controls the actual acquisition loop timing (best-effort).
- **Output safety**: when **outputs are NOT armed**, the system forces the configured **safe output** (no more “still writing” when disarmed).
- **Output shaping**: deadband + ramp settings are active.
- **Logging/DB**: `logging.interval_s`, `logging.event_only`, and `logging.retention_days` are enforced (trend tables get periodic cleanup).

**Note on `i2cdetect`**: on some images `i2cdetect` is installed at `/usr/sbin/i2cdetect`. If `i2cdetect` says “command not found”, use:\n`sudo /usr/sbin/i2cdetect -y 1`

---

## For Tomorrow: Settings Tweaks Needed

Before testing with the conveyor/hopper:

1. **Go to Settings > DAQ Channels** - Enable Channel 1 (first row)
2. **Go to Settings > Signal Tuning** - Set these values:
   - Stability Window: **25** samples
   - Kalman Process Noise: **10** (for dynamic filling)
   - Kalman Measurement Noise: **25**
3. **Go to Settings > System** - Verify Hardware Mode is **Real**
4. **Save Settings**

---

## Important: How Stability Works

| Component | Affected by UNSTABLE? |
|-----------|----------------------|
| Weight reading | ❌ NO - always updates |
| Weight display | ❌ NO - always updates |
| PLC output | ❌ NO - always sends |
| ZERO button | ✅ YES - blocked when unstable |
| TARE button | ✅ YES - blocked when unstable |
| Add calibration point | ✅ YES - blocked when unstable |

**For conveyor/hopper filling:** The scale WILL show UNSTABLE while parts are dropping in - this is NORMAL and doesn't affect weight reading or PLC output!

---

## Bug Fixes & Improvements (Dec 18, 2025 Late PM)

### Stability Detector Fix (CRITICAL)
**Problem**: Scale was flickering between STABLE/UNSTABLE constantly.

**Root Cause**: The `StabilityDetector` was being **re-instantiated** on every config refresh (every 2-30 seconds), which reset its internal sample buffer. The detector could never accumulate enough samples to determine stability.

**Fix Applied** (`src/services/acquisition.py`):
- Now only updates `stddev_threshold` and `slope_threshold` directly on the existing detector
- Only re-creates the detector if `window` size changes (rare)
- Buffer is preserved across config reloads

### Weight Display Precision Setting (NEW)
Added configurable decimal places for weight display:

| Setting | Display |
|---------|---------|
| 0 | 75 lb (whole pounds) |
| 1 | 75.2 lb (one decimal - default) |
| 2 | 75.24 lb (two decimals) |

**Location**: Settings > Signal Tuning > Weight Display

### Emoji Removal
All emoji icons removed from settings.html for encoding compatibility when deploying via SCP/PSCP. Tabs now show plain text:
- Quick Setup, Signal Tuning, Zero & Scale, etc.

### Kalman Filter Tuning
Recommended settings for faster response:
- `kalman_process_noise`: 5.0 (was 1.0)
- `kalman_measurement_noise`: 25 (was 50)

### Tare Offset Fix
Cleared accidental tare offset that was causing 22 lb error in weight readings.

---

## UI REDESIGN COMPLETED (Dec 18, 2025 PM)

### Pages Redesigned

| Page | Status | Key Features |
|------|--------|--------------|
| **Dashboard** | ✅ Complete | Large weight display, Zero/Tare buttons, PLC output panel, status indicators |
| **Calibration** | ✅ Complete | Live signal display, add/delete points, clear all |
| **PLC Output** | ✅ Complete | ARM toggle, test output toggle, output config, calibration, correction curve |
| **Settings** | ✅ Complete | Tabbed technician settings, helper text, safe defaults, DAQ channel table |

### New UI Routes Added

- `GET /settings` - Render the tabbed technician Settings page
- `POST /settings` - Save Settings page form to SQLite config

### Config Backwards-Compatibility Fix (Important)

- Older SQLite configs may be missing new nested keys (like `logging`, `zero_tracking`, etc.)
- `AppRepository.get_latest_config()` now **deep-merges the saved config onto `default_config()`**, so new pages don’t 500 and new settings appear with safe defaults.

### New API Endpoints Added

- `POST /api/zero` - Zero the scale
- `POST /api/tare` - Tare the scale
- `POST /api/tare/clear` - Clear tare offset
- `POST /api/calibration/add` - Add calibration point
- `POST /api/calibration/delete/<id>` - Delete calibration point
- `POST /api/calibration/clear` - Clear all points
- `POST /api/output/arm` - Arm/disarm outputs
- `POST /api/output/config` - Save output configuration
- `POST /api/output/test` - Start/stop test output (toggle)
- `POST /api/output/calibrate` - Capture calibration point
- `POST /api/output/calibrate/reset` - Reset to factory
- `POST /api/plc-profile/delete/<id>` - Delete PLC profile point

### Test Output Feature

- **Toggle behavior**: Click START → stays on until STOP clicked
- UI turns red with "TEST OUTPUT ACTIVE" indicator
- Test value input disabled while active
- Overrides weight-based output completely

### Files Modified

- `src/app/routes.py` - New API endpoints
- `src/app/templates/dashboard.html` - Complete redesign
- `src/app/templates/calibration.html` - Complete redesign
- `src/app/templates/plc_profile.html` - Complete redesign
- `src/app/templates/settings.html` - New tabbed Settings page
- `src/app/templates/base.html` - Nav updated (Settings link, Config hidden unless maintenance enabled)
- `src/services/acquisition.py` - Test mode support + calibration mapping/runtime updates + config refresh improvements + excitation monitoring runtime support
- `src/hw/sequent_megaind_stub.py` - Simulation improvements
- `src/db/repo.py` - Expanded defaults + deep-merge for older configs
- `src/core/pwl.py` - **Dec 19 historical note**: extrapolation support was documented for calibration curves.

---

## Calibration / Signal Work (Dec 18, 2025 late PM)

### What was changed

- **Raw mV calibration path**: Calibration capture uses raw mV signal values.
- **Calibration UI signal display**: Calibration page shows raw mV signal used for point capture.
- **Output channels default to 1**: Default MegaIND analog I/O channels are treated as 1-indexed.
- **Config refresh interval honored**: Acquisition loop refreshes config using `timing.config_refresh_s` (instead of hardcoded 2s).
- **Filter parameter updates without state reset**: On config refresh, filter parameters are updated while trying to preserve filter state.

### Known issue (RESOLVED)

- **Filtered weight does not match calibrated raw weight** - **FIXED**: Was caused by an accidental tare offset being applied. Cleared via `/api/tare/clear`.
- **Stability flickering** - **FIXED**: Stability detector was being reset on config refresh. Fixed by preserving buffer across reloads.

## 🎯 LIVE DASHBOARD

# 👉 http://172.16.190.25:8080

Open in any browser to view live load cell readings.

---

## ✅ System Deployed (December 18, 2025)

| Component | Status | Details |
|-----------|--------|---------|
| **Dashboard** | ✅ LIVE | http://172.16.190.25:8080 |
| **Flask Service** | ✅ Running | Auto-starts on boot |
| **24b8vin DAQ** | ✅ Online | I2C 0x31, Firmware 1.4, 8 channels |
| **MegaIND I/O** | ✅ Online | I2C 0x52 (Stack 2), Firmware 4.8 |
| **Hardware Mode** | ✅ REAL | Live load cell readings |

### Quick Commands (SSH to Pi)
```bash
sudo systemctl status loadcell-transmitter   # Check status
sudo journalctl -u loadcell-transmitter -f   # View logs
sudo systemctl restart loadcell-transmitter  # Restart
```

---

## What's Been Prepared

### 📚 Documentation Created

1. **`HardwareTestReadiness_TODAY.md`** — Complete runbook (2.5-3.5 hour timeline)
   - Phase 1: Bootstrap (SSH → Running Dashboard)
   - Phase 2: Hardware Smoke Tests (I2C scan, board detection)
   - Phase 3: Calibration + Real Testing
   - Phase 4: Analog Output Verification (0-10V/4-20mA testing)
   - Phase 5: Final Checklist
   - Full troubleshooting guide

2. **`QUICK_START_HARDWARE_TEST.md`** — One-page quick reference
   - Copy-paste commands
   - Quick troubleshooting
   - Essential checklist

### 🛠️ Test Scripts Created

Located in `scripts/`:

1. **`setup_test_scripts.sh`** — Make all scripts executable (run once on Pi)
2. **`test_hardware_basic.sh`** — Automated I2C scan + board detection
3. **`test_24b8vin_channels.sh`** — Read all 8 DAQ channels
4. **`test_megaind_output.sh`** — Interactive voltage sweep test (with multimeter)
5. **`verify_calibration.py`** — Interactive calibration verification helper
6. **`analog_output_test_log.py`** — Automated output test with pass/fail report

### ✅ Existing Dashboard Features (Already Implemented)

- **Board Discovery**: Dashboard shows "Boards Online: X/Y" with DAQ and IO pills
- **I2C Health Check**: Automatic detection at startup
- **Calibration UI**: Multi-point piecewise-linear calibration
- **Stability Detection**: STABLE/UNSTABLE indicator
- **Analog Output**: 0-10V and 4-20mA modes
- **Fault-Safe Behavior**: Safe output on excitation fault when excitation monitoring is enabled
- **Systemd Service**: Auto-start on boot with restart on failure

---

## Justin's Pre-Test Checklist

### Hardware Assembly
- [ ] Raspberry Pi 4B with fresh Raspberry Pi OS installed
- [ ] SSH enabled (provide IP address to team)
- [ ] Hardware stack order verified: **Pi → 24b8vin (bottom) → MegaIND (top)**
- [ ] 40-pin GPIO connectors fully seated on all boards
- [ ] 24V power connected to MegaIND and Super Watchdog
- [ ] Pi powered from Super Watchdog (NOT USB-C)

### Wiring
- [ ] Load cells connected to 24b8vin channels 1-4 (SIG+/SIG-)
- [ ] SlimPak excitation wired to load cells (EXC+/EXC-)
- [ ] Excitation monitoring: EXC+ → MegaIND AI (0-10V input)
- [ ] PLC analog output wiring ready (AO+ / AO-)

### Test Equipment
- [ ] Multimeter (for voltage verification)
- [ ] Known calibration weights available:
  - 0 lb (empty scale)
  - 25 lb weight
  - 50 lb weight (or similar)
  - 100 lb weight (or similar)
  - 150 lb or max capacity weight

---

## Testing Day Workflow

### Step 1: Initial Access (5 min)
```powershell
# From Windows machine
ssh pi@<IP>
# Change default password immediately
```

### Step 2: Bootstrap (30-45 min)
Follow: `HardwareTestReadiness_TODAY.md` Phase 1
- OS updates
- I2C enable + reboot
- Install packages
- Copy repo via scp
- Install Python deps
- Configure systemd service (verify `LCS_HW_MODE=real`; repo service file defaults to real)
- Start service
- Verify dashboard accessible

### Step 3: Hardware Smoke Tests (15-30 min)
Follow: `HardwareTestReadiness_TODAY.md` Phase 2

**Critical STOP POINT**: Run `sudo i2cdetect -y 1` (or `sudo /usr/sbin/i2cdetect -y 1` if command not found) and send screenshot
- Expected: **0x31** (24b8vin DAQ) and **0x52** (MegaIND, stack 2). **0x30** appears only if Super Watchdog is installed.

Run automated tests:
```bash
cd /opt/loadcell-transmitter
bash scripts/setup_test_scripts.sh
./scripts/test_hardware_basic.sh
./scripts/test_24b8vin_channels.sh
./scripts/test_megaind_output.sh
```

Dashboard should show: **"Boards Online: 2/2"** with green DAQ and IO pills

### Step 4: Calibration (45-60 min)
Follow: `HardwareTestReadiness_TODAY.md` Phase 3
- Configure channels (enable 1-4)
- Verify excitation (~10V)
- Tune stability settings
- Zero capture (empty scale)
- Multi-point calibration (25, 50, 100, 150 lb)
- Verify readings
- Test reboot persistence

Helper script:
```bash
python3 scripts/verify_calibration.py
```

### Step 5: Analog Output Test (30-45 min)
Follow: `HardwareTestReadiness_TODAY.md` Phase 4
- Configure output mode (0-10V)
- Train PLC profile points in Calibration Hub (e.g., 0 lb = 0V, 150 lb = 10V)
- Test multiple weight points across range
- Verify with multimeter (within ±0.2V of profile curve)
- Test fault-safe output

Automated test:
```bash
python3 scripts/analog_output_test_log.py
```

### Step 6: Final Verification (15-30 min)
Follow: `HardwareTestReadiness_TODAY.md` Phase 5
- Run through final checklist
- Backup database
- Document results

---

## Success Criteria

### ✅ Dashboard Must Show:
- **Boards Online**: 2/2 (green DAQ and IO pills)
- **Excitation**: ~10.0V (green status) when excitation monitoring is enabled
- **Stability**: Toggles between STABLE/UNSTABLE correctly
- **Weight**: Matches known test weights within ±2 lb
- **Output**: Tracks weight correctly (within ±0.2V or ±0.5mA)
- **Fault Behavior**: Safe output (0V or 4mA) when excitation fails and excitation monitoring is enabled

### ✅ System Must:
- Start automatically on boot
- Survive reboot without losing calibration
- Run for 10+ minutes without crashes
- Log events correctly
- Respond to live weight changes

---

## Quick Command Reference

```bash
# Service management
sudo systemctl status loadcell-transmitter
sudo systemctl restart loadcell-transmitter
sudo journalctl -u loadcell-transmitter -f

# Hardware diagnostics
sudo i2cdetect -y 1  # if command not found: sudo /usr/sbin/i2cdetect -y 1
./scripts/test_hardware_basic.sh
./scripts/test_24b8vin_channels.sh
./scripts/test_megaind_output.sh

# Calibration verification
python3 scripts/verify_calibration.py
python3 scripts/analog_output_test_log.py

# Database backup
cp /var/lib/loadcell-transmitter/app.sqlite3 ~/backup-$(date +%Y%m%d-%H%M%S).sqlite3
```

---

## STOP POINTS — Send These Outputs

1. **After Bootstrap**: Dashboard screenshot showing "Boards Online: 2/2"
2. **After I2C Scan**: Output of `sudo i2cdetect -y 1` (or `sudo /usr/sbin/i2cdetect -y 1`)
3. **After Channel Test**: Output of `./scripts/test_24b8vin_channels.sh`
4. **After Voltage Test**: Multimeter readings from `./scripts/test_megaind_output.sh`
5. **After Calibration**: Screenshot of calibration points table
6. **After Output Test**: Output of `python3 scripts/analog_output_test_log.py`

---

## Troubleshooting Quick Hits

| Issue | Quick Fix |
|-------|-----------|
| "Boards Online: 0/2" or "I/O OFFLINE" | Check `sudo i2cdetect -y 1` (or `/usr/sbin/i2cdetect`), verify wiring, restart service. System auto-retries every 5s. |
| Can't add calibration point | Wait for STABLE, increase stability threshold |
| Output voltage wrong | Verify PLC profile points trained in Calibration Hub, check weight calibration loaded |
| Excitation low | Check SlimPak output, verify wiring |
| **Excitation shows 0.00V** | 1) Check Settings > Quick Setup > Excitation Input Channel matches your wiring (1-4). 2) Test with `megaind 0 uinrd 1` to verify hardware. 3) If excitation is not wired yet, turn OFF **Enable Excitation Monitoring**. |
| Dashboard not accessible | Check service status, verify port 8080 binding |
| Weight stuck at max calibrated value | Historical note from Dec 19 references `src/core/pwl.py` path. |
| Weight off with 1 cal point | Add more points (recommended 3-10); with 1 point system uses a simple single-point slope fallback |
| Added load cell, weight doubled | Expected - signals are summed. Clear calibration and recalibrate with new configuration |

---

## Timeline Estimate

| Phase | Time |
|-------|------|
| Bootstrap | 30-45 min |
| Hardware Tests | 15-30 min |
| Calibration | 45-60 min |
| Output Verification | 30-45 min |
| Final Checks | 15-30 min |
| **Total** | **~2.5-3.5 hours** |

Add 30-60 min buffer for troubleshooting/unexpected issues.

---

## Files to Reference

- **Full Runbook**: `docs/HardwareTestReadiness_TODAY.md`
- **Quick Start**: `docs/QUICK_START_HARDWARE_TEST.md`
- **Test Scripts**: `scripts/test_*.sh`, `scripts/*_test_log.py`
- **Existing Docs**: 
  - `docs/WiringAndCommissioning.md`
  - `docs/CalibrationProcedure.md`
  - `docs/TestPlan.md`

---

## Contact / Support

- All scripts are copy-paste ready
- Every command includes working directory context
- Stop points prevent cascading failures
- Troubleshooting section covers common issues

---

**You're ready for real hardware testing TODAY!**

Follow the runbook, send outputs at STOP POINTS, and document results.

**Good luck!**
