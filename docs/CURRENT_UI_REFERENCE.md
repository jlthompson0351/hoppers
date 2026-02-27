# Current UI Reference

**Document Version:** 2.3  
**Date:** February 12, 2026  
**Purpose:** Document current UI state after redesign and stability fixes

---

## Table of Contents

1. [Page Overview](#page-overview)
2. [Dashboard Page](#dashboard-page)
3. [HDMI Operator Page](#hdmi-operator-page)
4. [Calibration Page](#calibration-page)
5. [PLC Output Configuration Page](#plc-output-configuration-page)
6. [Settings Page](#settings-page)
7. [Config Page (Raw)](#config-page-raw)
8. [Logs Page](#logs-page)
9. [API Endpoints](#api-endpoints)
10. [Template Structure](#template-structure)
11. [CSS Variables](#css-variables)

---

## Page Overview

| Page | URL | Purpose | Requires Maintenance Mode |
|------|-----|---------|---------------------------|
| Dashboard | `/` | Live weight, Zero/Tare, status | No |
| HDMI Operator | `/hdmi` | 800x480 operator UI with large weight and touch controls | No |
| Calibration Hub | `/calibration` | Unified Weight and PLC output mapping | No |
| Settings | `/settings` | All system configuration and advanced tools | No |
| Config (Raw) | `/config` | Raw JSON config editor (maintenance) | **Yes** |
| Logs | `/logs` | Event log viewer | No |

---

## Dashboard Page

**URL:** `/`  
**Template:** `templates/dashboard.html`  
**Route:** `routes.dashboard()`

### Layout (Redesigned)

```
┌─────────────────────────────────────────────────────────────────┐
│  Load Cell Scale Transmitter                    [Nav Links]     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    ┌─────────────────────┐                      │
│                    │      25.0 lb        │  ← Large weight      │
│                    │   [STABLE] [OK]     │  ← Status pills      │
│                    └─────────────────────┘                      │
│                                                                 │
│        [ ZERO ]  [ TARE ]  [ CLEAR TARE ]                       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [ LEGACY WEIGHT MAPPING ] | [ JOB TARGET MODE ]                 │
├───────────────────────────────┬─────────────────────────────────┤
│      PLC OUTPUT               │      RAW DATA                   │
│      0.833 V (0-10V)          │      Signal: 0.002500           │
│      Channel 1                │      Raw mV: 0.625              │
│      [■■■■■░░░░░] 27.7%      │      Loop Hz: 14.1              │
├───────────────────────────────┴─────────────────────────────────┤
│      DAQ [●] Online     MegaIND [●] Online     Excitation: OK   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Large Weight Display** - Prominent total weight in lbs (always updates, even when UNSTABLE)
2. **Status Pills** - STABLE/UNSTABLE, OK/FAULT indicators
3. **Zero Button** - Sets current weight as zero reference (requires STABLE)
4. **Tare Button** - Adds current weight to tare offset (requires STABLE)
5. **Clear Tare** - Removes tare offset (always available)
6. **PLC Output Panel** - Shows commanded output, mode, channel, scale bar (always updates)
7. **Raw Data Panel** - Signal for calibration, raw mV, loop Hz
8. **System Status Bar** - Board online status, excitation status
9. **Mode Toggle Strip** - Switches between Legacy Weight Mapping and Job Target Mode. When Job Target Mode is active, a dedicated status bar appears showing Set Weight, Scale Weight, and Trigger Status.

### Stability Indicator Behavior

| What | Affected by UNSTABLE? | Notes |
|------|----------------------|-------|
| Weight display | NO | Always updates at ~17Hz |
| PLC output | NO | Always sent to PLC |
| Zero button | YES | Blocked when unstable |
| Tare button | YES | Blocked when unstable |
| Clear Tare | NO | Always available |

**For dynamic filling applications** (conveyor dropping parts): The scale will show UNSTABLE while weight is changing rapidly. This is NORMAL and does not affect weight reading or PLC output.

### JavaScript Polling

- Polls `/api/snapshot` at the configured poll rate (`ui.poll_rate_ms` in Settings → Timing → Dashboard Poll Rate; default 500ms)
- Updates all values via DOM manipulation
- Handles Zero/Tare/Clear via POST to API endpoints

### API Calls

| Action | Endpoint | Method |
|--------|----------|--------|
| Zero | `/api/zero` | POST |
| Tare | `/api/tare` | POST |
| Clear Tare | `/api/tare/clear` | POST |
| Snapshot | `/api/snapshot` | GET |

---

## HDMI Operator Page

**URL:** `/hdmi`  
**Template:** `templates/hdmi.html`  
**Route:** `routes.hdmi()`

### Layout (800x480)

```
┌─────────────────────────────────────────────────────────────────┐
│  Scale HDMI                                      [STABLE] [OK]  │
├───────────────────────────────────┬─────────────────────────────┤
│            75.1                   │  Job Target                  │
│             lb                    │  Set Weight       100.0 lb   │
│  Tare: 0.0 lb                     │  Scale Weight      75.1 lb   │
│  Zero Offset: -2.064 lb (...)     │  Processed Weight            │
│  Zero Tracking: ACTIVE (...)      │  Shift / Today / Loads / Avg │
│  Zero Updated: 13:20:24           │  [ CLEAR SHIFT ]             │
├───────────────────────────────────┴─────────────────────────────┤
│ [ ZERO ] [ TARE ] [ CLEAR TARE ] [ SETTINGS ]                   │
├─────────────────────────────────────────────────────────────────┤
│ DAQ [●]   I/O [●]   Loop: 20.0 Hz   Updated: 13:01:27          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Centered Live Weight Card** - Weight and unit are centered for better readability at distance
2. **Zero Diagnostics In-Card** - Shows tare, zero offset, zero tracking state/reason, and last zero update
3. **Job Target Panel** - Shows `Set Weight` and live `Scale Weight` when target mode is active
4. **Processed Totals Panel** - Shows shift/day totals, load count, and average load
5. **Shift Clear Action** - `CLEAR SHIFT` calls `/api/production/shift/clear` to reset shift window
6. **Bottom Control Row** - `ZERO`, `TARE`, `CLEAR TARE`, `CLEAR ZERO`, `SETTINGS`
7. **Kiosk Fit** - Sized specifically for fixed 800x480 HDMI touch displays

### Snapshot Fields Used by HDMI

- `weight.total_lbs`
- `weight.tare_offset_lbs`
- `weight.zero_offset_lbs`
- `weight.zero_offset_mv` (fallback `weight.zero_offset_signal`)
- `weight.zero_tracking_enabled`
- `weight.zero_tracking_active`
- `weight.zero_tracking_locked`
- `weight.zero_tracking_reason`
- `weight.zero_offset_updated_utc`
- `jobControl.enabled`
- `jobControl.mode`
- `jobControl.set_weight`
- `jobControl.active`
- `system.loop_hz`
- `system.last_update_utc`
- `boards.online`

### API Calls

| Action | Endpoint | Method |
|--------|----------|--------|
| Zero | `/api/zero` | POST |
| Tare | `/api/tare` | POST |
| Clear Tare | `/api/tare/clear` | POST |
| Clear Zero | `/api/zero/clear` | POST |
| Clear Shift | `/api/production/shift/clear` | POST |
| Snapshot Poll | `/api/snapshot` | GET |
| Settings Navigation | `/settings` | GET |

---

## Calibration Page

**URL:** `/calibration`  
**Template:** `templates/calibration.html`  
**Routes:** `routes.calibration_get()`

### Layout (Redesigned)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Scale Calibration                            │
│                                                                 │
│    ┌───────────────┐     ┌───────────────┐                      │
│    │   25.0 lb     │     │  0.002500     │                      │
│    │ Current Weight│     │ Current Signal│                      │
│    │   [STABLE]    │     │               │                      │
│    └───────────────┘     └───────────────┘                      │
│                                                                 │
│    How to Calibrate:                                            │
│    1. Place known weight on scale                               │
│    2. Wait for STABLE indicator                                 │
│    3. Enter weight value and click Add Point                    │
│                                                                 │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │  Known Weight: [______] lb    [ Add Calibration Point ] │  │
│    └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│    Saved Calibration Points:                                    │
│    ┌─────────────────────────────────────────────────────────┐  │
│    │ # │ Weight (lb) │ Signal    │ Time     │ Action         │  │
│    │ 1 │ 0.00        │ 0.000000  │ 10:30:00 │ [Delete]       │  │
│    │ 2 │ 25.00       │ 0.002500  │ 10:35:00 │ [Delete]       │  │
│    │ 3 │ 50.00       │ 0.005000  │ 10:40:00 │ [Delete]       │  │
│    └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│    [ Clear All Points ]                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **Live Weight & Signal Display** - Shows current values for reference (signal shown in raw mV)
2. **Stability Indicator** - Shows STABLE/UNSTABLE badge
3. **Add Calibration Point** - Form to add known weight
4. **Points Table** - List of saved calibration points with delete buttons
5. **Clear All Points** - Button to remove all calibration data

### Calibration Point Behavior

- Calibration signal is captured in raw **mV**.
- Adding a point is append-only; repeated same-weight points are kept as history.
- Weight mapping currently uses single-point or two-point linear behavior.
- If only one point exists, the runtime uses single-point slope fallback.

### API Calls

| Action | Endpoint | Method |
|--------|----------|--------|
| Add Point | `/api/calibration/add` | POST |
| Delete Point | `/api/calibration/delete/<id>` | POST |
| Clear All | `/api/calibration/clear` | POST |

---

## PLC Output Configuration Page

**URL:** `/plc-profile`  
**Template:** `templates/plc_profile.html`  
**Routes:** `routes.plc_profile_get()`

**Default State:** Outputs are **ARMED** on startup (changed 2026-02-12). Manual disarm available for maintenance.

### Layout (Redesigned)

```
┌─────────────────────────────────────────────────────────────────┐
│                 PLC Output Configuration                        │
│         Configure analog output to PLC and correction curve     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ⚠️ OUTPUTS DISARMED          [ ARM OUTPUTS ]            │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  ✓ OUTPUTS ARMED              [ DISARM OUTPUTS ]         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────┐  ┌─────────────────────────────┐   │
│  │   📊 LIVE OUTPUT        │  │   ⚙️ OUTPUT CONFIGURATION   │   │
│  │                         │  │                             │   │
│  │      0.833 V            │  │   Mode: [0-10V ▼]           │   │
│  │   Commanded Output      │  │   Channel: [1 ▼]            │   │
│  │                         │  │   Safe Output: [0.000]      │   │
│  │   25.0    0.833 V       │  │   [ Save Configuration ]    │   │
│  │  Weight   Readback      │  │                             │   │
│  │                         │  │   PLC Profile: Train in     │   │
│  │  PLC mapping via        │  │   Calibration Hub           │   │
│  │  Calibration Hub        │  ├─────────────────────────────┤   │
│  └─────────────────────────┘  │   📡 MEGAIND STATUS         │   │
│                               │   Board: ✓ Online           │   │
│  ┌─────────────────────────┐  │   Firmware: 4.8             │   │
│  │   🔧 TEST OUTPUT        │  │   Power: 24.1 V             │   │
│  │   ⚠️ Test overrides     │  │   Readback: 0.833 V         │   │
│  │                         │  └─────────────────────────────┘   │
│  │   Value: [5.000]        │                                    │
│  │   [ START TEST OUTPUT ] │  ← Toggle button                   │
│  │   [ STOP TEST OUTPUT ]  │  ← Changes when active             │
│  └─────────────────────────┘                                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   🎯 OUTPUT CALIBRATION (MegaIND)                        │   │
│  │   Two-point calibration for accurate analog output       │   │
│  │                                                          │   │
│  │   Type: [0-10V ▼]   Channel: [1 ▼]   Status: Not Cal'd   │   │
│  │                                                          │   │
│  │   [1] Low Ref: [0.5] V    [ Capture Point 1 ]            │   │
│  │   [2] High Ref: [9.5] V   [ Capture Point 2 ]            │   │
│  │   [✓]                     [ Reset to Factory ]           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │   📈 PLC CORRECTION CURVE                                │   │
│  │   Fine-tune if PLC has scaling errors                    │   │
│  │                                                          │   │
│  │   [0-10V] [4-20mA]                                       │   │
│  │                                                          │   │
│  │   Output: [___] V   PLC Shows: [___] lb   [ Add Point ]  │   │
│  │                                                          │   │
│  │   # │ Output (V) │ PLC Shows (lb) │ Time     │ Action    │   │
│  │   1 │ 0.000      │ 0.00           │ 10:30:00 │ [Delete]  │   │
│  │   2 │ 5.000      │ 150.00         │ 10:35:00 │ [Delete]  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Key Features

1. **ARM/DISARM Toggle** - Safety control for enabling outputs
2. **Live Output Monitor** - Real-time commanded output, weight, readback
3. **Output Configuration** - Mode (0-10V/4-20mA), channel, safe output. PLC mapping configured via Calibration Hub.
4. **MegaIND Status** - Board online, firmware, power supply, output readback
5. **Test Output Toggle** - Starts/stops manual test output (stays on until stopped)
6. **Output Calibration** - Two-point calibration for MegaIND analog outputs
7. **PLC Correction Curve** - Add/delete points to correct PLC scaling errors

### Test Output Behavior

- Click **START TEST OUTPUT** → Output stays at test value until stopped
- UI changes to red "TEST OUTPUT ACTIVE" state
- Button changes to **STOP TEST OUTPUT**
- Test value input is disabled while active
- Click **STOP TEST OUTPUT** → Returns to weight-based output

### API Calls

| Action | Endpoint | Method | Body |
|--------|----------|--------|------|
| Arm/Disarm | `/api/output/arm` | POST | `{armed: true/false}` |
| Save Config | `/api/output/config` | POST | FormData |
| Test Output | `/api/output/test` | POST | `{action: "start"/"stop", value: 5.0}` |
| Calibrate | `/api/output/calibrate` | POST | `{type, channel, value, point}` |
| Reset Cal | `/api/output/calibrate/reset` | POST | `{type, channel}` |
| Add Profile | `/plc-profile/add` | POST | FormData |
| Delete Profile | `/api/plc-profile/delete/<id>` | POST | - |

---

## Settings Page

**URL:** `/settings`  
**Template:** `templates/settings.html`  
**Routes:** `routes.settings_get()`, `routes.settings_post()`

### Purpose

The Settings page consolidates the previously hidden settings concepts into a single technician-facing page with:

- Quick Setup at the top (range, PLC output basics, excitation monitoring with enable/disable toggle)
- Job Target Mode tab (webhook trigger behavior, one-point trigger calibration)
- Tabs for signal filtering, zero behavior, output behavior, alarms, DAQ channels, detection, timing, logging, advanced, and system
- Plain-language helper text on each setting (“what it does” + “what happens if you increase/decrease it”)

### Tab Overview

| Tab | Contents |
|-----|----------|
| Quick Setup | PLC output mode/channel, excitation monitoring (enable + channel + thresholds). PLC mapping configured via Calibration Hub. |
| Job Target Mode | Configure webhook trigger logic (exact vs early), trigger signal value (dropdown populated from PLC profile points), low signal value, and webhook token. If no PLC profile points exist, a message directs operator to Calibration Hub. |
| Signal Tuning | Kalman/IIR filter, stability detection, **weight display precision** |
| Zero & Scale | Zero tracking and power-up behavior |
| Output Control | Dead band, ramping, auto-arm |
| Alarms & Limits | Overload, underload, weight alarms, fault handling |
| DAQ Channels | Channel enable/disable, roles, gain codes |
| Detection | Dump detection, drift detection |
| Timing | Acquisition loop rate, config refresh, I2C retries |
| Logging | Trend logging interval, retention, what to log |
| Advanced | Watchdog timers, RS485, temperature sensors, LEDs |
| System | Hardware mode (real/sim), maintenance UI toggle |

### Weight Display Precision (New in v2.1)

Located in **Signal Tuning** tab under "Weight Display":

| Setting | Description |
|---------|-------------|
| 0 - Whole pounds | Shows "75 lb" - for rough measurements |
| 1 - One decimal | Shows "75.2 lb" - standard precision (default) |
| 2 - Two decimals | Shows "75.24 lb" - for precision weighing |

### Important Behavior

- The app configuration stored in SQLite can be older than the current code.
- The repository layer now **deep-merges the stored config onto the current defaults**, so new settings appear with safe defaults instead of causing missing-key errors.
- **Emojis removed** (v2.1): All emoji icons replaced with plain text for encoding compatibility.

---

## Config Page (Raw)

**URL:** `/config`  
**Template:** `templates/config.html`  
**Routes:** `routes.config_get()`, `routes.config_post()`

### Current Implementation

Simple JSON textarea editor (unchanged). This page is intended for advanced maintenance use only.

```html
<form method="post" action="/config">
  <textarea name="cfg_json" rows="18">
    {JSON config here}
  </textarea>
  <button type="submit">Save</button>
</form>
```

---

---

## Logs Page

**URL:** `/logs`  
**Template:** `templates/logs.html`  
**Route:** `routes.logs_get()`

Displays recent system events (unchanged).

---

## API Endpoints

### Dashboard APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/snapshot` | GET | Unified JSON snapshot for polling |
| `/api/zero` | POST | Zero the scale |
| `/api/tare` | POST | Tare the scale |
| `/api/tare/clear` | POST | Clear tare offset |

### Calibration APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/calibration/add` | POST | Add calibration point (append-only history) |
| `/api/calibration/delete/<id>` | POST | Delete calibration point |
| `/api/calibration/clear` | POST | Clear all calibration points |

### PLC Output APIs

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/output/arm` | POST | Arm/disarm outputs |
| `/api/output/config` | POST | Save output configuration |
| `/api/output/test` | POST | Start/stop test output |
| `/api/output/calibrate` | POST | Capture calibration point |
| `/api/output/calibrate/reset` | POST | Reset to factory calibration |
| `/api/plc-profile/delete/<id>` | POST | Delete PLC profile point |

### Job Target APIs

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/job/webhook` | POST | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Receive target weight from external system |
| `/api/job/status` | GET | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Check current job target state |
| `/api/job/clear` | POST | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Reset target state back to zero/idle |
| `/api/job/mode` | POST | None | Toggle between Legacy and Target Mode |
| `/api/job/trigger/from-nudge` | POST | API token (`X-API-Key`, `Authorization`, or legacy `X-Scale-Token`) | Capture current nudge value as trigger signal |

**Webhook request example:**
```json
POST /api/job/webhook
Headers: { "X-API-Key": "your-token", "Content-Type": "application/json" }
Body: {
  "event": "job.load_size_updated",
  "jobId": "1703487",
  "machineKey": "PLP6",
  "loadSize": 200.0,
  "idempotencyKey": "1703487:200:6d1c4f60-6ea4-4d0f-9cc9-2a2f5f0e8b2a",
  "timestamp": "2026-02-27T14:38:45.000Z"
}
```

**Webhook response (200):**
```json
{ "success": true, "accepted": true, "action": "activated", "status": { "set_weight": 200.0, "active": true } }
```

**Error codes:** 400 (missing required fields), 401 (invalid token), 409 (mode is legacy), 503 (no token configured or service unavailable).

### Snapshot Response Schema (Updated)

```json
{
  "schema_version": 1,
  "timestamp": "2025-12-18T18:00:00+00:00",
  "system": { ... },
  "boards": { ... },
  "excitation": { ... },
  "weight": {
    "total_lbs": 25.0,
    "raw_lbs": 25.1,
    "stable": true,
    "tare_offset_lbs": 0.0,
    "signal_for_cal": 0.0025,
    "cal_points_used": 3
  },
  "channels": [ ... ],
  "plcOutput": {
    "mode": "0_10V",
    "command": 0.833,
    "units": "V",
    "armed": true,
    "test_mode": false,
    "test_value": 0.0
  },
  "jobControl": {
    "enabled": true,
    "mode": "target_signal_mode",
    "trigger_mode": "exact",
    "pretrigger_lb": 0.0,
    "set_weight": 100.0,
    "active": true,
    "meta": {
      "job_id": "1703487",
      "step_id": null,
      "event_id": "1703487:100:6d1c4f60-6ea4-4d0f-9cc9-2a2f5f0e8b2a",
      "target_weight_lb": 100.0
    }
  },
  "production": { ... },
  "events": []
}
```

---

## Template Structure

### Template Files

| File | Purpose |
|------|---------|
| `base.html` | Base layout with header/nav |
| `dashboard.html` | Live weight, Zero/Tare buttons |
| `hdmi.html` | HDMI operator page (800x480 kiosk) |
| `kiosk.html` | Touch calibration kiosk page |
| `calibration.html` | Calibration point management |
| `plc_profile.html` | PLC output configuration |
| `settings.html` | Technician-friendly settings UI (tabbed) |
| `config.html` | JSON config editor (maintenance) |
| `scale_settings.html` | Legacy hidden settings page (deprecated) |
| `logs.html` | Event log viewer |

---

## CSS Variables

```css
:root {
  --bg: #0d1117;
  --card: #161b22;
  --text: #e6edf3;
  --muted: #7d8590;
  --accent: #61dafb;
  --ok: #2ecc71;
  --warn: #ffcc66;
  --bad: #ff6b6b;
}
```

---

**Document Created:** December 18, 2025  
**Last Updated:** February 12, 2026 (v2.3 - HDMI operator page documentation update)
