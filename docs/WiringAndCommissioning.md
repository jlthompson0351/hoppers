# Wiring and Commissioning

## 1. Safety & Responsibilities
- Wiring must be performed by qualified personnel following local electrical codes.
- Ensure all PLC/panel wiring is de-energized before terminating conductors.
- Treat load-cell wiring as **instrumentation**: keep separated from motor/drive/power wiring.

## 2. Hardware Stack
### 2.1 Physical stack order (fixed assumption)
- Raspberry Pi 4B
- Sequent **megaind-rpi** (Industrial Automation HAT) mounted directly on the Pi (**bottom**, closest to Pi)
- Sequent **24b8vin-rpi** (8x 24-bit Analog Inputs DAQ HAT) stacked on top of the MegaIND (**top**)

### 2.2 Communications (fixed assumption)
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
- **megaind-rpi** (typically 0x50 + stack_id)
- **24b8vin-rpi** (typically 0x31 + stack_id)
- **Super Watchdog** (typically 0x30)

### Stack ID / address selection (required to document at commissioning)
Both I/O boards support a **stack ID / I2C address selection** mechanism (board-specific jumpers/DIP/options).
- During commissioning, record:
  - MegaIND stack ID and observed I2C address
  - 24b8vin stack ID and observed I2C address
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

## 3. Load Cell Wiring (4-wire full bridge; ~3 mV/V typical)
Typical 4-wire colors vary by manufacturer; verify documentation.
- **EXC+** (Excitation +) → SlimPak EXC+
- **EXC−** (Excitation −) → SlimPak EXC−
- **SIG+** (Signal +) → DAQ differential input +
- **SIG−** (Signal −) → DAQ differential input −

### Notes
- Use shielded, twisted-pair cable for SIG+/SIG−.
- Prefer star-grounding at the control panel instrument ground, avoid ground loops.

## 4. Excitation Voltage Measurement (required)
Goal: continuously monitor excitation sag without loading the source.
- Wire **SlimPak EXC+ → MegaIND analog input (0–10V IN)**.
- Wire **SlimPak EXC− → MegaIND analog input reference/return**.
- Confirm MegaIND analog input is configured as 0–10V and is high-impedance.

Commissioning check:
- With load cells connected, verify excitation reads near target (~10V) and is stable.

## 5. DAQ Channel Allocation
- One DAQ channel per load cell.
- System supports enabling/disabling any of the 8 channels; **disabled channels must be excluded** from:
  - totals
  - drift checks
  - stability checks
  - alarms and fault logic based on load-cell signals

Recommendation:
- Assign contiguous channels (e.g., CH0–CH3) for simplicity.
- Document channel-to-load-cell physical location (front-left, etc.).

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
3. Verify excitation measurement wired to MegaIND AI and reading plausible value in UI.
4. Verify each load cell channel reads non-saturated raw mV with minor noise.
5. Verify enabled channels match installed load cells (3 or 4 active).
6. Verify PLC analog output wiring and input configuration (voltage vs current).
7. Verify safe output behavior (force fault and confirm PLC reads 0V or 4mA).
8. Run `i2cdetect -y 1` and confirm both Sequent boards appear on the I2C bus (see I2C requirement above).

## 10. Commissioning Procedure (high level)
1. Start system on Pi and verify **I/O LIVE** status in Settings → System tab.
2. Confirm excitation monitoring and raw mV signals on Dashboard.
3. Tune filter and stability parameters for the site vibration environment.
4. Perform multi-point calibration (see `docs/CalibrationProcedure.md`).
5. Create PLC profile mapping curve if PLC scaling is unknown/legacy.
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


