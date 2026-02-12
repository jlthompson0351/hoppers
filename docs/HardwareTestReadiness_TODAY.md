# Hardware Test Readiness Runbook — TODAY
**Target**: Fresh Raspberry Pi OS → Calibrated scale with verified analog output  
**Hardware**: Pi → MegaIND (bottom) → 24b8vin (top)  
**Comms**: I2C bus 1

---

## 🎯 SYSTEM IS DEPLOYED AND LIVE (December 18, 2025)

# 👉 Dashboard: http://172.16.190.25:8080

The Flask application is installed, configured, and running. Open the dashboard URL above in any browser to view live load cell readings.

---

## ✅ Deployed System Status

| Component | Status | Details |
|-----------|--------|---------|
| **Dashboard** | ✅ LIVE | http://172.16.190.25:8080 |
| **Flask Service** | ✅ Running | Auto-starts on boot |
| **24b8vin** (8x ADC) | ✅ Online | I2C 0x31, Firmware 1.4 |
| **MegaIND** (Industrial I/O) | ✅ Online | I2C 0x50, Firmware 4.08 |
| **Hardware Mode** | ✅ REAL | Live hardware readings |

| Pi Property | Value |
|-------------|-------|
| **Hostname** | `Hoppers` |
| **IP Address** | `172.16.190.25` |
| **Dashboard URL** | http://172.16.190.25:8080 |
| **SSH User** | `pi` |
| **OS** | Debian GNU/Linux, Kernel 6.12.47 (aarch64) |

**Connection Guide:** See `CONNECTION_GUIDE.md` for SSH/plink/dashboard access from Windows.

---

## 🔧 Service Management Commands

```bash
# Check if service is running
sudo systemctl status loadcell-transmitter

# View live logs
sudo journalctl -u loadcell-transmitter -f

# Restart service
sudo systemctl restart loadcell-transmitter

# Stop service
sudo systemctl stop loadcell-transmitter
```

---

## Phase 1: Bootstrap (Fresh Pi OS → Running Dashboard)

### 1.1 SSH Access & Initial Setup
**After Justin provides SSH IP:**

```bash
ssh pi@<IP_ADDRESS>
# Default password is usually "raspberry" — change it immediately
passwd
```

### 1.2 OS Updates & I2C Enable
**Directory**: `/home/pi`

```bash
sudo apt update && sudo apt upgrade -y
```

**Enable I2C interface:**

```bash
sudo raspi-config
```

- Navigate to: `3 Interface Options` → `I5 I2C` → `Yes` → `Finish`
- **Reboot required**: `sudo reboot`

**After reboot, SSH back in and verify I2C is enabled:**

```bash
ls /dev/i2c-*
# Expected output: /dev/i2c-1
```

### 1.3 Install System Packages
**Directory**: `/home/pi`

```bash
sudo apt install -y \
  i2c-tools \
  python3-dev \
  python3-pip \
  python3-venv \
  python3-smbus \
  git \
  vim
```

### 1.4 Clone Repository & Install Dependencies
**Directory**: `/home/pi`

```bash
# Create application directory
sudo mkdir -p /opt/loadcell-transmitter
sudo chown pi:pi /opt/loadcell-transmitter

# Clone repo (use your actual repo URL or rsync from dev machine)
# Option A: If you have a git repo
# git clone <YOUR_REPO_URL> /opt/loadcell-transmitter

# Option B: Copy from your dev machine via scp
# From your Windows machine, run:
# scp -r C:\Users\jthompson\Desktop\hoppers pi@<IP>:/tmp/hoppers
# Then on Pi:
# cp -r /tmp/hoppers/* /opt/loadcell-transmitter/
```

**For today's test, use Option B (scp from your dev machine):**

From PowerShell on your Windows machine:
```powershell
scp -r C:\Users\jthompson\Desktop\hoppers pi@<IP_ADDRESS>:/tmp/hoppers
```

Then on Pi:
```bash
cp -r /tmp/hoppers/* /opt/loadcell-transmitter/
```

**Directory**: `/opt/loadcell-transmitter`

```bash
cd /opt/loadcell-transmitter
```

**Install Python dependencies:**

```bash
./scripts/install_pi.sh
```

### 1.5 Create Data Directory
**Directory**: `/opt/loadcell-transmitter`

```bash
sudo mkdir -p /var/lib/loadcell-transmitter
sudo chown pi:pi /var/lib/loadcell-transmitter
```

### 1.6 Configure Systemd Service
**Directory**: `/opt/loadcell-transmitter`

