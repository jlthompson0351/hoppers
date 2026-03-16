# Current Implementation Documentation

**Document Version:** 2.7  
**Date:** March 16, 2026  
**Purpose:** Document current implementation after job-control, webhook, floor-threshold, and between-jobs re-zero warning updates.

Status note (Feb 2026):
- This document contains historical implementation notes and current system state.
- For calibration behavior currently running in this repo, use:
  - `docs/CALIBRATION_CURRENT_STATE.md`
  - `docs/CalibrationProcedure.md`

**Recent Update (Feb 26, 2026):**
- **Job Target Signal Mode:** Added a webhook-driven output control mode (`POST /api/job/webhook`). When active, the scale output holds a low signal until the scale weight reaches a target weight (minus an optional pretrigger offset), at which point it sends a fixed trigger signal to the PLC.
- **Simplified Target Logic:** Replaced complex state machine with a pure threshold comparison (`scale_weight >= target - pretrigger`).
- **Dashboard Mode Toggle:** Added a quick toggle on the dashboard to switch between "Legacy Weight Mapping" and "Job Target Mode".
- **Target-Aware Auto-Zero:** Zero tracking now tracks `error = weight - zero_target_lb`, allowing auto-zero to work with an operator-configurable floor instead of assuming 0 lb.
- **Post-Dump Re-Zero:** Implemented one-shot correction after dump cycle completion.
- **Unrounded Control Loop:** Auto-zero and stability logic now use unrounded filtered weight for precision; rounding is display-only.
- **Bug Fix:** Fixed `NameError` in opto-button ZERO path.
- **Throughput Alignment:** Throughput cycle detection thresholds are now target-relative to support a configurable zero floor.

**Recent Update (Mar 5, 2026):**
- **Completed Job Webhook Pipeline:** Added transition-based job completion detection (close previous job when the next normal job ID arrives on the same line/machine scope).
- **Durable Outbox Retry:** Added persisted outbound queue for completed-job webhook delivery with retry/backoff.
- **Override Attribution:** Manual HDMI overrides are attributed to the active normal job window for summary reporting.
- **Record Timestamping:** Added `record_time_set_utc` (server-entered time) for set-weight records, independent of ERP timestamps.

**Recent Update (Mar 6, 2026):**
- **Basket Dump Opto Counting:** New opto action `basket_dump` records rising-edge pulses into `counted_events` table. Completed-job payload now includes `basket_dump_count`. Schema v7 migration adds `counted_events` table.
- **Configurable Floor Threshold:** Replaced implicit 3 lb floor with operator-editable `scale.zero_target_lb`. Job Target Signal mode can use 0.0 lb floor. Legacy mode holds `job_control.legacy_floor_signal_value` when `net_lbs <= zero_target_lb`.

**Recent Update (Mar 16, 2026):**
- **Between-Jobs Re-Zero Warning:** Added a non-blocking warning that latches after a completed dump/cycle when the scale settles stable and remains outside the configured zero tolerance.
- **Configurable Warning Threshold:** Added `scale.rezero_warning_threshold_lb` with a default of `20.0 lb`.
- **Operator Warning Surfaces:** `/hdmi` and `/` dashboard now render a persistent `Press ZERO before next job` banner when the warning is active.
- **Snapshot Contract:** `/api/snapshot` now exposes `rezero_warning_active`, `rezero_warning_reason`, `rezero_warning_weight_lbs`, `rezero_warning_threshold_lbs`, and `rezero_warning_since_utc`.
- **Completed-Job Webhook Diagnostics:** The completed-job payload now carries the latest re-zero warning status and post-dump re-zero outcome at job close time.

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
│  Zero Offset (signal domain mV)  │ ← CANONICAL: Applied before calibration
│            ↓                     │
│  Weight Calibration (1pt/2pt)    │ ← mV → lbs conversion
│            ↓                     │
│  Kalman Filter (zero-lag)        │
│            ↓                     │
│  Tare Offset (weight domain lbs) │ ← Applied after calibration
│            ↓                     │
│  Stability Detection             │
│  Zero Tracking (auto-correct)    │ ← Adjusts zero_offset_mv (Target-Aware)
│            ↓                     │
│  Output Scaling                  │
└──────────────────────────────────┘
       ↓ I2C
Sequent MegaIND (Analog Output)
       ↓
