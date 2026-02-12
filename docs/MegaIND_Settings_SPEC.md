# MegaIND Settings Page Specification
**Document Version:** 1.1  
**Date:** December 18, 2025 (Updated)  
**Purpose:** Define accurate MegaIND hardware capabilities and settings page spec for maintenance technicians

---

## 🎯 LIVE DASHBOARD: http://172.16.190.25:8080

---

## ✅ DEPLOYED & RUNNING (December 18, 2025)

| Property | Value |
|----------|-------|
| **Dashboard** | http://172.16.190.25:8080 |
| **Status** | ✅ Online, connected to Flask service |
| **I2C Base Address** | **0x50** (stack 0) |
| **Address Range** | 0x50–0x57 (stack 0–7) |
| **Firmware Version** | 04.08 |
| **CPU Temperature** | 41°C |
| **Power Source** | 24.13V |
| **Pi Voltage** | 5.23V |
| **CLI Tool** | `megaind` (installed at `/usr/local/bin/megaind`) |
| **Python Module** | `megaind` (import as `import megaind`) |

---

## SECTION A — MegaIND Capabilities (Truth Table)

### Hardware Stack Configuration
- **Physical Stack Order:** Raspberry Pi → MegaIND (bottom, closest to Pi) → 24b8vin (top)
- **I2C Bus:** Both boards share I2C bus 1 (`/dev/i2c-1`)
- **I2C Base Address:** **0x50** (verified December 18, 2025)
- **Stack Level / ID:** 0..7 (eight-level stackable via address jumpers)
- **No I2C Conflict:** MegaIND (0x50–0x57) and 24b8vin (0x31–0x38) use different address ranges

### Subsystem Capabilities

| Subsystem | Channels | Range/Type | Software Configurable | Hardware Jumper Required | Notes |
|-----------|----------|------------|----------------------|-------------------------|--------|
| **Analog Inputs (Voltage)** | 4 | 0–10V **OR** ±10V | NO | YES | Range selection is PHYSICAL JUMPER per channel. Software must read via correct function (get0_10In vs getpm10In) |
| **Analog Inputs (Current)** | 4 | 4–20mA | N/A | NO | Direct read via get4_20In |
| **Analog Outputs (Voltage)** | 4 | 0–10V | YES (0..10V value) | NO | Writable via set0_10Out, readable via get0_10Out |
| **Analog Outputs (Current)** | 4 | 4–20mA | YES (4..20mA value) | NO | Writable via set4_20Out, readable via get4_20Out |
| **Opto-isolated Digital Inputs** | 4 | Binary (0/1) | N/A | NO | Read via getOptoCh or getOpto |
| **Opto Input Counters** | 4 (one per opto) | 0..65535 counts | YES (enable/disable edges) | NO | Rising/falling edge counting configurable independently |
| **Opto Input Frequency Read** | 4 (one per opto) | Hz | N/A | NO | Read via getOptoFrequency |
| **Open-drain Outputs** | 4 | On/Off + PWM | YES (0..100% duty) | NO | PWM duty via setOdPWM/getOdPWM. PWM freq 10..6400Hz |
| **LEDs (onboard)** | 4 | On/Off | YES | NO | Control via setLed/setLedAll/getLed |
| **Watchdog Timer** | 1 | Period: 10..65000s | YES | NO | Period=65000 disables. Includes init period, off period, reset counter |
| **RS485 / MODBUS** | 1 | Mode: Disabled / Modbus RTU Slave | YES (mode, baud, parity, stop, addr) | PARTIAL | Physical jumpers may be required for bus control; software command to release/control bus |
| **RTC (Real-Time Clock)** | 1 | Date/Time | YES | NO | Accessible via rtcGet/rtcSet in Python API |
| **One-Wire Bus (OWB)** | 1 | Up to 16 DS18B20 temp sensors | YES (scan, read) | NO | Accessible via owbScan, owbGetSensorNo, owbGetTemp, owbGetRomCode |
| **Diagnostics** | N/A | Power supply voltage, Raspberry Pi voltage, CPU temp, Firmware version | READ-ONLY | NO | getFwVer, getPowerVolt, getRaspVolt, getCpuTemp |

### IMPORTANT CORRECTIONS
- **MegaIND does NOT have 8 load cell inputs.** That is the 24b8vin HAT (separate board, top of stack).
- **Analog input range (0–10V vs ±10V) is selected by PHYSICAL JUMPERS PER CHANNEL**, not software.
- The UI **must** indicate "Physical Jumper Setting" when displaying input range type.

---

## SECTION B — "Settings → MegaIND" Page Spec (Consolidated)

### Navigation
- **Main navigation:** Use the consolidated **Settings** page (`/settings`).
- **Sub-sections within Settings:**
  - **24b8vin** (load cell DAQ board)
  - **MegaIND** (industrial I/O board) — THIS SPEC

### Page Purpose
- Maintenance technicians (not operators) configure, test, and diagnose the MegaIND board
- Allow live monitoring of all I/O
- Support output testing with safety interlocks ("ARM OUTPUTS" toggle)
- Support calibration and factory reset
- Log all configuration changes with timestamp, user, and old/new values

### Page Layout (Cards/Sections)

---

#### 1. Board Identity & Connectivity

