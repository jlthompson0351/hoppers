# Wiring and Commissioning

## 1. Safety & Responsibilities
- Wiring must be performed by qualified personnel following local electrical codes.
- Ensure all PLC/panel wiring is de-energized before terminating conductors.
- Treat load-cell wiring as **instrumentation**: keep separated from motor/drive/power wiring.

## 2. Hardware Stack & Wiring (CRITICAL)

### 2.1 Stack Order (Bottom to Top)
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

### 2.2 Power Wiring
1.  **24V DC Source** -> Connect to **Watchdog** Green Connector.
2.  **Daisy Chain** -> Jumper wires from Watchdog 24V -> **MegaIND** 24V Green Connector.
    *   *Note: Watchdog powers the Pi. MegaIND powers itself and the DAQ.*
3.  **USB-C Power:** Connect a USB-C cable from the **Watchdog's USB-C OUT** to the **Raspberry Pi's USB-C Power Port**.
    *   *This is the primary power path for the Pi.*

### 2.3 DIP Switch Settings
*   **Watchdog:** No switches (Address 0x30 fixed).
*   **MegaIND:** All switches **OFF** (Stack Level 0 -> Address 0x50).
*   **DAQ:** All Switches **OFF** (Stack Level 0 -> Address 0x31).

### 2.4 Communications (fixed assumption)
- Both HATs communicate with the Raspberry Pi exclusively over the Pi’s **I2C bus** (I2C port).

### 2.3 Other required hardware
- **SlimPak Ultra**: excitation only to load cells
- **Sequent Super Watchdog HAT**: UPS battery backup + hardware watchdog

## 2.4 Power Architecture (UPS + Watchdog)
- **Primary Supply**: 24VDC (industrial standard).
- **Distribution**:
  - 24V → MegaIND (for analog I/O power)
  - 24V → Super Watchdog (for charging + Pi power)
- **Pi Power**: The **Super Watchdog HAT** MUST provide the 5V power to the Raspberry Pi.
  - **Do NOT** power the Pi via USB-C or MegaIND 5V output when using the Watchdog.
  - This ensures the Watchdog can power-cycle the Pi on lockup and provide UPS ride-through.

## 2.5 I2C requirement (commissioning + runtime)
### Commissioning check (first boot)
On first boot/commissioning, run:

```bash
sudo i2cdetect -y 1
# If command not found: sudo /usr/sbin/i2cdetect -y 1
```

Verify that **three Sequent boards appear** on the I2C bus:
- **Watchdog** (0x30)
- **24b8vin-rpi** (0x31 - Stack 0)
- **megaind-rpi** (0x50 - Stack 0)

### Stack ID / address selection (required to document at commissioning)
Both I/O boards support a **stack ID / I2C address selection** mechanism (board-specific jumpers/DIP/options).
- **DAQ (24b8vin):** Set all DIP switches **OFF** (Stack 0).
- **MegaIND:** Set all DIP switches **OFF** (Stack 0).
- Verify after any change by re-running `i2cdetect -y 1`.

### Sequent CLI tools (commissioning expectation)
These tools are commonly used for board-level verification:
- 24b8vin DAQ: `24b8vin` (from `24b8vin-rpi` repo)
- MegaIND: `megaind` (from `megaind-rpi` repo)
- Watchdog: `wdt` (from Super Watchdog repo)

Recommended practice:
- Run `<tool> -h` and perform a simple read/write test per the vendor manual.

### Address conflicts
If an address conflict occurs (both boards responding at the same address or a collision with another I2C device):
- Check Sequent documentation for any **jumper/DIP/address-select options** on the affected board(s).
- If supported, change one board’s address selection and re-run `i2cdetect -y 1` to confirm the conflict is resolved.
 - Re-test using the Sequent CLI tools above.

### Runtime requirement (software)
The software shall perform an **I2C presence check at startup** and show a clear **FAULT** in the UI if:
- a required board is missing from the I2C bus, or
- an address conflict is detected (or the board cannot be uniquely identified).

**New:** Use the **Dashboard status pills** (DAQ / IO) and **Settings → System** to verify detected boards and configuration.
- Green pill = Board detected and online.
- Red pill = Board missing/offline or address mismatch.

Implementation expectation:
- Do **not** hardcode Sequent addresses; instead use commissioning-recorded addresses/stack IDs and enforce them at startup.

## 3. Load Cell Wiring (Summing Board Configuration)

**Architecture Change (Feb 2026):**
The system now uses a **Load Cell Summing Board** (Junction Box) to combine all load cells into a single signal BEFORE entering the DAQ HAT.

### 3.1 Wiring Diagram
```
[Load Cell 1] --\
[Load Cell 2] --|--> [Summing Board] --(4 wires)--> [DAQ HAT Channel 1]
[Load Cell 3] --|
[Load Cell 4] --/
```

### 3.2 DAQ Connections
Connect the **Summing Board Output** to **DAQ Channel 1**:
- **SIG+** → DAQ CH1 IN+
- **SIG−** → DAQ CH1 IN−
- **EXC+** → SlimPak EXC+ (Pass-through via summing box)
- **EXC−** → SlimPak EXC− (Pass-through via summing box)
- **SHIELD** → Panel Ground