PLC (0-10V or 4-20mA input)
```

### Zeroing & Tare — Canonical mV Architecture

**Critical Design:** Zero correction occurs in the **signal domain (mV)** before weight calibration.

**Why this matters:**
- Zero offset is stored as `zero_offset_mv` (CANONICAL source of truth)
- `zero_offset_lbs` is a derived/cached field for display compatibility
- Zero tracking measures drift in lbs, then converts back to mV for storage
- This preserves calibration slope/gain integrity

**Manual Zero Operation:**
```python
# Manual ZERO button calculation (src/app/routes.py):
drift_mv = current_raw_mv - calibration_zero_mv
new_zero_offset_mv = old_zero_offset_mv + drift_mv
```

**Zero Tracking Operation (Target-Aware):**
```python
# Auto zero tracking (src/core/zero_tracking.py):
weight_error_lbs = current_gross_weight_lbs - zero_target_lb  # Target is the configured floor
signal_correction_mv = weight_error_lbs / lbs_per_mv  # Convert lbs → mV
new_zero_offset_mv = old_zero_offset_mv + signal_correction_mv
# Derive for display: zero_offset_lbs = zero_offset_mv * lbs_per_mv
```

**Storage (SQLite config JSON):**
- `zero_offset_mv` → Canonical field (applied to raw signal)
- `zero_offset_lbs` → Derived field (for UI display)
- `tare_offset_lbs` → Independent weight-domain offset (applied after calibration)

---

## Hardware Stack

### Physical Stack Order (Bottom to Top)

```
┌─────────────────────────────────┐
│   MegaIND HAT (TOP)             │ ← I2C: 0x52, Stack ID: 2
│   Industrial Automation I/O     │   Firmware: 4.8
├─────────────────────────────────┤
│   24b8vin HAT (BOTTOM)          │ ← I2C: 0x31, Stack ID: 0
│   8x 24-bit Analog Inputs       │   Firmware: 1.4
├─────────────────────────────────┤
│   Raspberry Pi 4B               │ ← Hostname: Hoppers
│   IP: 172.16.190.25             │   OS: Debian (aarch64)
└─────────────────────────────────┘

Load Cells: 4x S-type 350Ω → Summing Board → DAQ Channel 1
```

### Current Calibration (Feb 20, 2026)

**Hardware**: 4 S-type load cells wired to summing board, single channel output

**Calibration Points**: 9-point piecewise linear
- 3, 25, 50, 100, 150, 200, 250, 300, 335 lbs
- Anchor: 3 lb @ 5.644 mV (zero floor)
- Slope: 112 lb/mV (verified from 3-cell data, holds with 4 cells)

**PLC Output Profile**: 17 points (10-400 lb)
- Formula: V = (weight + 9) / 100
- PLC multiplier: 1000, -9 lb offset in PLC hardware
- Range: 10 lb (0.190V) to 400 lb (4.090V)
- Old vs New: Old 1.663V for 250 lb → New 2.590V for 250 lb

**Zero Floor**: 3 lb (prevents PLC dead zone < 0.1V)

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
| **numpy** | Math operations | General numeric helpers and utility math |
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

### Job Target Signal Mode (Webhook Control)

The scale can operate in two distinct output modes:
1.  **Legacy Weight Mapping:** The continuous 0-10V / 4-20mA output represents the current weight on the scale (e.g. 0V = 0lb, 10V = 400lb).
2.  **Job Target Signal Mode:** The output acts as a digital-like trigger signal for a PLC batching system.

**How Job Target Mode Works:**
- An external system sends an HTTP `POST` to `/api/job/webhook` with payload:
  `{"event":"job.load_size_updated","jobId":"...","machine_id":"...","line_id":"...","set_weight":100.0,"unit":"lb","idempotencyKey":"...","timestamp":"...","product_id":"...","operator_id":"..."}`
- Backward-compatible payload keys are still accepted (`machineKey`, `loadSize`).
- On each authenticated receipt, the full webhook JSON payload is stored in `set_weight_history.metadata_json`.
- While `scale_weight < (set_weight - pretrigger_lb)`, the scale outputs a fixed `low_signal_value` (e.g., 0.0V).
- When `scale_weight >= (set_weight - pretrigger_lb)`, the scale outputs a fixed `trigger_signal_value` (e.g., 10.0V).
- The mode is toggleable from the main Dashboard UI or the Settings page.
- If mode is not enabled (`legacy_weight_mapping`), webhook updates are rejected with HTTP `409` by design.

**Configuration (`job_control` block):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Whether target mode is active. |
| `mode` | str | `legacy_weight_mapping` | `legacy_weight_mapping` or `target_signal_mode`. |
| `trigger_mode` | str | `exact` | `exact` (trigger at target) or `early` (trigger at target - offset). |
| `legacy_floor_signal_value` | float/null | `null` | Optional fixed legacy-mode PLC output to hold while live weight is at/below `scale.zero_target_lb`. `null` means auto-follow the PLC profile at the floor weight. |
| `trigger_signal_value` | float | `1.0` | Output value when target is reached. |
| `low_signal_value` | float | `0.0` | Output value when below target. |
| `pretrigger_lb` | float | `0.0` | Early trigger offset (only applied if `trigger_mode` is `early`). |
| `webhook_token` | str | `""` | Required token for API endpoints. |
| `completed_job_webhook_url` | str | `""` | Optional destination URL for completed-job summary POST delivery. |

**API Endpoints:**

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/job/mode` | POST | None | Toggle mode: `{"mode": "target_signal_mode"}` or `{"mode": "legacy_weight_mapping"}` |
| `/api/job/webhook` | POST | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Set target weight from external system payload |
| `/api/job/status` | GET | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Returns `{enabled, mode, status: {set_weight, active, meta}}` |
| `/api/job/clear` | POST | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Clears active job, resets output to low signal |
| `/api/job/trigger/from-nudge` | POST | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Captures current output nudge value as trigger signal |