**Purpose:** Verify MegaIND board is online and identify hardware/firmware.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Stack Level | Dropdown (0..7) | Select MegaIND stack level (ID) | Corresponds to physical address jumpers on board |
| Board Online | Indicator (green/red) | I2C detect / connectivity status | Auto-refresh every 2s. Red if board not detected |
| Firmware Version | Read-only text | Firmware version (e.g., "1.1.8") | Populated via `getFwVer(stack)` |
| Power Supply Voltage | Read-only text + units | External power supply voltage (V) | Populated via `getPowerVolt(stack)`. Update every 5s |
| Raspberry Pi Voltage | Read-only text + units | Pi 5V rail voltage (V) | Populated via `getRaspVolt(stack)`. Update every 5s. Warn if <4.75V |
| CPU Temperature | Read-only text + units | Pi CPU temp (°C) | Populated via `getCpuTemp(stack)`. Update every 5s. Warn if >70°C |

**Safety/Warning:**  
- Display warning banner if Board Online = red: "MegaIND board not detected at stack level X. Check I2C connection and address jumpers."

---

#### 2. Analog Inputs

**Purpose:** Monitor analog input channels (voltage and current).

##### 2A. Voltage Inputs (0–10V / ±10V)

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Channel 1..4 Label | Editable text | User-assigned label (e.g., "Excitation Monitor") | Stored in config DB |
| Channel 1..4 Range | Read-only badge | "0–10V" or "±10V" | **PHYSICAL JUMPER SETTING — NOT SOFTWARE CONFIGURABLE.** Display prominent badge. |
| Channel 1..4 Live Value | Read-only text + units | Current reading (V) | Update every 1s. Use `get0_10In(stack, ch)` or `getpm10In(stack, ch)` based on jumper setting |
| Channel 1..4 Enable | Checkbox | Enable/disable reading | If disabled, do not poll or display value |

**Safety/Warning:**  
- Display persistent banner: "⚠️ Input range (0–10V vs ±10V) is set by PHYSICAL JUMPERS on the board. Verify jumper positions match your wiring before use."
- If user attempts to "change" range in UI, display modal: "Range cannot be changed in software. Adjust physical jumpers on MegaIND board."

##### 2B. Current Inputs (4–20mA)

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Channel 1..4 Label | Editable text | User-assigned label | Stored in config DB |
| Channel 1..4 Live Value | Read-only text + units | Current reading (mA) | Update every 1s via `get4_20In(stack, ch)` |
| Channel 1..4 Enable | Checkbox | Enable/disable reading | If disabled, do not poll or display value |

---

#### 3. Analog Outputs

**Purpose:** Control and test analog output channels (voltage and current). **SAFETY-CRITICAL SECTION.**

**Global Safety Interlock:**

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| **ARM OUTPUTS** | Toggle (**ON by default** as of 2026-02-12) | Master enable for analog output writes | Defaults to ARMED for automatic operation. Display in large red/green toggle. Log every state change. Manual disarm available for maintenance. |

**Safety/Warning:**  
- Display persistent banner: "⚠️ DANGER: Analog outputs control external equipment. Verify all wiring and equipment state before enabling outputs."
- When ARM OUTPUTS = OFF, display: "Outputs are DISARMED. No writes will be sent to board."
- When ARM OUTPUTS = ON, display: "Outputs are ARMED. Changes will immediately affect connected equipment."

##### 3A. Voltage Outputs (0–10V)

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Channel 1..4 Label | Editable text | User-assigned label (e.g., "PLC Output 0–10V") | Stored in config DB |
| Channel 1..4 Set Value | Number input (0..10) + units (V) | Commanded output voltage | Only writable if ARM OUTPUTS = ON. Write via `set0_10Out(stack, ch, value)` |
| Channel 1..4 Readback | Read-only text + units | Actual output value read from board (V) | Update every 2s via `get0_10Out(stack, ch)` |
| Channel 1..4 Test Output | Toggle button | Start/stop test output: output stays at specified value until stopped | Requires ARM OUTPUTS = ON. Confirm via modal. While active, overrides normal output logic. Log start/stop. |

##### 3B. Current Outputs (4–20mA)

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Channel 1..4 Label | Editable text | User-assigned label (e.g., "PLC Output 4–20mA") | Stored in config DB |
| Channel 1..4 Set Value | Number input (4..20) + units (mA) | Commanded output current | Only writable if ARM OUTPUTS = ON. Write via `set4_20Out(stack, ch, value)` |
| Channel 1..4 Readback | Read-only text + units | Actual output value read from board (mA) | Update every 2s via `get4_20Out(stack, ch)` |
| Channel 1..4 Test Output | Toggle button | Start/stop test output: output stays at specified value until stopped | Requires ARM OUTPUTS = ON. Confirm via modal. While active, overrides normal output logic. Log start/stop. |

**Safety/Warning:**  
- Require explicit confirmation modal for any output change: "Set Channel X to Y volts/mA? This will affect connected equipment."
- Log every output change (timestamp, user, channel, old value, new value, reason/context).

---

#### 4. Calibration (MegaIND-level)

**Purpose:** Perform two-point calibration for analog inputs and outputs. Reset to factory calibration if needed. **Note: These advanced tools are located at the bottom of the Settings -> MegaIND tab.**