```bash
# Install the systemd service file
sudo cp systemd/loadcell-transmitter.service /etc/systemd/system/

# Edit the service file (only if you need to change settings)
sudo nano /etc/systemd/system/loadcell-transmitter.service
```

**Note:** The system always uses real hardware - there is no simulated mode. If hardware is unavailable, the UI shows "I/O OFFLINE" and retries automatically.

**Enable and start the service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable loadcell-transmitter
sudo systemctl start loadcell-transmitter
```

**Verify service is running:**

```bash
sudo systemctl status loadcell-transmitter
```

Expected: `active (running)` in green

**View logs:**

```bash
sudo journalctl -u loadcell-transmitter -f
```

Press `Ctrl+C` to exit log viewer.

### 1.7 Access Dashboard
**From your Windows machine:**

Open browser and navigate to: `http://<PI_IP_ADDRESS>:8080`

You should see the Load Cell Scale Transmitter dashboard.

### 1.8 Verify Dashboard Survives Reboot

```bash
sudo reboot
```

**After reboot (wait ~60 seconds), SSH back in and check:**

```bash
sudo systemctl status loadcell-transmitter
```

Expected: `active (running)`

**Verify dashboard is accessible in browser again.**

---

## Phase 2: Hardware Smoke Tests

### 2.1 I2C Bus Scan — **STOP POINT**
**Directory**: `/home/pi`

```bash
sudo i2cdetect -y 1
# If you get "command not found": sudo /usr/sbin/i2cdetect -y 1
```

**Expected output example:**
```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
30: 30 31 -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: 50 -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
70: -- -- -- -- -- -- -- --
```

**Expected devices (VERIFIED December 18, 2025):**
- `0x31`: **24b8vin** DAQ (stack 0) — 8x 24-bit analog inputs
- `0x50`: **MegaIND** (stack 0) — Industrial I/O (analog outputs, opto inputs, etc.)
- `0x30`: Super Watchdog (if present — not currently installed)

**⚠️ STOP: Send screenshot of i2cdetect output before proceeding.**

**If devices are missing:**
1. Check physical HAT seating (40-pin GPIO connection)
2. Check power connections (24V to boards, 5V to Pi from Watchdog)
3. Verify stack order: Pi → MegaIND → 24b8vin
4. Check for loose jumper wires or damaged connectors

### 2.2 Dashboard Board Discovery
**Navigate to**: **Settings** (`/settings`) (or **Config (Raw)** if maintenance is enabled)

**Look for "Boards Online" status:**
- Expected: `Boards Online: 2/2` (green indicators)
- DAQ (24b8vin): 0x31 — Online
- MegaIND: 0x50 — Online

**If "Boards Online: 0/2" or "I/O OFFLINE":**
1. Check systemd logs: `sudo journalctl -u loadcell-transmitter -n 50`
2. Look for I2C errors or "Failed to initialize" messages
3. Verify I2C wiring and run `sudo i2cdetect -y 1`
4. System auto-retries every 5 seconds when hardware is offline

### 2.3 24b8vin ADC Read Test
**Directory**: `/opt/loadcell-transmitter/.vendor/24b8vin-rpi`

**Build CLI tool:**

```bash
cd /opt/loadcell-transmitter/.vendor/24b8vin-rpi
make
```

**Test reading channel 1:**

```bash
./24b8vin -stack 0 rd 1
```

**Expected**: Output shows a voltage reading in mV (may be near 0 if no load cell connected yet)

Example output:
```
Channel 1: 0.523 mV
```

**Test all 4 channels:**

```bash
for ch in 1 2 3 4; do echo "Channel $ch:"; ./24b8vin -stack 0 rd $ch; done
```

**⚠️ STOP: Send output of all channel reads.**

### 2.4 MegaIND Output Test
**Directory**: `/opt/loadcell-transmitter/.vendor/megaind-rpi`

**Build CLI tool:**

```bash
cd /opt/loadcell-transmitter/.vendor/megaind-rpi
make
```

**Test 0-10V output (set to 5V):**

```bash
./megaind -stack 0 uout 5
```

**Measure with multimeter between MegaIND AO+ and AO-**

Expected: ~5V

**Test full range:**

```bash
# 0V
./megaind -stack 0 uout 0
# Measure: ~0V

# 10V
./megaind -stack 0 uout 10
# Measure: ~10V

# Back to 0V for safety
./megaind -stack 0 uout 0
```

**⚠️ STOP: Confirm voltage measurements match commanded values within ±0.1V.**

### 2.5 Watchdog Verification (if present)
**Directory**: `/opt/loadcell-transmitter/.vendor`

**Clone watchdog repo if not present:**