**Webhook payload requirements:**
- `event` (string, optional; if present must be `job.load_size_updated`)
- `jobId` (string, required; `product_id` can be used as fallback)
- `machine_id` or `machineKey` (string, required)
- `line_id` (string, optional; defaults to `default_line`)
- `set_weight` or `loadSize` (float, required, >= 0)
- `unit` (optional; `lb`, `kg`, `g`, `oz`; defaults to `lb`)
- `idempotencyKey` (string, required, used for dedupe)
- `timestamp` (ISO-8601 string, required)
- `product_id` / `operator_id` (optional, persisted)

**Runtime behavior:**
- Durable persistence uses SQLite tables:
  - `set_weight_current` for fast latest lookup by `(line_id, machine_id)`
  - `set_weight_history` for append-only audit (every authenticated receipt)
  - `job_lifecycle_state` for restart-safe active job tracking
  - `job_completion_outbox` for durable retryable completed-job webhook delivery
  - `counted_events` for opto-driven counts (e.g. `basket_dump`) per job window; completed-job payload includes `basket_dump_count`
- `set_weight_current` and `set_weight_history` include `record_time_set_utc` (server-entered record time).
- The full webhook payload is stored in `set_weight_history.metadata_json`.
- Duplicate `idempotencyKey` values are accepted as replays; they append history with `duplicate_event=1` and do not overwrite `set_weight_current`.
- On startup, acquisition restores from `set_weight_current` first; legacy `job_control` config is kept as compatibility fallback.
- On job transition, a completed-job summary payload is enqueued and posted asynchronously from the acquisition service.
- The trigger signal dropdown on the Settings > Job Target Mode tab is populated from existing PLC profile points (Calibration Hub). Operator picks a known voltage/weight pair instead of typing a raw number.
- Switching mode via dashboard toggle immediately changes the output path. If a job is active during toggle to legacy, output reverts to proportional weight mapping.

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

**DEPRECATED**: The `range.min_lb` and `range.max_lb` settings have been removed. PLC output mapping is now configured via Calibration Hub (train weight/voltage pairs). System calculates volts-per-pound from saved profile points. An internal linear fallback (0-250 lb) only kicks in when no profile points are trained.

### Excitation Monitoring

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `excitation.enabled` | bool | `true` | Master enable for excitation monitoring. When `false`, excitation is not used for fault-safe output gating. |
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
| `output.armed` | bool | `true` | Output interlock. When `false`, system forces safe output (no weight-based writes). **Defaults to ARMED** for automatic startup. |
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
| `scale.zero_target_lb` | float | `0.0` | Operator-editable floor threshold. ZERO and target-aware empty logic use this weight as the floor target. Set to `0.0` when no floor is desired. |

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
| `zero_tracking.enabled` | bool | `false` | Auto-zero maintenance enable (**currently DISABLED** - manual ZERO preferred) |
| `zero_tracking.range_lb` | float | `25.0` | Only track when within ±this band |
| `zero_tracking.deadband_lb` | float | `0.1` | Stop correcting when inside this band |
| `zero_tracking.hold_s` | float | `0.5` | Wait time before tracking starts (sec) |
| `zero_tracking.negative_hold_s` | float | `8.0` | Wait time for negative weight (fast path) |
| `zero_tracking.rate_lbs` | float | `50.0` | Max correction rate (lb/s) |
| `zero_tracking.persist_interval_s` | float | `1.0` | How often to save offset during tracking |
| `zero_tracking.post_dump_enabled` | bool | `true` | Enable one-shot re-zero after dump cycle |
| `zero_tracking.post_dump_min_delay_s` | float | `5.0` | Wait time after dump before re-zero attempt |
| `zero_tracking.post_dump_window_s` | float | `10.0` | Max time to wait for stable empty condition |
| `zero_tracking.post_dump_empty_threshold_lb` | float | `4.0` | Weight must be within ±this of zero target |
| `zero_tracking.post_dump_max_correction_lb` | float | `8.0` | Max single correction allowed |