**Calibration Commands Available (from CLI):**

| Subsystem | Calibrate Command | Reset Command |
|-----------|-------------------|---------------|
| 0–10V Inputs | `megaind <id> uincal <ch> <value>` | `megaind <id> uincalrst <ch>` |
| 4–20mA Inputs | `megaind <id> iincal <ch> <value>` | `megaind <id> iincalrst <ch>` |
| 0–10V Outputs | `megaind <id> uoutcal <ch> <value>` | `megaind <id> uoutcalrst <ch>` |
| 4–20mA Outputs | `megaind <id> ioutcal <ch> <value>` | `megaind <id> ioutcalrst <ch>` |

**Two-Point Calibration Procedure (per channel):**

1. **Select Channel & Subsystem** (e.g., "0–10V Input, Channel 2")
2. **Point 1:**
   - Apply known reference value (e.g., 0.5V) to channel via precision source
   - Enter reference value in UI
   - Click "Capture Point 1"
   - UI calls: `megaind <stack> uincal <ch> <value>`
3. **Point 2:**
   - Apply second known reference value (must be ≥5V apart for voltage, ≥10mA apart for current)
   - Enter reference value in UI
   - Click "Capture Point 2"
   - UI calls: `megaind <stack> uincal <ch> <value>` again
4. **Validation:**
   - After two points, calibration is active
   - Display confirmation: "Calibration complete. Test with known reference."
5. **Reset to Factory:**
   - Button: "Reset Channel X to Factory Calibration"
   - Confirm via modal
   - Call: `megaind <stack> uincalrst <ch>`

**UI Fields:**

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Subsystem | Dropdown | 0–10V In / 4–20mA In / 0–10V Out / 4–20mA Out | Selects which I/O type to calibrate |
| Channel | Dropdown (1..4) | Channel number | |
| Point 1 Reference Value | Number input | Known reference value for point 1 | Units auto-populate based on subsystem (V or mA) |
| Capture Point 1 | Button | Capture calibration point 1 | Calls appropriate `*cal` command |
| Point 2 Reference Value | Number input | Known reference value for point 2 | Must be ≥5V (voltage) or ≥10mA (current) from point 1 |
| Capture Point 2 | Button | Capture calibration point 2 | Calls appropriate `*cal` command again |
| Calibration Status | Read-only text | "Not calibrated" / "Point 1 captured" / "Calibrated" | Track state per channel |
| Reset to Factory | Button | Reset calibration for selected channel | Calls appropriate `*calrst` command. Confirm via modal. |

**Safety/Warning:**  
- Display guidance: "For accurate calibration, use a precision reference source. Voltage calibration requires two points ≥5V apart. Current calibration requires two points ≥10mA apart."
- Log all calibration events (timestamp, user, channel, subsystem, point 1/2 values, or reset action).

---

#### 5. Digital I/O

**Purpose:** Monitor opto-isolated inputs and control open-drain outputs.

##### 5A. Opto-Isolated Inputs

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Channel 1..4 Label | Editable text | User-assigned label | Stored in config DB |
| Channel 1..4 State | Indicator (0/1, off/on) | Live digital input state | Update every 500ms via `getOptoCh(stack, ch)` |
| Channel 1..4 Counter | Read-only number | Edge counter value (0..65535) | Update every 2s via `getOptoCount(stack, ch)` |
| Channel 1..4 Reset Counter | Button | Reset counter to 0 | Call `rstOptoCount(stack, ch)`. Log event. |
| Channel 1..4 Count Rising Edges | Checkbox | Enable counting on rising edges | Set via `setOptoRisingCountEnable(stack, ch, state)`. Log change. |
| Channel 1..4 Count Falling Edges | Checkbox | Enable counting on falling edges | Set via `setOptoFallingCountEnable(stack, ch, state)`. Log change. |
| Channel 1..4 Frequency | Read-only text + units (Hz) | Measured frequency of input signal | Update every 2s via `getOptoFrequency(stack, ch)` |

##### 5B. Open-Drain Outputs

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Channel 1..4 Label | Editable text | User-assigned label | Stored in config DB |
| Channel 1..4 State | Toggle (On/Off) | Digital output state | Requires ARM OUTPUTS = ON. Set via `setOdPWM(stack, ch, 0)` for off, `setOdPWM(stack, ch, 100)` for on |
| Channel 1..4 PWM Duty | Slider (0..100%) | PWM duty cycle | Requires ARM OUTPUTS = ON. Set via `setOdPWM(stack, ch, value)`. Readback via `getOdPWM(stack, ch)` |
| Channel 1..4 PWM Frequency | Number input (10..6400 Hz) | PWM frequency | Set via CLI `megaind <id> odfwr <ch> <freq>` (not in Python API; call via subprocess) |

**Safety/Warning:**  
- Open-drain outputs require ARM OUTPUTS = ON to write.
- Display warning: "Open-drain outputs may control motors, valves, or other equipment. Verify wiring before enabling."

---

#### 6. Watchdog Timer

**Purpose:** Configure MegaIND watchdog for Raspberry Pi power cycling and monitor reset history.