```bash
cd /opt/loadcell-transmitter/.vendor
git clone https://github.com/SequentMicrosystems/Super-Watchdog-HAT-rpi.git watchdog-rpi
cd watchdog-rpi
make
```

**Check watchdog status:**

```bash
./wdt -reload 60
./wdt -period
```

Expected: Shows watchdog period (60 seconds)

**Check health:**

```bash
./wdt -health
```

Expected: No errors

---

## Phase 3: Calibration + Real Testing Procedure

### 3.1 Preparation
**Before calibration:**
1. Connect all load cells to 24b8vin inputs (CH1-CH4)
2. Wire excitation from SlimPak to load cells
3. Optional (recommended): wire excitation monitoring EXC+ → MegaIND AI (0-10V input)
4. System powered on for 10-20 minutes (thermal stabilization)
5. Scale empty and mechanically stable

### 3.2 Configure Channels
**Navigate to**: Dashboard → Config

1. Enable channels 1-4 (or 1-3 if using 3 load cells)
2. Set stack levels:
   - DAQ stack: 0
   - MegaIND stack: 0
3. Set I2C bus: 1
4. Save configuration

### 3.3 Verify Excitation
**Navigate to**: Dashboard

**Check "System Status" card:**
- Excitation voltage: ~10.0V (target)
- Status: GREEN (no warnings/faults)

If excitation is not wired yet, disable **Enable Excitation Monitoring** in Settings and continue calibration using raw mV.

**If excitation is low (<9.5V):**
1. Check SlimPak output with multimeter
2. Verify EXC+ and EXC- wiring to MegaIND AI
3. Check load cell connections

### 3.4 Verify Raw Signals
**Navigate to**: Dashboard or Config

**Check each channel's raw mV reading:**
- Should be non-zero but not saturated
- Typical range: -50 mV to +50 mV (unloaded)
- Channels should change when you press on that corner of scale

**⚠️ STOP: Record raw mV for each channel (empty scale).**

Example:
```
CH1: 1.23 mV
CH2: -0.45 mV
CH3: 0.87 mV
CH4: -1.12 mV
```

### 3.5 Stability Tuning
**Navigate to**: Config

**Initial settings (adjust based on vibration):**
- Filter alpha: 0.1 (or cutoff ~5 Hz)
- Stability window: 2.0 seconds
- Stability threshold: 0.5 lb stddev

**Test stability:**
1. Ensure scale is empty and still
2. Wait 5-10 seconds
3. Dashboard should show: **STABLE** (green indicator)
4. Tap the scale or add vibration
5. Dashboard should show: **UNSTABLE** (red indicator)

**If stability never triggers:**
- Increase stability threshold (try 1.0 lb or 2.0 lb)
- Increase stability window (try 3.0 seconds)

**If stability is too sensitive:**
- Decrease threshold (try 0.2 lb)
- Increase filter alpha (try 0.2 for more smoothing)

### 3.6 Zero Capture (Empty Scale)
**Navigate to**: Calibration

1. Ensure scale is **empty**
2. Wait for **STABLE** indicator
3. Note the raw signal value (sum of all channels)
4. Click "Add Point"
5. Enter:
   - Known weight: `0` lb
6. Confirm point is added to calibration table

**⚠️ STOP: Record zero point signal value.**

### 3.7 Multi-Point Calibration
**Prepare known weights:**
- Minimum 2 additional points (e.g., 25 lb and 100 lb)
- Recommended 3-5 points across expected range (e.g., 0, 25, 50, 100, 150 lb)

**For each calibration weight:**

1. Place known weight on scale (centered if possible)
2. Wait for **STABLE** indicator (may take 5-10 seconds)
3. Navigate to: Calibration
4. Click "Add Point"
5. Enter known weight in lb
6. Confirm point appears in calibration table

**Recommended calibration points:**
- 0 lb (empty)
- 25 lb (low end)
- 50 lb (mid-low)
- 100 lb (mid)
- 150 lb or max capacity (high end)

**After adding all points:**
1. Remove all weights (return to empty scale)
2. Dashboard should read: **0.0 lb ± 1 lb**
3. Add each test weight again and verify reading within ±2 lb

**⚠️ STOP: Record calibration points and verification readings.**

Example:
```
Calibration Points:
  0 lb → signal: 1234.5 mV
  25 lb → signal: 2345.6 mV
  100 lb → signal: 5678.9 mV

Verification:
  Empty: Dashboard reads 0.2 lb ✓
  25 lb: Dashboard reads 24.8 lb ✓
  100 lb: Dashboard reads 99.5 lb ✓
```

### 3.8 Save Calibration
**Directory**: `/var/lib/loadcell-transmitter`

