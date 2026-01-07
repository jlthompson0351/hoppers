# Current Implementation Documentation

**Document Version:** 2.2  
**Date:** December 19, 2025  
**Purpose:** Document current implementation after UI redesign, stability fixes, and weight-side “bulletproofing” (Settings wired to runtime + safer outputs + DB housekeeping)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Hardware Stack](#hardware-stack)
3. [Python Libraries](#python-libraries)
4. [Signal Filtering (Kalman)](#signal-filtering-kalman)
5. [Hardware Sample Averaging](#hardware-sample-averaging)
6. [Configuration Options](#configuration-options)
7. [File Structure](#file-structure)
8. [Deployment Process](#deployment-process)
9. [Pi Connection Details](#pi-connection-details)

---

## System Overview

The Load Cell Scale Transmitter reads weight from up to 8 load cell channels via the Sequent Microsystems 24b8vin DAQ HAT, applies filtering, and outputs a scaled analog signal (0-10V or 4-20mA) via the MegaIND HAT for PLC consumption.

### Architecture Flow

```
Load Cells (4x 350Ω)
       ↓
Sequent 24b8vin DAQ (8x 24-bit ADC)
       ↓ I2C
Raspberry Pi (Python App)
       ↓
┌──────────────────────────────────┐
│  Hardware Averaging (2 samples)  │
│            ↓                     │
│  Kalman Filter (zero-lag)        │
│            ↓                     │
│  Stability Detection             │
│            ↓                     │
│  Calibration Curve (PWL)         │
│            ↓                     │
│  Tare Offset                     │
│            ↓                     │
│  Output Scaling                  │
└──────────────────────────────────┘
       ↓ I2C
Sequent MegaIND (Analog Output)
       ↓
PLC (0-10V or 4-20mA input)
```

---

## Hardware Stack

### Physical Stack Order (Bottom to Top)

```
┌─────────────────────────────────┐
│   24b8vin HAT (TOP)             │ ← I2C: 0x31, Stack ID: 0
│   8x 24-bit Analog Inputs       │   Firmware: 1.4
├─────────────────────────────────┤
│   MegaIND HAT (BOTTOM)          │ ← I2C: 0x50, Stack ID: 0
│   Industrial Automation I/O     │   Firmware: 4.08
├─────────────────────────────────┤
│   Raspberry Pi 4B               │ ← Hostname: Hoppers
│   IP: 172.16.190.15             │   OS: Debian (aarch64)
└─────────────────────────────────┘
```

### 24b8vin DAQ HAT Capabilities

| Feature | Specification |
|---------|---------------|
| Channels | 8 differential inputs |
| Resolution | 24-bit |
| Input Ranges | ±10V to ±0.18V (gain selectable) |
| Gain Codes | 0-7 (7 = highest gain, ±0.18V) |
| Interface | I2C |
| CLI Tool | `24b8vin` |
| Python Library | `SM24b8vin` (vendored) |

### MegaIND HAT Capabilities

| Feature | Specification |
|---------|---------------|
| Analog Outputs | 4x 0-10V, 4x 4-20mA |
| Analog Inputs | 4x 0-10V, 4x 4-20mA |
| Digital I/O | 4 optocoupled inputs, 4 open-drain outputs |
| Interface | I2C |
| CLI Tool | `megaind` |
| Python Library | `megaind` (pip) |

---

## Python Libraries

### requirements.txt (Current)

```
Flask==3.0.0
waitress==2.1.2
smbus2>=0.4.3

# Math/calibration
numpy>=1.24.0

# Better logging (colors, rotation, easier syntax)
loguru>=0.7.0

# GPIO control (reset pins, data-ready signals on Pi)
RPi.GPIO>=0.7.1; platform_system == "Linux"

# Modbus TCP for PLC communication
pymodbus>=3.6.0
```

### Library Purposes

| Library | Purpose | Why We Use It |
|---------|---------|---------------|
| **Flask** | Web framework | Dashboard UI, REST API endpoints |
| **waitress** | WSGI server | Production-grade server (not Flask dev server) |
| **smbus2** | I2C communication | Low-level I2C for Sequent HATs |
| **numpy** | Math operations | Calibration regression, array math |
| **loguru** | Logging | Better than stdlib, colors, rotation, easier syntax |
| **RPi.GPIO** | GPIO control | Reset pins, data-ready signals |
| **pymodbus** | Modbus TCP | PLC communication protocol (future use) |

### Vendored Libraries (in `.vendor/`)

| Library | Location | Purpose |
|---------|----------|---------|
| SM24b8vin | `.vendor/24b8vin-rpi/python/` | 24b8vin DAQ Python driver |
| megaind-rpi | `.vendor/megaind-rpi/` | MegaIND reference (using pip version) |

---

## Signal Filtering (Kalman)

### Why Kalman Over Moving Average

| Filter Type | Lag | Noise Reduction | Response to Real Changes |
|-------------|-----|-----------------|--------------------------|
| Moving Average | HIGH (N/2 samples) | Good | Slow - averages out real changes |
| IIR/Exponential | Medium | Medium | Better but still lags |
| **Kalman Filter** | **ZERO** | **Excellent** | **Instant** - distinguishes noise from signal |

### Kalman Filter Implementation

**File:** `src/core/filtering.py`

```python
class KalmanFilter:
    """1D Kalman filter for load cell weight estimation.
    
    Key advantage over IIR/moving average:
    - Zero lag: Responds instantly to real weight changes
    - Optimal noise reduction: Distinguishes noise from real signal changes
    - Tunable: Adjust process_noise and measurement_noise per mode
    """
    
    def __init__(
        self,
        process_noise: float = 1.0,      # Q: how much weight changes between readings
        measurement_noise: float = 50.0,  # R: how noisy ADC readings are
        initial_value: float = 0.0,
    ) -> None:
        self.x = float(initial_value)  # State estimate
        self.P = 1000.0                 # Error covariance
        self.Q = float(process_noise)
        self.R = float(measurement_noise)
    
    def update(self, measurement: float) -> float:
        # Predict
        self.P = self.P + self.Q
        
        # Update
        y = measurement - self.x        # Innovation
        S = self.P + self.R             # Innovation covariance
        K = self.P / S                  # Kalman gain
        self.x = self.x + K * y         # Updated estimate
        self.P = (1.0 - K) * self.P     # Updated covariance
        
        return self.x
```

### Tuning Parameters

| Parameter | Description | Low Value | High Value |
|-----------|-------------|-----------|------------|
| `process_noise` (Q) | How much true weight changes between readings | Stable weight (hopper sitting) | Fast changes (filling/dumping) |
| `measurement_noise` (R) | How noisy ADC readings are | Trust measurements more (less filtering) | Filter more aggressively |

**Recommended Settings:**

| Mode | process_noise | measurement_noise | Use Case |
|------|---------------|-------------------|----------|
| Static Weighing | 1.0 | 50-100 | Stable hopper, need smooth display |
| Counting | 1.0 | 20-30 | Need to see small weight changes quickly |
| Dynamic Filling | 5-10 | 20-30 | Conveyor dropping parts into hopper |
| Fast Response | 10.0 | 20 | Maximum responsiveness, some jitter acceptable |

### Application Mode: Dynamic Filling (Conveyor + Hopper)

When parts are being dropped into a hopper by a conveyor:

**Expected Behavior:**
- Weight updates continuously at ~17Hz (every 60ms)
- PLC output follows weight in real-time
- STABLE indicator will show UNSTABLE during filling (this is normal!)
- ZERO and TARE buttons blocked during filling (by design)

**Recommended Settings for Dynamic Filling:**

| Setting | Value | Location |
|---------|-------|----------|
| Kalman Process Noise (Q) | 10.0 | Signal Tuning |
| Kalman Measurement Noise (R) | 25 | Signal Tuning |
| Stability Window | 25 samples | Signal Tuning |
| Stability Stddev | 3-5 lb | Signal Tuning |
| Stability Slope | 5-10 lb/s | Signal Tuning |
| Config Refresh | 30 s | Timing |

**Key Point:** The STABLE/UNSTABLE indicator does NOT affect weight reading or PLC output - it only blocks zero/tare operations. For continuous filling applications, the scale works fine even when showing UNSTABLE.

### Fallback to IIR

The system supports falling back to IIR filtering if needed:

```json
{
  "filter": {
    "use_kalman": false,
    "alpha": 0.18
  }
}
```

---

## Hardware Sample Averaging

### Implementation

**File:** `src/hw/sequent_24b8vin.py`

The DAQ wrapper takes multiple samples per read and averages them for hardware-level noise reduction:

```python
class Sequent24b8vin:
    def __init__(
        self,
        stack_id: int = 0,
        i2c_bus: int = 1,
        average_samples: int = 2,  # Default: 2 samples per read
    ) -> None:
        self.average_samples = max(1, int(average_samples))
    
    def read_differential_mv(self, channel: int) -> float:
        samples = []
        for i in range(self.average_samples):
            volts = float(self._board.get_u_in(vendor_ch))
            samples.append(volts)
            if i < self.average_samples - 1:
                time.sleep(0.002)  # 2ms delay for ADC settling
        
        avg_volts = sum(samples) / len(samples)
        return avg_volts * 1000.0  # mV
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `average_samples` | 2 | Number of samples to average per read |
| `SAMPLE_DELAY_S` | 0.002 | Delay between samples (2ms) |

**Config wiring (important):** `daq24b8vin.average_samples` from **Settings → DAQ Channels** is applied to the driver at startup and on config reload (no restart required).

---

## Configuration Options

### Backwards-Compatible Config Loading (Important)

Configurations are stored as JSON in SQLite (`config_versions.config_json`). As new features/settings are added, older deployments may have an older config “shape” (missing nested keys like `logging`, `zero_tracking`, etc.).

To prevent runtime failures and to ensure new settings always have safe defaults, `AppRepository.get_latest_config()` now:

- Loads the most recent saved JSON config (if present)
- Deep-merges it onto the current `default_config()`
- Returns the merged result

This guarantees new UI/templates (especially `/settings`) never break due to missing keys.

### Filter Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `filter.use_kalman` | bool | `true` | Use Kalman filter (vs IIR) |
| `filter.kalman_process_noise` | float | `1.0` | Q: process noise covariance |
| `filter.kalman_measurement_noise` | float | `50.0` | R: measurement noise covariance |
| `filter.alpha` | float | `0.18` | IIR filter alpha (if use_kalman=false) |
| `filter.stability_window` | int | `25` | Samples for stability detection |
| `filter.stability_stddev_lb` | float | `0.8` | Stddev threshold for stable (lbs) |
| `filter.stability_slope_lbs` | float | `0.8` | Slope threshold for stable (lbs/s) |
| `filter.median_enabled` | bool | `false` | Median pre-filter (spike rejection) |
| `filter.median_window` | int | `5` | Median window size (odd) |
| `filter.notch_enabled` | bool | `false` | Power-line notch filter enable |
| `filter.notch_freq` | int | `60` | Notch frequency (50 or 60 Hz) |

**Notes (implemented):**
- Median + notch run **before** Kalman/IIR (spike rejection → narrowband rejection → smoothing).
- The notch filter requires \( \text{loop_rate_hz} > 2 \times \text{notch_freq} \) (Nyquist). At the default 20 Hz loop rate, a 50/60 Hz notch will **auto-disable** (pass-through).

### Display Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `display.weight_decimals` | int | `1` | Decimal places for weight display (0, 1, or 2) |

### DAQ Channel Settings

| Key | Type | Description |
|-----|------|-------------|
| `daq24b8vin.channels[N].enabled` | bool | Channel enabled |
| `daq24b8vin.channels[N].role` | string | "Load Cell 1", "Excitation", etc. |
| `daq24b8vin.channels[N].gain_code` | int | 0-7 (7 = max gain, ±0.18V) |

### Range Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `range.min_lb` | float | `0.0` | Minimum weight for output scaling |
| `range.max_lb` | float | `300.0` | Maximum weight for output scaling |

### Excitation Monitoring

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `excitation.ai_channel` | int | `1` | MegaIND channel for excitation voltage (1-4) |
| `excitation.warn_v` | float | `9.0` | Warning threshold (volts) |
| `excitation.fault_v` | float | `8.0` | Fault threshold (volts) |

### Output Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `output.mode` | string | `"0_10V"` | Output mode: "0_10V" or "4_20mA" |
| `output.ao_channel_v` | int | `1` | MegaIND voltage output channel (1-4) |
| `output.ao_channel_ma` | int | `1` | MegaIND current output channel (1-4) |
| `output.safe_v` | float | `0.0` | Safe voltage on fault |
| `output.safe_ma` | float | `4.0` | Safe current on fault |
| `output.armed` | bool | `false` | Output interlock. When `false`, system forces safe output (no weight-based writes). |
| `output.test_mode` | bool | `false` | Test output active (overrides weight) |
| `output.test_value` | float | `0.0` | Test output value (V or mA) |
| `output.deadband_enabled` | bool | `true` | Hold output steady for small weight changes |
| `output.deadband_lb` | float | `0.5` | Deadband width (lbs) |
| `output.ramp_enabled` | bool | `false` | Slew-rate limit output changes (smoother PLC input) |
| `output.ramp_rate_v` | float | `5.0` | Max output rate (V/s) in 0–10V mode |
| `output.ramp_rate_ma` | float | `8.0` | Max output rate (mA/s) in 4–20mA mode |

### Scale Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `scale.tare_offset_lbs` | float | `0.0` | Software tare offset |

### Dump Detection

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `dump_detection.drop_threshold_lb` | float | `25.0` | Min drop to detect dump |
| `dump_detection.min_prev_stable_lb` | float | `10.0` | Min stable weight before dump |

### Drift Detection

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `drift.ratio_threshold` | float | `0.12` | Channel ratio drift threshold |
| `drift.ema_alpha` | float | `0.02` | EMA smoothing for drift |
| `drift.consecutive_required` | int | `20` | Consecutive warnings for alarm |

### Zero Tracking (Auto-Zero)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `zero_tracking.enabled` | bool | `false` | Auto-zero maintenance enable |
| `zero_tracking.range_lb` | float | `0.5` | Only track when within this band |
| `zero_tracking.rate_lbs` | float | `0.1` | Max correction rate (lb/s) |

### Startup

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `startup.auto_zero` | bool | `false` | Auto-zero when app starts (only if empty) |
| `startup.auto_arm` | bool | `false` | Auto-arm outputs after startup delay |
| `startup.delay_s` | int | `5` | Startup settling delay before “valid” operation |
| `startup.output_value` | float | `0.0` | Output value during startup delay |

### Alarms / Limits

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `alarms.overload_lb` | float\|null | `null` | Overload threshold (blank disables) |
| `alarms.overload_action` | string | `"alarm"` | `alarm` / `safe` / `lock` |
| `alarms.allow_negative` | bool | `false` | Allow negative weights (else clamp to 0) |
| `alarms.underload_lb` | float | `-5` | Underload warning threshold |
| `alarms.high_lb` | float\|null | `null` | High alarm threshold |
| `alarms.low_lb` | float\|null | `null` | Low alarm threshold |
| `alarms.rate_lbs` | float\|null | `null` | Rate-of-change alarm (lb/s) |

### Fault Handling

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `fault.delay_s` | float | `2.0` | Fault persistence required before triggering |
| `fault.recovery` | string | `"auto"` | `auto` or `manual` recovery |

### Timing

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `timing.loop_rate_hz` | int | `20` | Target acquisition loop rate |
| `timing.config_refresh_s` | float | `2.0` | Config reload interval from DB |
| `timing.i2c_retry_count` | int | `3` | I2C retries before declaring error |
| `timing.board_offline_s` | int | `5` | Time to mark a board offline |

**Notes (implemented):**
- `timing.loop_rate_hz` controls the acquisition loop sleep timing (best-effort). If I2C + processing can’t keep up, the **actual loop Hz** will be lower (shown in UI).

### Calibration Signal Units / Ratiometric Fallback

The acquisition loop publishes `weight.signal_for_cal` for the Calibration page.

- If ratiometric is effectively enabled (excitation present and non-trivial), `signal_for_cal` is **mV/V**.
- If excitation is missing/0V, the loop falls back to **raw mV** so calibration points can still be collected.

### Logging

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `logging.interval_s` | int | `1` | Trend log interval |
| `logging.retention_days` | int | `30` | Auto-delete logs older than this |
| `logging.log_raw` | bool | `false` | Include raw signal in logs |
| `logging.log_weight` | bool | `true` | Include weight in logs |
| `logging.log_output` | bool | `true` | Include output in logs |
| `logging.event_only` | bool | `false` | Only log on events |

**Notes (implemented):**
- Trend retention cleanup runs periodically (hourly) using `logging.retention_days`.
- `logging.log_raw=true` enables per-channel + excitation trend tables (in addition to the total trend).
- `logging.event_only=true` logs trends only on key events (fault/stable transitions, dump detected, drift warnings).

### Watchdog / Auxiliary Features

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `watchdog.daq_enabled` | bool | `false` | Enable 24b8vin watchdog |
| `watchdog.daq_period_s` | int | `120` | 24b8vin watchdog period |
| `watchdog.megaind_enabled` | bool | `false` | Enable MegaIND watchdog |
| `watchdog.megaind_period_s` | int | `120` | MegaIND watchdog period |
| `rs485.enabled` | bool | `false` | Enable RS485/MODBUS features (disabled by default) |
| `onewire.enabled` | bool | `false` | Enable One-Wire temperature sensors (disabled by default) |
| `leds.enabled` | bool | `false` | Enable LED control (disabled by default) |

---

## File Structure

```
hoppers/
├── .vendor/                      # Vendored libraries
│   ├── 24b8vin-rpi/             # Sequent DAQ driver
│   └── megaind-rpi/             # Sequent MegaIND driver
├── docs/                         # Documentation
├── scripts/                      # Utility scripts
│   ├── install_pi.sh            # Pi installation script
│   ├── run_pi.sh                # Run script for Pi
│   └── ...
├── src/
│   ├── app/                     # Flask web application
│   │   ├── __main__.py          # Entry point
│   │   ├── routes.py            # HTTP routes
│   │   └── templates/           # Jinja2 HTML templates
│   │       ├── base.html
│   │       ├── dashboard.html
│   │       ├── calibration.html
│   │       ├── settings.html    # Technician-friendly Settings (tabbed)
│   │       ├── config.html      # Config (Raw) JSON editor (maintenance)
│   │       ├── logs.html
│   │       ├── plc_profile.html
│   │       └── scale_settings.html  # Legacy hidden settings (deprecated)
│   ├── core/                    # Core algorithms
│   │   ├── calibration.py       # Calibration curve (PWL)
│   │   ├── drift.py             # Drift detection
│   │   ├── dump_detection.py    # Dump event detection
│   │   ├── filtering.py         # Kalman + IIR filters
│   │   ├── plc_profile.py       # PLC output curve
│   │   └── pwl.py               # Piecewise linear math
│   ├── db/                      # Database layer
│   │   ├── repo.py              # Repository pattern
│   │   ├── schema.py            # SQLite schema
│   │   └── migrate.py           # Migrations
│   ├── hw/                      # Hardware abstraction
│   │   ├── interfaces.py        # Abstract interfaces
│   │   ├── factory.py           # Hardware factory
│   │   ├── sequent_24b8vin.py   # Real DAQ driver
│   │   ├── sequent_megaind.py   # Real MegaIND driver
│   │   ├── sequent_24b8vin_stub.py  # Stub for dev
│   │   └── sequent_megaind_stub.py  # Stub for dev
│   └── services/                # Background services
│       ├── acquisition.py       # Main acquisition loop (with hardware retry)
│       ├── output_writer.py     # Analog output logic
│       ├── state.py             # Shared state for UI
│       └── watchdog.py          # Watchdog service
├── systemd/
│   └── loadcell-transmitter.service  # Systemd unit file
├── requirements.txt
└── README.md
```

---

## Deployment Process

### Files to Deploy

When pushing updates to the Pi:

```powershell
# Copy updated files
pscp -pw <password> requirements.txt pi@172.16.190.15:/opt/loadcell-transmitter/
pscp -pw <password> src/core/filtering.py pi@172.16.190.15:/opt/loadcell-transmitter/src/core/
pscp -pw <password> src/hw/sequent_24b8vin.py pi@172.16.190.15:/opt/loadcell-transmitter/src/hw/
pscp -pw <password> src/services/acquisition.py pi@172.16.190.15:/opt/loadcell-transmitter/src/services/
# ... etc for any changed files
```

### Install Dependencies

```powershell
plink -batch -ssh pi@172.16.190.15 -pw <password> "cd /opt/loadcell-transmitter && source .venv/bin/activate && pip install -r requirements.txt"
```

### Restart Service

```powershell
plink -batch -ssh pi@172.16.190.15 -pw <password> "sudo systemctl restart loadcell-transmitter"
```

### Verify

```powershell
plink -batch -ssh pi@172.16.190.15 -pw <password> "sudo systemctl status loadcell-transmitter --no-pager"
```

---

## Pi Connection Details

| Property | Value |
|----------|-------|
| **Hostname** | `Hoppers` |
| **IP Address** | `172.16.190.15` |
| **Dashboard URL** | http://172.16.190.15:8080 |
| **Username** | `pi` |
| **Password** | `depor` |
| **SSH Port** | 22 |
| **Network** | `Magni-Guest` |
| **App Location** | `/opt/loadcell-transmitter/` |
| **Data Directory** | `/var/lib/loadcell-transmitter/` |
| **Service Name** | `loadcell-transmitter.service` |

### Quick Commands

```bash
# SSH to Pi
ssh pi@172.16.190.15

# Check service status
sudo systemctl status loadcell-transmitter

# View logs (follow mode)
sudo journalctl -u loadcell-transmitter -f

# Restart service
sudo systemctl restart loadcell-transmitter

# Check I2C devices
sudo i2cdetect -y 1  # if command not found: sudo /usr/sbin/i2cdetect -y 1

# Read DAQ channel 1
24b8vin 0 rd 1

# Check MegaIND board
megaind 0 board
```

---

## Current UI Pages

| Page | URL Path | Purpose |
|------|----------|---------|
| Dashboard | `/` | Live weight, Zero/Tare buttons, PLC output status |
| Calibration Hub | `/calibration` | Unified Weight and PLC output "Hand-in-Hand" mapping |
| Settings | `/settings` | All system setup, port selection, and advanced maintenance |
| Config (Raw) | `/config` | Raw JSON system settings (maintenance) |
| Logs | `/logs` | Event log viewer |

### Dashboard Features
- Large prominent weight display
- STABLE/FAULT status indicators
- Zero, Tare, Clear Tare buttons
- System status bar (board online status)

### Calibration Hub Features (Hand-in-Hand)
- **Visual Weight Bar**: 0-100% capacity bar with live pointer.
- **Scale Calibration**: Multi-point load cell signal mapping (mV/V -> lb).
- **PLC Output Mapping**: Interactive "Live Match" nudge slider. Nudge the V/mA until the PLC matches the scale, then save.
- **Freeze Mode**: Suspends normal logic during nudging for stable calibration.

### Settings Features (Clean Split)
- **Quick Setup**: Set weight capacity, port selection (AO1-4), and output mode (0-10V/4-20mA).
- **MegaIND Tab**: 
    - Port mapping and conflict detection.
    - Advanced tools: Ramping (Smoothing), Safe Values.
    - **Internal Board Cal**: 2-point CLI tool for calibrating MegaIND hardware accuracy.

---

## Known Issues / Notes

1. **Service Stop Timeout**: Service takes ~90s to stop gracefully (systemd kills it). Consider adding signal handlers.

2. **Excitation Monitoring**: If excitation reads 0.00V (status DISABLED), verify:
   - `ratiometric` is enabled in Settings
   - MegaIND analog input channel is set correctly
   - excitation wiring (EXC+ to MegaIND AI, EXC− return)

   If ratiometric is enabled and excitation is low, the status will show WARN/FAULT and the system may force safe output depending on configuration.

3. **I2C Discovery Tools**: On some OS images, `i2cdetect` is installed at `/usr/sbin/i2cdetect`. If `i2cdetect` is “command not found”, run `sudo /usr/sbin/i2cdetect -y 1`.

---

## Recent Changes (v2.3)

### January 6, 2026

1. **Unified Calibration Hub**: Merged PLC output calibration into the Scale Calibration page for a "Hand-in-Hand" workflow.
2. **Interactive Live Nudge**: Added real-time voltage/mA nudging during calibration to match PLC displays precisely.
3. **Proportional Mapping**: Replaced simple linear output with Piece-wise Linear (PWL) mapping for perfectly accurate PLC readings.
4. **Clean Split Logic**: Separated "Setup" (Settings page) from "Training" (Calibration Hub).
5. **Conflict Guard**: Implemented auto-scanning for I/O pin conflicts between system roles and logic rules.
6. **Hardware Extensions**: Added support for Relays and Open-Drain outputs in the MegaIND drivers.

### December 19, 2025 (v2.2)

### December 18, 2025

1. **Stability Detector Bug Fix**: Fixed a bug where the `StabilityDetector` was being re-instantiated on every config refresh (every 2-30 seconds), which reset its internal buffer and prevented stable readings. Now only thresholds are updated; the buffer is preserved.

2. **Display Precision Setting**: Added configurable weight display precision (0, 1, or 2 decimal places) in Settings > Signal Tuning > Weight Display.

3. **Removed Emojis from UI**: Replaced all emoji icons in settings.html with plain text for better encoding compatibility when deploying via SCP/PSCP.

4. **Kalman Filter Tuning**: Documented application-specific settings:
   - Static weighing: Q=1.0, R=50
   - Dynamic filling (conveyor): Q=10.0, R=25

5. **Tare Offset API**: Added `/api/tare/clear` endpoint for programmatic tare clearing.

6. **Stability Window Documentation**: Clarified that large stability windows (e.g., 90 samples) cause slow tare response. Recommended 25 samples (~1.5 seconds at 17Hz).

7. **Dynamic Filling Mode**: Documented that STABLE/UNSTABLE indicator does NOT affect weight reading or PLC output - only blocks zero/tare operations. Scale works correctly for continuous filling even when showing UNSTABLE.

---

**Document Created:** December 18, 2025  
**Last Updated:** December 19, 2025 (v2.2 - Settings wired to runtime + output safety + DB housekeeping)