**Default Behavior (from docs):**  
- Default period: **120 seconds** (if not explicitly set)
- If watchdog is not reloaded within the period, the Pi is power-cycled
- To **disable** watchdog: set period = 65000

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Watchdog Enabled | Toggle (On/Off) | Enable or disable watchdog | On = set period via `wdtSetPeriod(stack, val)`<br>Off = set period = 65000 |
| Watchdog Period | Number input (10..64999 s) | Period in seconds; Pi must reload within this interval | Set via `wdtSetPeriod(stack, val)`. Get via `wdtGetPeriod(stack)` |
| Default Period (Boot) | Number input (10..64999 s) | Period loaded after Pi power cycle; must be long enough for boot + app start | Set via `wdtSetDefaultPeriod(stack, val)`. Get via `wdtGetDefaultPeriod(stack)` |
| Power-Off Interval | Number input (10..4147200 s, max ~48 days) | How long to keep Pi powered off after watchdog timeout | Set via `wdtSetOffInterval(stack, val)`. Get via `wdtGetOffInterval(stack)` |
| Reset Count | Read-only number | Number of Pi re-powers performed by watchdog | Get via `wdtGetResetCount(stack)`. Clear via button below. |
| Clear Reset Count | Button | Reset the reset count to 0 | Call via CLI `megaind <id> wdtrcclr`. Confirm via modal. Log event. |
| Reload Watchdog Now | Button | Manually reload (pet) the watchdog timer | Call `wdtReload(stack)`. This also enables the watchdog if disabled. |

**Behavior Notes:**  
- Calling `wdtReload(stack)` enables the watchdog if currently disabled.
- If a background service is managing the watchdog (e.g., systemd watchdog), manual reload may interfere. Display warning if detected.

**Safety/Warning:**  
- Display: "⚠️ Watchdog will power-cycle the Raspberry Pi if not reloaded within the period. Ensure your application reloads the watchdog regularly."
- Log all watchdog config changes.

---

#### 7. RS485 / MODBUS

**Purpose:** Configure RS485/MODBUS mode for external PLC or SCADA communication.

**Mode Options (from source code):**

| Mode | Value | Description |
|------|-------|-------------|
| Disabled | 0 | RS485 port disabled |
| Modbus RTU Slave | 1 | MegaIND acts as Modbus RTU slave device on RS485 bus |

**Configuration Fields:**

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| RS485 Mode | Dropdown | Disabled / Modbus RTU Slave | Default: Disabled |
| Baudrate | Number input | 1200..920600 bps | Only if mode = Modbus RTU. Default: 9600 |
| Stop Bits | Dropdown (1, 2) | Stop bits | Only if mode = Modbus RTU. Default: 1 |
| Parity | Dropdown | None / Even / Odd | Only if mode = Modbus RTU. Default: None |
| Modbus Slave Address Offset | Number input (1..255) | Slave address = Stack Level + Offset | Only if mode = Modbus RTU. Default: 1 |
| Calculated Slave Address | Read-only text | Stack Level + Address Offset | Auto-calculate. Example: Stack 1 + Offset 1 = Address 2 |
| Current Settings | Read-only text | Display current RS485 config read from board | Get via CLI `megaind <id> rs485rd` or via I2C read |
| Apply Settings | Button | Write RS485 config to board | Call CLI `megaind <id> rs485wr <mode> <baud> <stop> <parity> <addr>`. Confirm via modal. Log event. |

**Physical Jumper Requirement (from PDF docs):**  
- **IMPORTANT:** Some MegaIND revisions require **PHYSICAL JUMPERS** to enable RS485 mode or to "release bus control" to the Raspberry Pi.
- Display persistent banner: "⚠️ RS485 mode may require PHYSICAL JUMPERS on the board. Consult MegaIND user guide for your board revision."
- If software command to "release bus" or "control bus" exists in CLI, expose it here as a button.

**Safety/Warning:**  
- Display: "Changing RS485 settings will affect communication with external devices. Coordinate with control system before changing."
- Log all RS485 config changes.

---

#### 8. LEDs (Onboard Indicators)

**Purpose:** Control the 4 onboard LEDs for visual diagnostics.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| LED 1..4 State | Toggle (On/Off) | Control individual LED | Set via `setLed(stack, ch, val)`. Get via `getLed(stack, ch)` |
| Set All LEDs | Button | Batch control: set all 4 LEDs to a pattern | Modal to enter 4-bit pattern (0..15). Set via `setLedAll(stack, val)` |

**Notes:**  
- LEDs are for diagnostics/indication only. No safety implications.
- Log LED changes for diagnostics.

---

#### 9. RTC (Real-Time Clock)

**Purpose:** Set and read the onboard hardware RTC.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Current RTC Date/Time | Read-only text | Display current RTC value | Get via `rtcGet(stack)` → returns (year, month, day, hour, minute, second) |
| Sync RTC to System | Button | Set RTC to Raspberry Pi system time | Get system time, call `rtcSet(stack, y, mo, d, h, m, s)` |
| Set RTC Manually | Date/Time picker + button | Manually set RTC to specified date/time | Call `rtcSet(stack, y, mo, d, h, m, s)`. Confirm via modal. |

**Notes:**  
- RTC useful for timekeeping if Pi is offline or NTP unavailable.
- Log RTC changes.

---

#### 10. One-Wire Bus (Temperature Sensors)