**Calibration is automatically saved to SQLite database:**

```bash
ls -lh /var/lib/loadcell-transmitter/app.sqlite3
```

**To backup calibration:**

```bash
cp /var/lib/loadcell-transmitter/app.sqlite3 ~/app.sqlite3.backup-$(date +%Y%m%d-%H%M%S)
```

### 3.9 Verify Calibration Persists After Reboot

```bash
sudo reboot
```

**After reboot:**
1. SSH back in
2. Open dashboard
3. Place a known weight on scale
4. Verify reading matches calibrated value (within tolerance)

---

## Phase 4: Analog Output Verification

### 4.1 Configure Output Mode
**Navigate to**: Config → MegaIND Settings

1. Set output mode: `0-10V` (start with voltage mode)
2. Set scale range:
   - Min weight: `0` lb
   - Max weight: `150` lb (or your max calibrated weight)
3. Save configuration

### 4.2 Output Voltage Test Points
**Equipment needed**: Multimeter

**Measure between MegaIND AO+ and AO-**

**Expected mapping (0-10V mode, 0-150 lb range):**

| Weight | Expected Voltage | % of Range |
|--------|------------------|------------|
| 0 lb   | 0.0 V           | 0%         |
| 37.5 lb| 2.5 V           | 25%        |
| 75 lb  | 5.0 V           | 50%        |
| 112.5 lb| 7.5 V          | 75%        |
| 150 lb | 10.0 V          | 100%       |

**Test procedure for each point:**

1. Place weight on scale (or use closest available test weight)
2. Wait for **STABLE** indicator
3. Read dashboard weight: `___ lb`
4. Measure output voltage: `___ V`
5. Calculate expected voltage: `(weight / max_weight) * 10.0`
6. Verify measured voltage within ±0.2V of expected

**Example for 75 lb weight:**
- Dashboard: 74.8 lb
- Expected: (74.8 / 150) * 10.0 = 4.99 V
- Measured: 4.95 V ✓ (within ±0.2V)

**⚠️ STOP: Record all test point measurements.**

Example log:
```
Weight (lb) | Dashboard (lb) | Expected (V) | Measured (V) | Pass/Fail
------------|----------------|--------------|--------------|----------
0           | 0.2            | 0.01         | 0.00         | PASS
37.5        | 37.3           | 2.49         | 2.47         | PASS
75          | 74.8           | 4.99         | 4.95         | PASS
112.5       | 112.1          | 7.47         | 7.50         | PASS
150         | 149.6          | 9.97         | 9.98         | PASS
```

### 4.3 Test 4-20mA Mode (if PLC requires current input)
**Navigate to**: Config → MegaIND Settings

1. Set output mode: `4-20mA`
2. Save configuration

**Expected mapping (4-20mA mode, 0-150 lb range):**

| Weight | Expected Current | % of Range |
|--------|------------------|------------|
| 0 lb   | 4.0 mA          | 0%         |
| 37.5 lb| 8.0 mA          | 25%        |
| 75 lb  | 12.0 mA         | 50%        |
| 112.5 lb| 16.0 mA        | 75%        |
| 150 lb | 20.0 mA         | 100%       |

**Test with current meter or PLC analog input reading.**

### 4.4 Fault-Safe Output Test

**Test fault condition:**

> This test applies when excitation monitoring is enabled.

1. Disconnect SlimPak excitation (or simulate low excitation)
2. Dashboard should show: **FAULT** (red indicator)
3. Expected fault-safe output:
   - 0-10V mode: 0.0 V
   - 4-20mA mode: 4.0 mA
4. Measure output voltage/current
5. Verify matches expected fault-safe value
6. Reconnect excitation
7. Verify fault clears and normal operation resumes

---

## Phase 5: Final "TODAY" Checklist

### ✅ Bootstrap Complete
- [ ] Raspberry Pi OS installed and updated
- [ ] I2C enabled (`/dev/i2c-1` exists)
- [ ] Required packages installed (i2c-tools, python3, etc.)
- [ ] Repository cloned to `/opt/loadcell-transmitter`
- [ ] Python venv created and dependencies installed
- [ ] Systemd service installed and enabled
- [ ] Dashboard accessible at `http://<PI_IP>:8080`
- [ ] Service survives reboot

### ✅ Hardware Verified
- [ ] `i2cdetect -y 1` shows all expected boards
- [ ] Dashboard shows "Boards Online: 2/2"
- [ ] 24b8vin CLI tool can read all channels
- [ ] MegaIND CLI tool can set output voltage
- [ ] Watchdog (if present) is healthy