### 3.3 Configuration Impact
- **Enabled Channels:** Enable **Channel 1 ONLY**. Disable Channels 2-8.
- **Gain Code:** Summing boards typically output the average mV/V signal (e.g., 0-30mV). Use **Gain Code 6 (±370mV)** or **7 (±180mV)**.
- **Diagnostics:** Individual corner diagnostics (drift detection) are **NOT POSSIBLE** in this configuration because the signals are summed in hardware.

## 4. Excitation Voltage Measurement (optional but recommended)
Goal: monitor excitation sag without loading the source (enable when wiring is available).
- Wire **SlimPak EXC+ → MegaIND analog input (0–10V IN)**.
- Wire **SlimPak EXC− → MegaIND analog input reference/return**.
- Confirm MegaIND analog input is configured as 0–10V and is high-impedance.
- In software, use **Settings -> Quick Setup -> Enable Excitation Monitoring** to turn this safety path on/off.

Commissioning check:
- With load cells connected and monitoring enabled, verify excitation reads near target (~10V) and is stable.

## 5. DAQ Channel Allocation
- **Current architecture:** summing board output on **DAQ Channel 1 only**.
- Enable Channel 1 and disable Channels 2-8 unless you are explicitly using a non-summing custom build.
- If using a custom multi-channel build, document exact channel-to-load-cell mapping and verify software supports that mode before deployment.

## 6. PLC Analog Output Wiring
The MegaIND board provides analog outputs compatible with PLC analog inputs.

### 6.1 0–10V mode
- MegaIND AO(V)+ → PLC analog input +
- MegaIND AO(V)−/COM → PLC analog input −/COM

### 6.2 4–20mA mode
- MegaIND AO(mA)+ → PLC analog input (mA)+
- MegaIND AO(mA)−/COM → PLC analog input (mA)−/COM

### Grounding
- Follow PLC manufacturer guidance for analog common/reference.
- If PLC input is isolated, treat the loop accordingly.
- Avoid tying analog commons to earth at multiple points.

## 7. Digital Inputs (Operator Buttons)
MegaIND digital inputs may be used for:
- zero/tare request
- calibration accept/next
- alarm acknowledge

Scaffold status:
- UI/button mapping is provisioned as interfaces but detailed behavior is to be implemented during integration.

## 8. Shielding, Grounding, and Noise Control
- Route load-cell signal cables away from VFD outputs, motor leads, contactors, solenoids.
- Terminate shield at **one end** only (typically panel end) unless manufacturer specifies otherwise.
- Use twisted pair for signal.
- Ensure SlimPak excitation wiring is robust and its return reference is consistent with measurement reference.

## 9. Startup Checklist
1. Verify correct stacking order and power supply to Raspberry Pi.
2. Verify SlimPak excitation output voltage and polarity.
3. If excitation monitoring is enabled, verify excitation measurement is wired to MegaIND AI and reading plausible value in UI.
4. Verify each load cell channel reads non-saturated raw mV with minor noise.
5. Verify enabled channels match wiring (for summing build: Channel 1 only).
6. Verify PLC analog output wiring and input configuration (voltage vs current).
7. Verify safe output behavior (force a configured fault; excitation fault test applies only when excitation monitoring is enabled).
8. Run `i2cdetect -y 1` and confirm both Sequent boards appear on the I2C bus (see I2C requirement above).

## 10. Commissioning Procedure (high level)
1. Start system on Pi and verify **I/O LIVE** status in Settings → System tab.
2. Confirm raw mV signals on Dashboard; if excitation monitoring is enabled, confirm excitation status/value as well.
3. Tune filter and stability parameters for the site vibration environment.
4. Perform weight calibration using the current runtime procedure (see `docs/CalibrationProcedure.md` and `docs/CALIBRATION_CURRENT_STATE.md`).
5. Verify proportional output mapping and optional correction workflow for your site before handoff.
6. Verify dump detection and totals accumulation in real process.

---

## 11. Complete Hardware Test & Deployment Runbook

**For a complete step-by-step procedure from fresh Raspberry Pi OS to calibrated production system, see:**

- **`docs/HardwareTestReadiness_TODAY.md`** — Complete runbook (~2.5-3.5 hours)
  - Phase 1: Bootstrap (SSH → Running Dashboard)
  - Phase 2: Hardware Smoke Tests (I2C scan, board detection)
  - Phase 3: Calibration + Real Testing
  - Phase 4: Analog Output Verification
  - Phase 5: Final Checklist

- **`docs/QUICK_START_HARDWARE_TEST.md`** — One-page quick reference

- **`docs/TODAY_SUMMARY.md`** — Executive summary with pre-test checklist

**Automated test scripts** (in `scripts/`):
```bash
# Make scripts executable
bash scripts/setup_test_scripts.sh

# Hardware smoke test
./scripts/test_hardware_basic.sh

# DAQ channel test
./scripts/test_24b8vin_channels.sh

# MegaIND output test
./scripts/test_megaind_output.sh

# Calibration verification
python3 scripts/verify_calibration.py

# Analog output test with logging
python3 scripts/analog_output_test_log.py
```

These automated tests provide:
- ✅ Copy-paste ready commands
- ✅ Pass/fail indicators
- ✅ Interactive verification helpers
- ✅ Systematic test logging
- ✅ Clear troubleshooting steps