**Purpose:** Scan and read up to 16 DS18B20 temperature sensors on the one-wire bus.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| Scan Bus | Button | Scan for connected DS18B20 sensors | Call `owbScan(stack)`, then `owbGetSensorNo(stack)` to get count |
| Sensor Count | Read-only number | Number of sensors detected | Update after scan |
| Sensor 1..16 ROM Code | Read-only text | 64-bit unique ROM code | Display as hex. Get via `owbGetRomCode(stack, sensor)` |
| Sensor 1..16 Temperature | Read-only text + units (°C) | Live temperature reading | Update every 5s via `owbGetTemp(stack, sensor)` |
| Sensor 1..16 Label | Editable text | User-assigned label | Stored in config DB |

**Notes:**  
- Sensors are auto-detected. No configuration required.
- Useful for monitoring ambient temperature or equipment temperature.

---

#### 11. Logging Hooks (for Future Implementation)

**Purpose:** Define what should be logged when settings change.

**Log Event Schema (minimum fields):**

| Field | Description |
|-------|-------------|
| Timestamp | ISO 8601 timestamp |
| User | Username or "system" |
| Event Type | "config_change", "calibration", "output_change", "watchdog_reload", etc. |
| Board Type | "megaind" |
| Stack Level | 0..7 |
| Subsystem | "analog_input", "analog_output", "digital_io", "watchdog", "rs485", etc. |
| Channel | Channel number (if applicable) |
| Old Value | Previous value/state |
| New Value | New value/state |
| Reason / Context | Optional: user-entered reason or auto-generated context |

**Events to Log:**

- ARM OUTPUTS state change
- Any analog output value change
- Calibration point capture or reset
- Watchdog config change or manual reload
- RS485 config change
- Opto counter reset
- Edge counting enable/disable
- Open-drain output state change
- LED state change
- RTC set
- All errors/exceptions during I2C communication

**UI Integration:**

- Add a "View MegaIND Logs" button that links to the main Logs page, pre-filtered to `board_type = "megaind"`.
- Display recent event count (last 24h) as a badge on the MegaIND settings page.

---

## SECTION C — Backend Call Plan (No Coding Yet)

### Python Library Functions (from `megaind` module)

#### Diagnostics
- **Get firmware version:** `megaind.getFwVer(stack)`
- **Get power supply voltage:** `megaind.getPowerVolt(stack)` → float (volts)
- **Get Raspberry Pi voltage:** `megaind.getRaspVolt(stack)` → float (volts)
- **Get CPU temperature:** `megaind.getCpuTemp(stack)` → float (°C)

#### Analog Inputs
- **Read 0–10V input:** `megaind.get0_10In(stack, ch)` → float (volts), ch = 1..4
- **Read ±10V input:** `megaind.getpm10In(stack, ch)` → float (volts), ch = 1..4
- **Read 4–20mA input:** `megaind.get4_20In(stack, ch)` → float (mA), ch = 1..4

#### Analog Outputs
- **Read 0–10V output:** `megaind.get0_10Out(stack, ch)` → float (volts), ch = 1..4
- **Set 0–10V output:** `megaind.set0_10Out(stack, ch, value)` → None, value = 0..10V
- **Read 4–20mA output:** `megaind.get4_20Out(stack, ch)` → float (mA), ch = 1..4
- **Set 4–20mA output:** `megaind.set4_20Out(stack, ch, value)` → None, value = 4..20mA

#### Digital Inputs (Opto)
- **Read single opto input:** `megaind.getOptoCh(stack, ch)` → int (0 or 1), ch = 1..4
- **Read all opto inputs:** `megaind.getOpto(stack)` → int (bitmap 0..15)
- **Read opto counter:** `megaind.getOptoCount(stack, ch)` → int (0..65535), ch = 1..4
- **Reset opto counter:** `megaind.rstOptoCount(stack, ch)` → None
- **Get rising edge counting enable:** `megaind.getOptoRisingCountEnable(stack, ch)` → int (0 or 1)
- **Set rising edge counting enable:** `megaind.setOptoRisingCountEnable(stack, ch, state)` → None, state = 0 or 1
- **Get falling edge counting enable:** `megaind.getOptoFallingCountEnable(stack, ch)` → int (0 or 1)
- **Set falling edge counting enable:** `megaind.setOptoFallingCountEnable(stack, ch, state)` → None, state = 0 or 1
- **Read opto input frequency:** `megaind.getOptoFrequency(stack, ch)` → float (Hz), ch = 1..4

#### Digital Outputs (Open-Drain)
- **Set PWM duty:** `megaind.setOdPWM(stack, ch, value)` → None, value = 0..100 (%), ch = 1..4
- **Get PWM duty:** `megaind.getOdPWM(stack, ch)` → int (0..100 %), ch = 1..4
- **Set PWM frequency:** NOT IN PYTHON API; must call CLI: `megaind <id> odfwr <ch> <freq>`
- **Get PWM frequency:** NOT IN PYTHON API; must call CLI: `megaind <id> odfrd <ch>`

#### LEDs
- **Set single LED:** `megaind.setLed(stack, ch, val)` → None, ch = 1..4, val = 0 or 1
- **Set all LEDs:** `megaind.setLedAll(stack, val)` → None, val = bitmap 0..15
- **Get single LED:** `megaind.getLed(stack, ch)` → int (0 or 1), ch = 1..4