### ✅ Calibration Complete
- [ ] If excitation monitoring is enabled: excitation voltage reads ~10V (within ±0.5V)
- [ ] All load cell channels show plausible raw mV
- [ ] Stability detection works (STABLE/UNSTABLE toggles)
- [ ] Zero point captured (0 lb)
- [ ] At least 2 additional calibration points captured
- [ ] Verification test shows weight readings within ±2 lb
- [ ] Calibration persists after reboot

### ✅ Analog Output Verified
- [ ] Output mode configured (0-10V or 4-20mA)
- [ ] Scale range configured (min/max lb)
- [ ] Output voltage measured at 0%, 25%, 50%, 75%, 100%
- [ ] All measurements within ±0.2V (or ±0.5mA) of expected
- [ ] Fault-safe output verified (0V or 4mA on excitation fault, if excitation monitoring is enabled)

### ✅ System Health
- [ ] Dashboard shows live weight updates (no stale data)
- [ ] Stability indicator responds to scale vibration/motion
- [ ] No error messages in systemd logs
- [ ] SQLite database backed up
- [ ] System can run for 10+ minutes without crashes

---

## Troubleshooting Reference

### Issue: "Boards Online: 0/2" in dashboard

**Check:**
```bash
# 1. Verify I2C bus scan
i2cdetect -y 1

# 2. Check systemd logs for errors
sudo journalctl -u loadcell-transmitter -n 100

# 3. Check I/O status in logs (look for "I/O is LIVE" or "Hardware offline")
sudo journalctl -u loadcell-transmitter | grep -i "live\|offline\|initialized"

# 4. Restart service
sudo systemctl restart loadcell-transmitter
```

### Issue: Dashboard not accessible

**Check:**
```bash
# 1. Service status
sudo systemctl status loadcell-transmitter

# 2. Port binding (should show :8080)
sudo netstat -tulpn | grep 8080

# 3. Firewall (if enabled)
sudo ufw status
```

### Issue: Calibration points rejected

**Check:**
- Wait for **STABLE** indicator before adding point
- Reduce stability threshold if vibration prevents stable readings
- Increase filter alpha for more smoothing

### Issue: Output voltage incorrect

**Check:**
1. Verify scale range settings (min/max lb)
2. Check output mode (0-10V vs 4-20mA)
3. Measure with multimeter directly at MegaIND terminals
4. Check for wiring issues or loose connections
5. Verify calibration is loaded (check dashboard weight reading first)

### Issue: Excitation voltage low

**Check:**
1. SlimPak output voltage with multimeter
2. EXC+ → MegaIND AI wiring
3. Load cell wiring (broken connection can cause sag)
4. SlimPak power supply
5. If excitation is intentionally not wired yet, turn OFF **Enable Excitation Monitoring** in Settings.

---

## Quick Command Reference

```bash
# Service management
sudo systemctl status loadcell-transmitter
sudo systemctl restart loadcell-transmitter
sudo systemctl stop loadcell-transmitter
sudo systemctl start loadcell-transmitter
sudo journalctl -u loadcell-transmitter -f

# I2C diagnostics
i2cdetect -y 1
i2cget -y 1 0x31 0x00  # Read from 24b8vin (address 0x31)
i2cget -y 1 0x50 0x00  # Read from MegaIND (address 0x50)

# CLI tools
cd /opt/loadcell-transmitter/.vendor/24b8vin-rpi
./24b8vin -stack 0 rd 1

cd /opt/loadcell-transmitter/.vendor/megaind-rpi
./megaind -stack 0 uout 5

# Database backup
cp /var/lib/loadcell-transmitter/app.sqlite3 ~/backup-$(date +%Y%m%d-%H%M%S).sqlite3

# View application logs (if using file logging)
tail -f /var/lib/loadcell-transmitter/app.log
```

---

## Expected Timeline (TODAY)

| Phase | Task | Time Estimate |
|-------|------|---------------|
| 1 | Bootstrap (SSH → Running Dashboard) | 30-45 min |
| 2 | Hardware Smoke Tests | 15-30 min |
| 3 | Calibration + Real Testing | 45-60 min |
| 4 | Analog Output Verification | 30-45 min |
| 5 | Final Checklist + Documentation | 15-30 min |
| **Total** | | **~2.5-3.5 hours** |

**STOP POINTS** (send screenshots/output):
1. After Phase 1.7 — Dashboard screenshot
2. After Phase 2.1 — `i2cdetect -y 1` output
3. After Phase 2.3 — 24b8vin channel reads
4. After Phase 2.4 — MegaIND voltage measurements
5. After Phase 3.7 — Calibration points table
6. After Phase 4.2 — Output voltage test results

---

**END OF RUNBOOK**
