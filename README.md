# Load Cell Scale Transmitter (Raspberry Pi 4B)

Industrial load-cell scale transmitter using a Raspberry Pi 4B with Sequent Microsystems stackable HATs:
- **24b8vin-rpi**: 8x 24-bit differential analog inputs for load-cell mV signals (supports 1-8 active channels, typically 2-4)
- **megaind-rpi**: 14-bit analog output to PLC (0–10V or 4–20mA), digital inputs (operator buttons), and one analog input for excitation monitoring

This is an industrial-grade system designed for robust behavior and automatic recovery. The system **always uses real hardware** - there is no simulated mode. If hardware is unavailable, the UI stays up and the system retries automatically.

## Hardware Stack & Wiring (CRITICAL)

### Stack Order (Bottom to Top)
1.  **Raspberry Pi 4B** (Bottom)
2.  **Watchdog HAT** (Stack 0, Address 0x30)
    *   **Function:** Powers the Pi + UPS Battery Backup.
    *   **Connection:** Sits directly on the Pi.
3.  **ISOLATION LAYER (Modified Header)**
    *   **CRITICAL:** You must use a stacking header with **Pins 2 (5V) and 4 (5V) CUT/REMOVED**.
    *   This prevents the MegaIND (above) from fighting the Watchdog's power supply.
4.  **MegaIND HAT** (Stack 0, Address 0x50)
    *   **Function:** PLC Output (0-10V) + Opto Inputs.
    *   **Connection:** Sits on the modified header.
5.  **DAQ HAT (24b8vin)** (Stack 0, Address 0x31)
    *   **Function:** Reads Load Cell.
    *   **Connection:** Sits on top of MegaIND.

### Power Wiring
1.  **24V DC Source** -> Connect to **Watchdog** Green Connector.
2.  **Daisy Chain** -> Jumper wires from Watchdog 24V -> **MegaIND** 24V Green Connector.
    *   *Note: Watchdog powers the Pi. MegaIND powers itself and the DAQ.*
3.  **USB-C Power:** Connect a USB-C cable from the **Watchdog's USB-C OUT** to the **Raspberry Pi's USB-C Power Port**.
    *   *This is the primary power path for the Pi.*

### DIP Switch Settings
*   **Watchdog:** No switches (Address 0x30 fixed).
*   **MegaIND:** All switches **OFF** (Stack Level 0 -> Address 0x50).
*   **DAQ:** All Switches **OFF** (Stack Level 0 -> Address 0x31).

## Quick start (Raspberry Pi)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.app
```

The system will:
- Attempt to initialize DAQ and MegaIND boards
- Show **I/O LIVE** in Settings when hardware is connected
- Show **I/O OFFLINE** and retry every 5 seconds if hardware is unavailable
- Keep outputs at safe values until hardware comes online

## Quick start (Windows / dev PC)

For development without hardware, you can still run the app - it will show I/O OFFLINE and continuously retry:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.app
```

Then open `http://127.0.0.1:8080`. The UI will be functional but show hardware as offline.

## SSH Access to Pi

**Pi IP:** `172.16.190.25`  
**Username:** `pi`  
**Password:** `depor`

### Using plink (Windows):
```powershell
plink -pw depor pi@172.16.190.25
```

### Using standard SSH:
```bash
ssh pi@172.16.190.25
# Enter password: depor
```

### Deploy files using pscp (Windows):
```powershell
# Copy a single file
pscp -pw depor local_file.py pi@172.16.190.25:/opt/loadcell-transmitter/path/to/file.py

# Restart service after deploying
plink -pw depor pi@172.16.190.25 "sudo systemctl restart loadcell-transmitter"
```

**Note:** The application runs from `/opt/loadcell-transmitter/` on the Pi (not `/home/pi/hoppers/`).

## HDMI Operator Interface (Kiosk Mode)