#### Watchdog
- **Reload watchdog:** `megaind.wdtReload(stack)` → None (also enables watchdog if disabled)
- **Get watchdog period:** `megaind.wdtGetPeriod(stack)` → int (seconds)
- **Set watchdog period:** `megaind.wdtSetPeriod(stack, val)` → None, val = 10..65000 (65000 = disable)
- **Get default period:** `megaind.wdtGetDefaultPeriod(stack)` → int (seconds)
- **Set default period:** `megaind.wdtSetDefaultPeriod(stack, val)` → None, val = 10..64999
- **Get off interval:** `megaind.wdtGetOffInterval(stack)` → int (seconds)
- **Set off interval:** `megaind.wdtSetOffInterval(stack, val)` → None, val = 10..4147200
- **Get reset count:** `megaind.wdtGetResetCount(stack)` → int (0..65535)
- **Clear reset count:** NOT IN PYTHON API; must call CLI: `megaind <id> wdtrcclr`

#### RTC
- **Get RTC date/time:** `megaind.rtcGet(stack)` → tuple (year, month, day, hour, minute, second)
- **Set RTC date/time:** `megaind.rtcSet(stack, y, mo, d, h, m, s)` → None

#### One-Wire Bus (Temperature Sensors)
- **Scan bus:** `megaind.owbScan(stack)` → None
- **Get sensor count:** `megaind.owbGetSensorNo(stack)` → int (0..16)
- **Get temperature:** `megaind.owbGetTemp(stack, sensor)` → float (°C), sensor = 1..16
- **Get ROM code:** `megaind.owbGetRomCode(stack, sensor)` → bytes (8 bytes)

#### RS485 / MODBUS
- **Read RS485 config:** NOT IN PYTHON API; must call CLI: `megaind <id> rs485rd`
- **Write RS485 config:** NOT IN PYTHON API; must call CLI: `megaind <id> rs485wr <mode> <baud> <stop> <parity> <addr>`

#### Calibration
**All calibration commands must be called via CLI** (not in Python API):

| Function | CLI Command | Parameters |
|----------|-------------|------------|
| Calibrate 0–10V input | `megaind <id> uincal <ch> <value>` | ch = 1..4, value = volts |
| Reset 0–10V input cal | `megaind <id> uincalrst <ch>` | ch = 1..4 |
| Calibrate 4–20mA input | `megaind <id> iincal <ch> <value>` | ch = 1..4, value = mA |
| Reset 4–20mA input cal | `megaind <id> iincalrst <ch>` | ch = 1..4 |
| Calibrate 0–10V output | `megaind <id> uoutcal <ch> <value>` | ch = 1..4, value = volts |
| Reset 0–10V output cal | `megaind <id> uoutcalrst <ch>` | ch = 1..4 |
| Calibrate 4–20mA output | `megaind <id> ioutcal <ch> <value>` | ch = 1..4, value = mA |
| Reset 4–20mA output cal | `megaind <id> ioutcalrst <ch>` | ch = 1..4 |

**Note on two-point calibration:**  
- Each calibration command is called **twice**: once for point 1, once for point 2.
- Voltage calibration: points must be ≥5V apart.
- Current calibration: points must be ≥10mA apart.

### Backend Service Architecture (Suggested)

1. **Create a `MegaIndService` class** (similar to existing `Sequent24b8vinService`):
   - Initialize with stack level (0..7)
   - Wrapper methods for all Python API calls (with exception handling)
   - Subprocess calls for CLI-only commands (calibration, RS485, watchdog reset count clear, etc.)
   - Thread-safe I2C access (use locks if needed)

2. **Create a `MegaIndRepository` class** for config persistence:
   - Store channel labels, enable/disable states, output "armed" state
   - Store RS485 config, watchdog config
   - Store calibration state (not calibrated / point 1 captured / calibrated)
   - Store input range jumper settings (user-documented, not auto-detected)

3. **Create Flask routes** in `app/routes.py`:
   - `GET /settings` → render consolidated technician settings page
   - `GET /api/megaind/<stack>/diagnostics` → JSON (firmware, voltages, temp, online status)
   - `GET /api/megaind/<stack>/analog-inputs` → JSON (all input values)
   - `POST /api/megaind/<stack>/analog-outputs/arm` → Enable/disable ARM OUTPUTS
   - `POST /api/megaind/<stack>/analog-outputs/<ch>/set` → Set output value (if armed)
   - `GET /api/megaind/<stack>/digital-io` → JSON (opto states, counters, OD states)
   - `POST /api/megaind/<stack>/digital-io/opto/<ch>/reset-counter`
   - `POST /api/megaind/<stack>/digital-io/opto/<ch>/set-edge-counting`
   - `POST /api/megaind/<stack>/digital-io/od/<ch>/set`
   - `POST /api/megaind/<stack>/calibration` → Execute calibration command (via CLI subprocess)
   - `GET /api/megaind/<stack>/watchdog` → JSON (period, default period, off interval, reset count)
   - `POST /api/megaind/<stack>/watchdog/reload`
   - `POST /api/megaind/<stack>/watchdog/set-period`
   - `GET /api/megaind/<stack>/rs485` → JSON (current RS485 config via CLI read)
   - `POST /api/megaind/<stack>/rs485/set` → Set RS485 config (via CLI subprocess)
   - `GET /api/megaind/<stack>/rtc` → JSON (current RTC date/time)
   - `POST /api/megaind/<stack>/rtc/set`
   - `GET /api/megaind/<stack>/owb` → JSON (sensor count, temps, ROM codes)
   - `POST /api/megaind/<stack>/owb/scan`
   - `GET /api/megaind/<stack>/leds` → JSON (LED states)
   - `POST /api/megaind/<stack>/leds/<ch>/set`