**Zero Tracking State Machine:**
- **ACTIVE (tracking):** Baseline adjusting now
- **ACTIVE (deadband):** Within ±0.1 lb, no correction needed
- **LOCKED (holdoff):** Waiting for hold timer (6 sec of stable)
- **LOCKED (load_present):** Weight on scale (|weight| > range)
- **LOCKED (unstable):** Scale bouncing/settling
- **LOCKED (tare_active):** Container weight set
- **DISABLED:** Feature off

**Additional Safety Guards:**
- Spike rejection via slope threshold
- Persistence throttling to reduce SD card wear
- Calibration slope (lbs/mV) always preserved

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

### Calibration Signal + Point Handling

The acquisition loop publishes `weight.signal_for_cal` for the Calibration page.

- `signal_for_cal` is captured in **raw mV**.
- Adding a point is append-only; repeated same-weight points are kept as history.
- Runtime mapping currently uses single-point or two-point linear behavior.
- Single-point operation remains available via zero-crossing slope fallback.

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
│   │   ├── filtering.py         # Kalman + stability
│   │   ├── zero_tracking.py     # Auto-zero state machine
│   │   ├── post_dump_rezero.py  # Post-dump re-zero logic
│   │   ├── throughput_cycle.py  # Cycle detection logic
│   │   └── zeroing.py           # Zero + calibration mapping helpers
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
│       └── state.py             # Shared state for UI
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
pscp -pw <password> requirements.txt pi@172.16.190.25:/opt/loadcell-transmitter/
pscp -pw <password> src/core/filtering.py pi@172.16.190.25:/opt/loadcell-transmitter/src/core/
pscp -pw <password> src/hw/sequent_24b8vin.py pi@172.16.190.25:/opt/loadcell-transmitter/src/hw/
pscp -pw <password> src/services/acquisition.py pi@172.16.190.25:/opt/loadcell-transmitter/src/services/
# ... etc for any changed files
```

### Install Dependencies

```powershell
plink -batch -ssh pi@172.16.190.25 -pw <password> "cd /opt/loadcell-transmitter && source .venv/bin/activate && pip install -r requirements.txt"
```

### Restart Service

```powershell
plink -batch -ssh pi@172.16.190.25 -pw <password> "sudo systemctl restart loadcell-transmitter"
```

### Verify

```powershell
plink -batch -ssh pi@172.16.190.25 -pw <password> "sudo systemctl status loadcell-transmitter --no-pager"
```

---

## Pi Connection Details

| Property | Value |
|----------|-------|
| **Hostname** | `Hoppers` |
| **IP Address** | `172.16.190.25` |
| **Dashboard URL** | http://172.16.190.25:8080 |
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
ssh pi@172.16.190.25

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
| Dashboard | `/` | Live weight, Zero/Tare buttons, PLC output status, HDMI launch controls |
| HDMI Interface | `/hdmi` | Touch-optimized operator interface for 800x480 displays |
| Calibration Hub | `/calibration` | Unified Weight and PLC output "Hand-in-Hand" mapping |
| Settings | `/settings` | All system setup, port selection, and advanced maintenance |
| Config (Raw) | `/config` | Raw JSON system settings (maintenance) |
| Logs | `/logs` | Event log viewer |

### Dashboard Features
- Large prominent weight display
- STABLE/FAULT status indicators
- Zero, Tare, Clear Tare buttons
- Zero offset display (lb + mV) with timestamp
- Zero tracking status (ACTIVE/LOCKED + reason)
- **HDMI Launch Controls**: `LAUNCH HDMI ON PI` and emergency `FORCE RELAUNCH HDMI` buttons.
- System status bar (board online status)

### HDMI Interface Features
- **Optimized Layout**: Designed for 800x480 industrial touch panels.
- **Two-Column Operator View**: Left card for centered live weight and Job Target data, right card for Zero/Tare diagnostics and daily/shift totals.
- **Job Target Panel**: Shows live `Scale Weight` and `Set Weight` when target mode is active.
- **Zero Diagnostics on HDMI**: Shows `Tare`, `Zero Offset`, `Zero Tracking`, and `Zero Updated` in the right panel.
- **Processed Weight Totals**: Includes shift/day totals, load count, average load, and a `CLEAR SHIFT` button.
- **Simplified Controls**: Large touch-friendly buttons for ZERO, TARE, CLEAR TARE, CLEAR ZERO, and SETTINGS.
- **Auto-Start**: Managed by `kiosk.service` to launch at boot.

### Calibration Hub Features (Hand-in-Hand)
- **Visual Weight Bar**: 0-100% capacity bar with live pointer.
- **Scale Calibration**: Single-point/two-point linear load cell mapping (raw mV -> lb).
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

2. **Excitation Monitoring**:
   - If monitoring is enabled and excitation reads near 0.00V, verify:
   - MegaIND analog input channel is set correctly
   - excitation wiring (EXC+ to MegaIND AI, EXC− return)
   - board power and common reference wiring
   - If excitation is intentionally not wired yet, disable it in **Settings -> Quick Setup -> Enable Excitation Monitoring**.

   Calibration capture still uses raw mV. Excitation WARN/FAULT drives safe output behavior only while excitation monitoring is enabled.

3. **I2C Discovery Tools**: On some OS images, `i2cdetect` is installed at `/usr/sbin/i2cdetect`. If `i2cdetect` is “command not found”, run `sudo /usr/sbin/i2cdetect -y 1`.

---

## Recent Changes (v2.6 -> v3.3)

### February 25, 2026 (v3.4)
1. **Target-Aware Auto-Zero**: Zero tracking now maintains `zero_target_lb` (3.0 lb) instead of 0.0 lb.
2. **Post-Dump Re-Zero**: Added one-shot correction after dump cycle completion.
3. **Unrounded Control Loop**: Auto-zero and stability logic now use unrounded filtered weight for precision.
4. **Bug Fix**: Fixed `NameError` in opto-button ZERO path.
5. **Throughput Alignment**: Throughput cycle detection thresholds are now target-relative.

### February 23, 2026 (v3.3.1)
1. **Crash Fix (Flask service)**: Replaced undefined `cal_zero_sig` with `cal_target_sig` in the `/api/zero` manual zero endpoint (`routes.py`) to prevent crash loop.

### February 20, 2026 (v3.3)

1. **Hardware Upgrade**: Added 4th load cell (was 3, now 4 S-type cells on summing board)
2. **Full Recalibration**: 9-point piecewise linear (3-335 lbs), slope 112 lb/mV, anchor 3 lb @ 5.644 mV
3. **New PLC Profile**: 17 points (10-400 lb), formula V = (weight + 9) / 100, fixed bad PLC zero offset
4. **Zero Floor Feature**: ZERO button now targets 3 lb instead of 0 lb (prevents PLC dead zone < 0.1V)
5. **Negative Dump Fix**: Empty weight floored to `max(0, empty_lbs)` in throughput_cycle.py to prevent inflated dump totals
6. **Code Safety**: Fixed 4 division-by-zero locations (`lbs_per_mv is not None and abs(...)` checks)
7. **Zero Tracking Gate**: Disabled during calibration mode (`calibration_active` check)
8. **High-Res Logging**: 20Hz logging to trends_total (delayed start Monday Feb 23, 2026 06:00 EST)
9. **Deploy Scripts**: Updated to include `throughput_cycle.py` in file lists

### February 2026 (v2.5)

1. **HDMI layout refined for 800x480**: centered weight card, dashboard-style zero diagnostics, and right-side daily/shift placeholder panel.
2. **Shift clear UX scaffolded**: `CLEAR SHIFT TOTAL` added as UI-only placeholder while throughput database integration is in progress.
3. **HDMI docs synchronized**: runbook, architecture, and UI references updated to match deployed behavior.
4. **Calibration behavior review documented**: code-backed runtime behavior and drift separation documented in `docs/CALIBRATION_CURRENT_STATE.md`.
5. **Procedure docs aligned**: operator calibration docs now match current single/two-point runtime behavior.
6. **API/UI docs clarified**: `/api/calibration/add` and calibration UI docs now describe append-only capture behavior.

### January 6, 2026

1. **Unified Calibration Hub**: Merged PLC output calibration into the Scale Calibration page for a "Hand-in-Hand" workflow.
2. **Interactive Live Nudge**: Added real-time voltage/mA nudging during calibration to match PLC displays precisely.
3. **Profile-Based Mapping**: Uses trained PLC profile points for output mapping. System interpolates between trained weight/voltage pairs, with optional deadband/ramp controls.
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
**Last Updated:** February 25, 2026 (v3.4 - Target-Aware Auto-Zero, Post-Dump Re-Zero, Unrounded Control Loop)