The system includes a dedicated, touch-optimized operator interface for HDMI-connected displays (e.g., Elecrow 5" 800x480).

- **HDMI Page**: Accessible at `/hdmi`. The layout is tuned for 800x480 with a centered live-weight card, tare/zero metadata lines (`Zero Offset`, `Zero Tracking`, `Zero Updated`), and a right-side totals placeholder panel for future database-backed daily/shift totals.
- **Shift Total Placeholder**: Includes `CLEAR SHIFT TOTAL` as a UI placeholder; backend clearing logic is intentionally not wired yet.
- **Auto-Launch**: The Pi can be configured to auto-launch this interface in full-screen (kiosk) mode at boot.
- **Remote Control**: The main Dashboard includes buttons to `LAUNCH HDMI ON PI` and an emergency `FORCE RELAUNCH HDMI` to recover from stuck browser processes.
- **Desktop Launcher**: A "Scale HDMI" shortcut is created on the Pi desktop for manual one-click launch.

**Detailed docs:** `docs/HDMI_KIOSK_RUNBOOK.md`

## Zero vs Tare (Drift Compensation)

Understanding the difference between ZERO and TARE is critical for accurate weighing:

| Button | What it does | When to use | Fixes drift? |
|--------|--------------|-------------|--------------|
| **ZERO** | Adjusts signal offset to compensate for drift | Scale shows weight when empty | ✅ Yes |
| **TARE** | Subtracts weight offset after calibration | Container on scale | ❌ No |

### How ZERO Works
1. Reads current signal (e.g., 5.85 mV)
2. Looks up calibration zero point (e.g., 5.61 mV = 0 lbs)
3. Calculates drift: `5.85 - 5.61 = 0.24 mV`
4. Stores offset, subtracts it from all future readings
5. Result: `5.85 - 0.24 = 5.61 mV → 0 lbs` ✓

### Zero Tracking (Automatic Drift Compensation)
Enable **Zero Tracking** in Settings to automatically compensate for drift:
- Monitors weight when near zero (±0.5 lbs)
- Slowly adjusts zero offset (0.1 lb/s rate)
- No manual intervention needed!

**Detailed docs:** `docs/ZERO_VS_TARE_FIX.md`, `docs/DRIFT_COMPENSATION_DIAGRAM.md`

## Runtime notes
- The Flask web server runs alongside a background acquisition loop thread.
- All configuration/calibration is stored in **SQLite** (default: `var/data/app.sqlite3`).
- **I/O Status**:
  - **I/O LIVE**: Both DAQ and MegaIND boards are connected and operational.
  - **I/O OFFLINE**: Hardware unavailable - system retries every 5 seconds, outputs held at safe values.
  - Check **Settings → System** tab for detailed board status and last communication timestamps.
- **Dashboard Polling**: The dashboard polls `/api/snapshot` every 500ms for live updates (no page refresh needed).
- **Kalman Filter**: Zero-lag filtering for instant response to weight changes. Configurable via Settings > Signal Tuning.
- **Stability Detection**: STABLE/UNSTABLE indicator - only affects Zero/Tare buttons, NOT weight reading or PLC output.
- **Output Stability**: 14-bit DAC provides 0.00061V resolution (0.015 lb at 100 lb/volt). Deadband filtering prevents output jitter to PLC.

## Directory layout
- `src/app/`: Flask UI (server-rendered templates + API endpoints)
- `src/core/`: filtering, stability detection, zeroing helpers, and zero-tracking logic
- `src/hw/`: hardware interfaces + simulated hardware + Sequent stubs
- `src/db/`: SQLite schema/migrations/repositories
- `src/services/`: acquisition loop, output writer, shared state
- `docs/`: engineering documents
- `scripts/`: run/export helpers
- `systemd/`: service unit example

## Commissioning & calibration

### Quick Start (Fresh Pi → Production)
**For complete hardware test and deployment:**
- **`docs/TODAY_SUMMARY.md`** — Executive summary and checklist
- **`docs/HardwareTestReadiness_TODAY.md`** — Complete step-by-step runbook (~2.5-3.5 hours)
- **`docs/QUICK_START_HARDWARE_TEST.md`** — One-page quick reference

**Automated test scripts** (in `scripts/`):
- `test_hardware_basic.sh` — I2C scan + board detection
- `test_24b8vin_channels.sh` — Read all DAQ channels
- `test_megaind_output.sh` — Voltage sweep test
- `verify_calibration.py` — Interactive calibration verification
- `analog_output_test_log.py` — Output test with pass/fail report

### Detailed Procedures
- `docs/WiringAndCommissioning.md` — Hardware wiring and I2C setup
- `docs/CalibrationProcedure.md` — Operator calibration procedure (current runtime behavior)
- `docs/CALIBRATION_CURRENT_STATE.md` — Code-backed calibration behavior and hardening direction
- `docs/TestPlan.md` — Comprehensive test plan

## Calibration Hub & Hand-in-Hand Mapping
The system features a unified **Calibration Hub** for both weight and PLC output:
- **Weight Calibration (current runtime)**: Single-point or two-point linear conversion from signal mV to lb.
- **Hand-in-Hand PLC Mapping**: Interactive "Live Match" nudge slider to link weight directly to V/mA.
- **Visual Monitor**: Real-time scale capacity bar (0-100%).
- **Multi-Load Cell Support**: Automatic signal summing from multiple load cells (typically 2-4 per hopper).

### Load Cell Channel Configuration
Configure which DAQ channels have load cells in **Settings → DAQ Channels**:
- Enable only channels with actual load cells connected
- Unused channels may show "ghost signals" due to floating inputs - this is normal for high-impedance ADCs
- Disable unused channels to prevent ghost signals from affecting weight readings
- System automatically sums signals from all enabled load cell channels

## Settings & Maintenance
The **Settings** page provides centralized control for:
- Hardware port mapping (AO1-4, Mode selection).
- Conflict detection (Red warnings for pin double-booking).
- Advanced tools (Ramping/Smoothing, Safe Fallback Values).
- Internal board calibration (2-point precision CLI tool).

## I2C requirement (commissioning + runtime)
### Commissioning check (first boot)
Run on the Raspberry Pi:

```bash
i2cdetect -y 1
```

Confirm **three Sequent boards** (MegaIND, 24b8vin, Watchdog) appear on the I2C bus.

**New:** The application now performs automatic **Board Discovery**:
- Visit **Scale Settings** > **I2C Hardware Discovery** to see detected boards and addresses.
- The **Dashboard** "System Status" card shows "Boards Online: X/Y".

### Hardware Config
- **Stack IDs**: Record the selected jumper/DIP settings for MegaIND and 24b8vin.
- **Power**: Ensure 24V feeds both the MegaIND and Super Watchdog, but **only the Watchdog** powers the Pi (5V).
- **CLI Tools**:
  - `24b8vin` (DAQ)
  - `megaind` (Industrial IO)
  - `wdt` (Watchdog)

### Software behavior requirement
When running on real hardware, the software must perform an **I2C presence check at startup** and surface a clear **FAULT** in the UI if a board is missing or an address conflict is detected.

## Application Modes

### Static Weighing (default)
For stable hoppers where weight doesn't change rapidly.
- Kalman Process Noise (Q): 1.0
- Kalman Measurement Noise (R): 50
- Stability Window: 25 samples

### Dynamic Filling (conveyor dropping parts into hopper)
For hoppers where weight changes continuously.
- Kalman Process Noise (Q): 10.0
- Kalman Measurement Noise (R): 25
- Stability Window: 25 samples

**Important:** During dynamic filling, the scale will show UNSTABLE - this is NORMAL and does NOT affect:
- Weight reading (always updates at ~17Hz)
- PLC output (always sent)

UNSTABLE only blocks Zero/Tare operations.

## PLC Output Verification

For verifying PLC analog output, see **`docs/PLC_OUTPUT_VERIFICATION.md`** which covers:
- Quick UI test mode procedure
- Full weight-to-output system test
- Automated test scripts
- Manual CLI commands for low-level testing
- PLC profile correction workflow

### PLC Signal Quality & Stability
The MegaIND board provides industrial-grade analog output suitable for Allen-Bradley and other PLCs:

**Hardware Specifications:**
- **14-bit DAC**: 0.00061V resolution per step (0-10V range)
- **Precision**: ±0.015 lb at 100 lb/volt scaling
- **Update rate**: ~20 Hz (synchronized with weight acquisition loop)

**Signal Conditioning:**
- **Deadband filter**: Prevents output changes smaller than configured threshold (default 0.5 lb)
- **Kalman filtering**: Zero-lag smoothing eliminates noise without delay
- **Ramp limiting** (optional): Slew rate control for gradual output changes

**Bench Testing Before Field Deployment:**
Before connecting to your PLC, verify signal stability:
1. Configure proper load cell channels in Settings → DAQ Channels
2. Enable output in Settings → Output Control (ARM OUTPUTS)
3. Monitor voltage with multimeter on MegaIND analog output terminals
4. Expected stability: <0.001V variation under stable load
5. Weight changes >0.5 lb will update output immediately

**Common PLC Scaling:**
- 0-250 lb → 0-10V (25 lb/volt)
- 0-500 lb → 0-10V (50 lb/volt)  
- 0-1000 lb → 0-10V (100 lb/volt)

Configure range in **Settings → Weight Range** to match your hopper capacity and PLC expectations.



## 🤖 AI Agent Workflow
This project is equipped with a **Multi-Agent Swarm** powered by Cursor.

### How to Start
To activate the swarm, simply tell the AI:
> "Read `.cursor/AGENTS.md` and start the Orchestrator workflow."

### The Team
-   **Agent-1 (Opus):** Senior Architect (Planning & Hard Problems).
-   **Agent-2 (Sonnet):** Lead Developer (Coding & Execution).
-   **Agent-3 (Sonnet):** Developer (Parallel Work).
-   **Agent-4 (Gemini):** Context Specialist (Large Refactors).

### The Knowledge Base
Skills are stored in `.cursor/skills-store/`. The Orchestrator will automatically "equip" agents with the right skills (React, Node, Supabase, etc.) for the job.