4. **Logging:**
   - Every POST request that changes state → insert event into `events` table
   - Include all fields from logging schema (Section B.11)

---

## SECTION D — Example Python Snippets (For Future Implementation)

### Example 1: Read Analog Input

```python
import megaind

# Configuration
STACK_LEVEL = 0  # MegaIND stack level (0..7)
CHANNEL = 1      # Voltage input channel 1

# Read 0–10V input (jumper must be in 0–10V position)
try:
    voltage = megaind.get0_10In(STACK_LEVEL, CHANNEL)
    print(f"Channel {CHANNEL} voltage: {voltage:.3f} V")
except Exception as e:
    print(f"Error reading analog input: {e}")

# Read ±10V input (jumper must be in ±10V position)
try:
    voltage = megaind.getpm10In(STACK_LEVEL, CHANNEL)
    print(f"Channel {CHANNEL} voltage (±10V range): {voltage:.3f} V")
except Exception as e:
    print(f"Error reading analog input: {e}")

# Read 4–20mA input
try:
    current = megaind.get4_20In(STACK_LEVEL, CHANNEL)
    print(f"Channel {CHANNEL} current: {current:.3f} mA")
except Exception as e:
    print(f"Error reading analog input: {e}")
```

---

### Example 2: Arm + Set Analog Output (SAFETY-CRITICAL)

```python
import megaind
import time

STACK_LEVEL = 0
CHANNEL = 1
TARGET_VOLTAGE = 5.0  # 5V output

# IMPORTANT: User must enable "ARM OUTPUTS" in UI before this code runs
# Check "armed" state from config database
armed = get_output_armed_state_from_db()  # Hypothetical function

if not armed:
    print("ERROR: Outputs are DISARMED. Cannot set output.")
    print("Enable 'ARM OUTPUTS' in the MegaIND settings page.")
    exit(1)

# Log the intent
log_event("megaind", STACK_LEVEL, "analog_output", CHANNEL, 
          old_value=None, new_value=TARGET_VOLTAGE, 
          reason="Technician test output")

# Set the output
try:
    megaind.set0_10Out(STACK_LEVEL, CHANNEL, TARGET_VOLTAGE)
    print(f"Set channel {CHANNEL} to {TARGET_VOLTAGE} V")
    
    # Verify readback after 500ms
    time.sleep(0.5)
    readback = megaind.get0_10Out(STACK_LEVEL, CHANNEL)
    print(f"Readback: {readback:.3f} V")
    
    if abs(readback - TARGET_VOLTAGE) > 0.1:
        print(f"WARNING: Readback mismatch! Expected {TARGET_VOLTAGE}, got {readback}")
        
except Exception as e:
    print(f"Error setting analog output: {e}")
    log_event("megaind", STACK_LEVEL, "analog_output", CHANNEL, 
              old_value=None, new_value=None, 
              reason=f"Error: {e}")
```

---

### Example 3: Read Opto Input + Counter

```python
import megaind

STACK_LEVEL = 0
CHANNEL = 1

# Read opto input state
try:
    state = megaind.getOptoCh(STACK_LEVEL, CHANNEL)
    print(f"Opto input {CHANNEL} state: {'HIGH' if state else 'LOW'}")
except Exception as e:
    print(f"Error reading opto input: {e}")

# Read counter value
try:
    count = megaind.getOptoCount(STACK_LEVEL, CHANNEL)
    print(f"Opto input {CHANNEL} counter: {count}")
except Exception as e:
    print(f"Error reading opto counter: {e}")

# Check edge counting configuration
try:
    rising_enabled = megaind.getOptoRisingCountEnable(STACK_LEVEL, CHANNEL)
    falling_enabled = megaind.getOptoFallingCountEnable(STACK_LEVEL, CHANNEL)
    print(f"Edge counting: Rising={rising_enabled}, Falling={falling_enabled}")
except Exception as e:
    print(f"Error reading edge counting config: {e}")

# Read input frequency
try:
    frequency = megaind.getOptoFrequency(STACK_LEVEL, CHANNEL)
    print(f"Opto input {CHANNEL} frequency: {frequency:.2f} Hz")
except Exception as e:
    print(f"Error reading opto frequency: {e}")

# Reset counter (if needed)
reset_counter = input("Reset counter? (y/n): ")
if reset_counter.lower() == 'y':
    try:
        megaind.rstOptoCount(STACK_LEVEL, CHANNEL)
        print(f"Counter {CHANNEL} reset to 0")
        log_event("megaind", STACK_LEVEL, "opto_counter_reset", CHANNEL, 
                  old_value=count, new_value=0)
    except Exception as e:
        print(f"Error resetting counter: {e}")
```

---

### Example 4: Set Open-Drain PWM Duty

```python
import megaind
import time

STACK_LEVEL = 0
CHANNEL = 1
DUTY_CYCLE = 50  # 50% duty cycle

# Check if outputs are armed
armed = get_output_armed_state_from_db()  # Hypothetical function
if not armed:
    print("ERROR: Outputs are DISARMED. Cannot set open-drain output.")
    exit(1)

# Read current duty cycle
try:
    current_duty = megaind.getOdPWM(STACK_LEVEL, CHANNEL)
    print(f"Current duty cycle: {current_duty}%")
except Exception as e:
    print(f"Error reading current duty: {e}")
    current_duty = None

# Set new duty cycle
try:
    megaind.setOdPWM(STACK_LEVEL, CHANNEL, DUTY_CYCLE)
    print(f"Set open-drain output {CHANNEL} to {DUTY_CYCLE}% duty")
    
    # Log the change
    log_event("megaind", STACK_LEVEL, "open_drain_output", CHANNEL, 
              old_value=current_duty, new_value=DUTY_CYCLE)
    
    # Verify readback
    time.sleep(0.5)
    readback = megaind.getOdPWM(STACK_LEVEL, CHANNEL)
    print(f"Readback duty cycle: {readback}%")
    
except Exception as e:
    print(f"Error setting open-drain PWM: {e}")
```

---

### Example 5: Calibration (Two-Point, via CLI subprocess)

```python
import subprocess

STACK_LEVEL = 0
CHANNEL = 1
SUBSYSTEM = "uincal"  # 0–10V input calibration

# Point 1: Apply 0.5V to input, then calibrate
point1_value = 0.5
input(f"Apply {point1_value}V to channel {CHANNEL} and press Enter...")
try:
    result = subprocess.run(
        ["megaind", str(STACK_LEVEL), SUBSYSTEM, str(CHANNEL), str(point1_value)],
        capture_output=True, text=True, check=True
    )
    print(f"Point 1 calibration captured: {result.stdout}")
    log_event("megaind", STACK_LEVEL, f"{SUBSYSTEM}_point1", CHANNEL, 
              old_value=None, new_value=point1_value)
except subprocess.CalledProcessError as e:
    print(f"Error during point 1 calibration: {e.stderr}")
    exit(1)

# Point 2: Apply 9.5V to input, then calibrate (≥5V apart from point 1)
point2_value = 9.5
input(f"Apply {point2_value}V to channel {CHANNEL} and press Enter...")
try:
    result = subprocess.run(
        ["megaind", str(STACK_LEVEL), SUBSYSTEM, str(CHANNEL), str(point2_value)],
        capture_output=True, text=True, check=True
    )
    print(f"Point 2 calibration captured: {result.stdout}")
    log_event("megaind", STACK_LEVEL, f"{SUBSYSTEM}_point2", CHANNEL, 
              old_value=None, new_value=point2_value)
    print("Calibration complete!")
except subprocess.CalledProcessError as e:
    print(f"Error during point 2 calibration: {e.stderr}")
    exit(1)
```

---

### Example 6: Watchdog Management

```python
import megaind
import time

STACK_LEVEL = 0
PERIOD = 60  # 60 seconds

# Get current watchdog period
try:
    current_period = megaind.wdtGetPeriod(STACK_LEVEL)
    print(f"Current watchdog period: {current_period}s")
except Exception as e:
    print(f"Error reading watchdog period: {e}")

# Set watchdog period
try:
    megaind.wdtSetPeriod(STACK_LEVEL, PERIOD)
    print(f"Watchdog period set to {PERIOD}s")
    log_event("megaind", STACK_LEVEL, "watchdog_period", None, 
              old_value=current_period, new_value=PERIOD)
except Exception as e:
    print(f"Error setting watchdog period: {e}")

# Reload (pet) the watchdog
try:
    megaind.wdtReload(STACK_LEVEL)
    print("Watchdog reloaded")
except Exception as e:
    print(f"Error reloading watchdog: {e}")

# Get reset count
try:
    reset_count = megaind.wdtGetResetCount(STACK_LEVEL)
    print(f"Watchdog reset count: {reset_count}")
except Exception as e:
    print(f"Error reading reset count: {e}")

# Disable watchdog (set period = 65000)
disable = input("Disable watchdog? (y/n): ")
if disable.lower() == 'y':
    try:
        megaind.wdtSetPeriod(STACK_LEVEL, 65000)
        print("Watchdog disabled")
        log_event("megaind", STACK_LEVEL, "watchdog_disabled", None, 
                  old_value=current_period, new_value=65000)
    except Exception as e:
        print(f"Error disabling watchdog: {e}")
```

---

## END OF SPECIFICATION

**Next Steps:**
1. Review this spec with maintenance team and stakeholders
2. Implement backend `MegaIndService` and repository classes
3. Implement Flask routes and API endpoints
4. Implement frontend UI (HTML + JavaScript for live updates)
5. Implement logging and event tracking
6. Test all I/O functions with physical hardware
7. Document commissioning procedures (jumper settings, wiring, etc.)

**Maintenance Notes:**
- This spec is based on MegaIND firmware v1.1.8 and Python library API as of Dec 2025.
- If firmware or library is updated, review and update this spec accordingly.
- Always consult the official Sequent Microsystems MegaIND user guide for hardware details.
