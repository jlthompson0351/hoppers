# 24b8vin Hardware Reference
**Sequent Microsystems Eight 24-Bit Analog Inputs DAQ HAT**

**Document Version:** 1.1  
**Date:** December 18, 2025  
**Purpose:** Accurate hardware specification for 24b8vin board — INPUT-ONLY DAQ

---

## 🎯 LIVE DASHBOARD: http://172.16.190.25:8080

---

## ✅ DEPLOYED & RUNNING (December 18, 2025)

| Property | Value |
|----------|-------|
| **Dashboard** | http://172.16.190.25:8080 |
| **Status** | ✅ Online, readings live in dashboard |
| **I2C Bus** | 1 (`/dev/i2c-1`) |
| **I2C Base Address** | **0x31** (stack 0) |
| **Firmware Version** | 1.4 |
| **Pi Hostname** | `Hoppers` |
| **Pi IP Address** | `172.16.190.25` |
| **CLI Tool** | `24b8vin` (installed at `/usr/local/bin/24b8vin`) |
| **Python Module** | `SM24b8vin` (import as `import SM24b8vin`) |

**Verified via SSH on December 18, 2025:**
```
$ sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
30: -- 31 -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: 50 -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 

$ 24b8vin 0 board
Firmware version 1.4, CPU temperature 0 C, Power source 0.00 V
```

---

## CRITICAL: What This Board Is (and Is NOT)

### ✅ This Board IS:
- **8-channel differential analog INPUT DAQ**
- 24-bit ADC resolution per channel
- Stackable up to 8 boards (stack IDs 0..7)
- I2C communication with Raspberry Pi
- Voltage input ranges: ±24V down to ±0.18V (software-selectable gain per channel)

### ❌ This Board is NOT:
- ❌ **NO analog OUTPUTS** (no 0–10V outputs, no 4–20mA outputs)
- ❌ **NO excitation outputs** (use external excitation source like SlimPak Ultra)
- ❌ **NO digital I/O** (no opto inputs, no open-drain outputs)
- ❌ **NO load cell signal conditioning** (it's a raw differential voltage DAQ)

**If you need outputs, you need a different board** (e.g., MegaIND for analog/digital outputs).

---

## Hardware Stack Configuration

### Physical Stack Order (FIXED)
```
┌─────────────────────────────────┐
│   24b8vin HAT (TOP)             │ ← This board (8x analog inputs)
├─────────────────────────────────┤
│   MegaIND HAT (BOTTOM)          │ ← Industrial I/O (outputs)
├─────────────────────────────────┤
│   Raspberry Pi 4B               │
└─────────────────────────────────┘
        ↓ I2C Bus (shared)
```

### I2C Addressing

**Base Address:** `0x31` (from `SLAVE_OWN_ADDRESS_BASE`)  
**Stack ID Selection:** DIP switches on board (ID2, ID1, ID0)  
**Address Calculation:** `I2C_Address = 0x31 + Stack_ID`

| Stack ID | DIP (ID2 ID1 ID0) | I2C Address | Hex |
|----------|-------------------|-------------|-----|
| 0 | OFF OFF OFF | 49 | 0x31 |
| 1 | OFF OFF ON  | 50 | 0x32 |
| 2 | OFF ON  OFF | 51 | 0x33 |
| 3 | OFF ON  ON  | 52 | 0x34 |
| 4 | ON  OFF OFF | 53 | 0x35 |
| 5 | ON  OFF ON  | 54 | 0x36 |
| 6 | ON  ON  OFF | 55 | 0x37 |
| 7 | ON  ON  ON  | 56 | 0x38 |

**Commissioning Verification:**
```bash
sudo i2cdetect -y 1
```
Expected output: device appears at calculated address (0x31..0x38).

### No Address Conflict with MegaIND
- **24b8vin:** 0x31..0x38 (base 0x31 + stack ID)
- **MegaIND:** Different base address
- Both can use Stack ID 0 without conflict

---

## Board Features (Verified from Source Code)

### 1. Analog Inputs (Primary Feature)

**Channels:** 8 (CH1..CH8)  
**Resolution:** 24-bit ADC  
**Output Format:** IEEE 754 floating point (volts)  
**Read Function:** `sm24b.get_u_in(channel)` → returns float (volts)

#### Gain Codes (Software-Selectable Per Channel)

| Gain Code | Full Scale Range | Typical Use Case |
|-----------|------------------|------------------|
| 0 | ±24V | High-voltage industrial signals |
| 1 | ±12V | Standard industrial signals |
| 2 | ±6V | Mid-range signals |
| 3 | ±3V | Low-voltage sensors |
| 4 | ±1.5V | Precision sensors |
| 5 | ±0.75V | High-resolution sensors |
| 6 | ±0.37V (±370mV) | Load cell signals (mV range) |
| 7 | ±0.18V (±180mV) | High-gain load cell signals |

**Set Gain:** `sm24b.set_gain(channel, gain_code)`  
**Get Gain:** `sm24b.get_gain(channel)` → returns int (0..7)

**For Load Cells (typical ~3 mV/V):**
- Use gain code 6 (±370mV) or 7 (±180mV)
- Example: 4-load-cell system, 350lb capacity, ~10V excitation
  - Each cell outputs ~0..30mV for 0..350lb
  - Use gain code 6 or 7 for best resolution

#### Sample Rate Selection

**Register:** `I2C_MEM_SR_SEL` (address 43 from data.h)  
**Options:**

| Code | Sample Rate |
|------|-------------|
| 0 | 250 sps |
| 1 | 500 sps |
| 2 | 1000 sps (1 Ksps) |
| 3 | 2000 sps (2 Ksps) |
| 4 | 4000 sps (4 Ksps) |
| 5 | 8000 sps (8 Ksps) |

**Note:** Sample rate selection is available via I2C register but **NOT exposed in the Python library**. Access via:
- CLI: `24b8vin <id> srrd` (read), `24b8vin <id> srwr <code>` (write)
- Direct I2C write (advanced): `bus.write_byte_data(address, 43, rate_code)`

**Recommendation for load cell applications:**
- Start with 250 sps or 500 sps (adequate for slow-changing weight)
- Higher rates useful for vibration monitoring or fast transients

---

### 2. LEDs (8 Onboard Indicators)

**Channels:** 8 (LED1..LED8)  
**Control:** Software via I2C

**Python API:**
- `sm24b.set_led(led, state)` → led=1..8, state=0 (off) or 1 (on)
- `sm24b.get_led(led)` → returns 0 or 1
- `sm24b.set_all_leds(bitmask)` → bitmask=0..255 (8 bits)
- `sm24b.get_all_leds()` → returns int (bitmask)

**Use Cases:**
- Channel activity indicators
- Fault/warning indicators
- Commissioning aids

---

### 3. RTC (Real-Time Clock)

**Feature:** Onboard battery-backed RTC  
**Python API:**
- `sm24b.get_rtc()` → returns tuple `(year, month, day, hour, minute, second)`
- `sm24b.set_rtc(year, month, day, hour, minute, second)` → year is full year (e.g., 2025)

**Use Cases:**
- Timestamping when Pi is offline or NTP unavailable
- Synchronized multi-board data acquisition

---

### 4. Watchdog Timer

**Feature:** Hardware watchdog with Pi power-cycle capability  
**Python API:**
- `sm24b.wdt_reload()` → Pet the watchdog (reset timer)
- `sm24b.wdt_get_period()` → returns int (seconds)
- `sm24b.wdt_set_period(period)` → period in seconds
- `sm24b.wdt_get_init_period()` → returns int (seconds, boot period)
- `sm24b.wdt_set_init_period(period)` → period in seconds
- `sm24b.wdt_get_off_period()` → returns int (seconds, power-off duration)
- `sm24b.wdt_set_off_period(period)` → period in seconds
- `sm24b.wdt_get_reset_count()` → returns int (number of Pi re-powers)
- `sm24b.wdt_clear_reset_count()` → clear reset count to 0

**Typical Values:**
- Default period: 120s (if not set)
- Init period (boot): 180s (allow time for Pi to boot and app to start)
- Off period: 10s (how long to keep Pi powered off after watchdog timeout)

**⚠️ Warning:** If watchdog is enabled, application must call `wdt_reload()` periodically or Pi will power-cycle.

---

### 5. Firmware Version

**Python API:**
- `sm24b.get_version()` → returns string `"major.minor"` (e.g., "1.1")

**Use Cases:**
- Commissioning verification
- Troubleshooting (verify firmware version)
- Feature compatibility checks

---

### 6. Diagnostics (Read-Only)

**Available via I2C registers (not in Python API; requires direct I2C read):**
- **Temperature:** Board temperature sensor
- **Raspberry Pi Voltage:** Pi 5V rail voltage

**Registers:**
- `I2C_MEM_DIAG_TEMPERATURE_ADD` (address 43)
- `I2C_MEM_DIAG_RASP_V_ADD` (address 44)

**Access Example (direct I2C):**
```python
from smbus2 import SMBus
bus = SMBus(1)
address = 0x31 + stack_id
temp = bus.read_byte_data(address, 43)  # Temperature
pi_voltage = bus.read_word_data(address, 44)  # Pi voltage
```

**Recommendation:** Expose these in UI for maintenance diagnostics.

---

### 7. Calibration

**Feature:** Input channel calibration (appears to be for CH1 only based on source code)  
**CLI Commands (NOT in Python API):**
```bash
24b8vin <id> calstat          # Display calibration status
# (Other calibration commands may exist; check: 24b8vin -h)
```

**Calibration Registers (from data.h):**
- `I2C_MEM_CALIB_VALUE` (address 86): 4-byte float, calibration reference value
- `I2C_MEM_CALIB_CHANNEL` (address 90): 1-byte channel number
- `I2C_MEM_CALIB_KEY` (address 91): Calibration key (0xAA)
- `I2C_MEM_CALIB_STATUS` (address 92): Status (0=in progress, 1=done, 2=error)

**Status Values:**
- `CALIB_IN_PROGRESS` = 0
- `CALIB_DONE` = 1
- `CALIB_ERROR` = 2

**⚠️ UNKNOWN:** Exact calibration procedure for 24b8vin is not fully documented in Python API.  
**Action Required:** Test CLI commands (`24b8vin -h`) to discover full calibration command set.

---

### 8. RS485 / MODBUS (Optional)

**Feature:** MODBUS RTU slave mode over RS485  
**Configuration:** Software + DIP switches

#### DIP Switch Functions (Physical, NOT Software-Configurable)
- **ID2, ID1, ID0:** Stack ID selection (0..7) → determines I2C address
- **RS485 Termination:** Enable/disable 120Ω termination resistor
- **TX/RX Source:** Select RS485 transceiver source

**⚠️ UI Constraint:** DIP switches are **PHYSICAL**. UI can only:
- Display expected DIP configuration
- Warn if mismatch detected (if detectable via I2C)
- Record commissioning DIP settings for reference

#### Software Configuration (CLI)
```bash
24b8vin 0 cfg485wr 1 1 9600 1 0
# Mode=1 (Modbus RTU), Slave_Addr_Offset=1, Baud=9600, StopBits=1, Parity=0 (none)
```

**Slave Address Calculation:**
```
Modbus_Slave_Address = Stack_ID + Slave_Address_Offset
```

Example: Stack ID = 1, Offset = 1 → Modbus Slave Address = 2

**Modbus Objects Supported:**
- **Coils (R/W):** LED1..LED8 (addresses 0x00..0x07)
- **Input Registers (R):** VIN1..VIN8 (32-bit IEEE 754, 2 registers per channel)
- **Holding Registers (R/W):** Gain codes CH1..CH8 (addresses 0x00..0x07)

**Function Codes:**
- 0x01: Read Coils
- 0x02: Read Discrete Inputs
- 0x03: Read Holding Registers
- 0x04: Read Input Registers
- 0x05: Write Single Coil
- 0x06: Write Single Register
- 0x0F: Write Multiple Coils
- 0x10: Write Multiple Registers

**⚠️ Note:** RS485/MODBUS mode is **OPTIONAL**. Most applications will use direct I2C communication via Python library.

---

### 9. Hidden Capabilities (Deep Research Findings)

**1. Status LEDs (Register 0)**
- **Feature:** 8 programmable LEDs on the board.
- **Register:** `I2C_MEM_LEDS` (Address 0).
- **Use Case:** Headless diagnostics (Green=OK, Red=Fault).

**2. Variable Sample Rate (Register 52)**
- **Feature:** Change ADC speed.
- **Register:** `I2C_MEM_SR_SEL` (Address 52).
- **Values:** 0=3.75 SPS, 1=7.5 SPS, 2=15 SPS, 3=30 SPS (Default).
- **Use Case:** Lower for stability, higher for transient detection.

**3. Real-Time Clock (RTC)**
- **Feature:** Battery-backed timekeeping.
- **Registers:** 57-62 (Year, Month, Day, Hour, Min, Sec).
- **Use Case:** Offline logging timestamps.

---

## Python Library: SM24b8vin

### Installation
```bash
sudo pip3 install SM24b8vin
```

### Basic Usage
```python
import SM24b8vin

# Initialize (stack=0, i2c_bus=1)
sm24b = SM24b8vin.SM24b8vin(stack=0, i2c=1)

# Read analog input CH1
voltage = sm24b.get_u_in(1)
print(f"CH1: {voltage:.6f} V")

# Set gain code for CH1 to ±0.37V (gain code 6)
sm24b.set_gain(1, 6)

# Read all 8 channels
for ch in range(1, 9):
    voltage = sm24b.get_u_in(ch)
    gain = sm24b.get_gain(ch)
    print(f"CH{ch}: {voltage:.6f} V (gain={gain})")
```

### Complete API Reference

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `__init__(stack, i2c)` | stack=0..7, i2c=1 | SM24b8vin object | Initialize board |
| `get_u_in(channel)` | channel=1..8 | float (volts) | Read analog input voltage |
| `get_gain(channel)` | channel=1..8 | int (0..7) | Get gain code for channel |
| `set_gain(channel, gain)` | channel=1..8, gain=0..7 | None | Set gain code for channel |
| `get_led(led)` | led=1..8 | int (0 or 1) | Get LED state |
| `set_led(led, state)` | led=1..8, state=0 or 1 | None | Set LED state |
| `get_all_leds()` | None | int (bitmask) | Get all LED states as bitmask |
| `set_all_leds(bitmask)` | bitmask=0..255 | None | Set all LEDs at once |
| `get_rtc()` | None | tuple (y, mo, d, h, m, s) | Get RTC date/time |
| `set_rtc(y, mo, d, h, m, s)` | year, month, day, hour, minute, second | None | Set RTC date/time |
| `wdt_reload()` | None | None | Reload (pet) watchdog timer |
| `wdt_get_period()` | None | int (seconds) | Get watchdog period |
| `wdt_set_period(period)` | period (seconds) | None | Set watchdog period |
| `wdt_get_init_period()` | None | int (seconds) | Get init period (boot) |
| `wdt_set_init_period(period)` | period (seconds) | None | Set init period |
| `wdt_get_off_period()` | None | int (seconds) | Get power-off period |
| `wdt_set_off_period(period)` | period (seconds) | None | Set power-off period |
| `wdt_get_reset_count()` | None | int | Get watchdog reset count |
| `wdt_clear_reset_count()` | None | None | Clear watchdog reset count |
| `get_version()` | None | str ("major.minor") | Get firmware version |

---

## CLI Tool: 24b8vin

### Installation
```bash
cd ~
git clone https://github.com/SequentMicrosystems/24b8vin-rpi.git
cd 24b8vin-rpi/
sudo make install
```

### Basic Commands

```bash
# Help
24b8vin -h

# Read analog input CH2 on board 0
24b8vin 0 vinrd 2

# Read all 8 channels on board 0
24b8vin 0 vinrd

# Get gain code for CH2 on board 0
24b8vin 0 grd 2

# Set gain code to 4 (±1.5V) for CH2 on board 0
24b8vin 0 gwr 2 4

# Calibration status
24b8vin 0 calstat

# RS485/MODBUS config (mode, addr_offset, baud, stop, parity)
24b8vin 0 cfg485wr 1 1 9600 1 0

# (Check 24b8vin -h for complete command list)
```

---

## Common Troubleshooting

### 1. Board Not Detected on I2C Bus

**Symptoms:**
- Python: `"Eight 24-Bit Analog Inputs not detected!"`
- CLI: `"Card not detected"`
- `i2cdetect -y 1` does not show device at expected address

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| I2C not enabled on Pi | Run `sudo raspi-config`, enable I2C, reboot |
| DIP switches incorrect | Verify DIP switch position matches stack ID you're using in software |
| Wrong I2C address in code | Calculate: 0x31 + stack_id. Example: stack_id=0 → 0x31 (decimal 49) |
| Physical connection issue | Verify HAT is seated properly on GPIO header |
| Address conflict | Another device on bus at same address; check `i2cdetect -y 1` |
| Wrong I2C bus | Use bus 1 (`/dev/i2c-1`), not bus 0 |

**Verification Commands:**
```bash
# Check if I2C enabled
lsmod | grep i2c

# Scan I2C bus
sudo i2cdetect -y 1

# Expected output for stack ID 0 (address 0x31 = 49):
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 00:          -- -- -- -- -- -- -- -- -- -- -- -- --
# 10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
# 30: -- 31 -- -- -- -- -- -- -- -- -- -- -- -- -- --
#        ^^
```

---

### 2. Incorrect Voltage Readings

**Symptoms:**
- Voltage reads 0.0 V when signal is present
- Voltage reads out of range
- Voltage is clipped at gain limit

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Wrong gain code | Input signal exceeds gain range. Example: 5V signal with gain 7 (±0.18V) → clipped. Use gain 2 (±6V). |
| Open input wiring | Check differential input connections (IN+, IN−) |
| Ground loop or offset | Verify signal reference/common |
| Board needs calibration | Run calibration procedure (see CLI: `24b8vin 0 calstat`) |

**Gain Selection Guide:**
```
Signal Range    →  Recommended Gain Code
±20V           →  0 (±24V)
±10V           →  1 (±12V)
±5V            →  2 (±6V)
±2V            →  3 (±3V)
±1V            →  4 (±1.5V)
±0.5V          →  5 (±0.75V)
±0.3V (300mV)  →  6 (±0.37V)
±0.1V (100mV)  →  7 (±0.18V)
```

---

### 3. Address Collision with Another Board

**Symptoms:**
- `i2cdetect` shows device at address, but wrong board responds
- Multiple boards on same bus conflict

**Solution:**

| Board | Base Address | Stack ID Range | Address Range |
|-------|--------------|----------------|---------------|
| 24b8vin | 0x31 | 0..7 | 0x31..0x38 |
| MegaIND | (Different base) | 0..7 | (No conflict) |

If stacking multiple 24b8vin boards, use different stack IDs (set via DIP switches).

Example:
- Board 1: DIP all OFF → Stack ID 0 → Address 0x31
- Board 2: DIP ID0 ON → Stack ID 1 → Address 0x32

---

### 4. Watchdog Keeps Resetting Pi

**Symptoms:**
- Pi power-cycles unexpectedly
- Watchdog reset count incrementing

**Solution:**
- Ensure application calls `wdt_reload()` periodically (before period expires)
- Check init period is long enough for Pi to boot and app to start (recommend ≥180s)
- Disable watchdog during commissioning: `sm24b.wdt_set_period(65000)` (special value)

---

### 5. RS485/MODBUS Not Working

**Symptoms:**
- Modbus master cannot communicate with board
- No response on RS485 bus

**Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| DIP switches incorrect | Verify termination and TX/RX source DIPs match hardware setup |
| Software not configured | Run CLI: `24b8vin 0 cfg485wr 1 1 9600 1 0` |
| Wrong Modbus slave address | Check: Modbus_Addr = Stack_ID + Offset |
| Bus termination missing | Enable termination DIP on last device on bus |

---

## Physical Settings (DIP Switches)

### Stack ID Selection (ID2, ID1, ID0)

**Location:** DIP switches on board  
**Purpose:** Selects I2C address (0x31 + stack_id)  
**Configuration:** Set BEFORE power-on

| ID2 | ID1 | ID0 | Stack ID | I2C Addr |
|-----|-----|-----|----------|----------|
| OFF | OFF | OFF | 0 | 0x31 |
| OFF | OFF | ON  | 1 | 0x32 |
| OFF | ON  | OFF | 2 | 0x33 |
| OFF | ON  | ON  | 3 | 0x34 |
| ON  | OFF | OFF | 4 | 0x35 |
| ON  | OFF | ON  | 5 | 0x36 |
| ON  | ON  | OFF | 6 | 0x37 |
| ON  | ON  | ON  | 7 | 0x38 |

### RS485 DIP Functions

**⚠️ UNKNOWN:** Exact DIP switch mapping for RS485 termination and TX/RX source selection is not documented in Python library or README.

**Action Required:** Consult board silkscreen or Sequent Microsystems hardware user guide (if available) for DIP switch labeling.

**Typical RS485 DIPs:**
- **TERM:** 120Ω termination resistor enable (ON for last device on bus)
- **TX/RX:** Transceiver source select (board-specific)

---

## Settings Schema for Maintenance UI

### A) Hardware-Level Settings (Software-Controllable via I2C)

```json
{
  "hardware_settings": {
    "i2c_bus": 1,
    "stack_id": 0,
    "expected_i2c_address": "0x31",
    "channels": [
      {
        "channel": 1,
        "enabled": true,
        "gain_code": 6,
        "label": "Load Cell Front-Left",
        "notes": "±370mV range for ~30mV full-scale load cell"
      },
      {
        "channel": 2,
        "enabled": true,
        "gain_code": 6,
        "label": "Load Cell Front-Right",
        "notes": ""
      },
      {
        "channel": 3,
        "enabled": true,
        "gain_code": 6,
        "label": "Load Cell Rear-Left",
        "notes": ""
      },
      {
        "channel": 4,
        "enabled": true,
        "gain_code": 6,
        "label": "Load Cell Rear-Right",
        "notes": ""
      },
      {
        "channel": 5,
        "enabled": false,
        "gain_code": 0,
        "label": "Unused",
        "notes": ""
      },
      {
        "channel": 6,
        "enabled": false,
        "gain_code": 0,
        "label": "Unused",
        "notes": ""
      },
      {
        "channel": 7,
        "enabled": false,
        "gain_code": 0,
        "label": "Unused",
        "notes": ""
      },
      {
        "channel": 8,
        "enabled": false,
        "gain_code": 0,
        "label": "Unused",
        "notes": ""
      }
    ],
    "leds": {
      "led_1": false,
      "led_2": false,
      "led_3": false,
      "led_4": false,
      "led_5": false,
      "led_6": false,
      "led_7": false,
      "led_8": false,
      "all_leds_bitmask": 0
    },
    "rtc": {
      "current_time": "(read-only, fetched via get_rtc())",
      "sync_to_system": "(button action)"
    },
    "watchdog": {
      "enabled": true,
      "period_seconds": 120,
      "init_period_seconds": 180,
      "off_period_seconds": 10,
      "reset_count": "(read-only)",
      "clear_reset_count": "(button action)"
    },
    "firmware_version": "(read-only, e.g., '1.1')",
    "diagnostics": {
      "board_temperature_c": "(read-only, requires direct I2C read)",
      "pi_voltage_v": "(read-only, requires direct I2C read)"
    }
  }
}
```

**Notes on Hardware Settings:**
- **`channel_enabled`:** This is **APP-LEVEL** (software ignores channel), NOT hardware disable. The ADC continues sampling; we just don't use the data.
- **`gain_code`:** Writable via `set_gain()`. Changes take effect immediately.
- **`leds`:** Writable via `set_led()` or `set_all_leds()`.
- **`watchdog`:** Enable by setting period <65000. Disable by setting period =65000 (special value).

---

### B) Physical-Only Settings (DIP Switches — UI Display/Record ONLY)

```json
{
  "physical_settings": {
    "dip_switches": {
      "stack_id_dip": {
        "id2": false,
        "id1": false,
        "id0": false,
        "calculated_stack_id": 0,
        "calculated_i2c_address": "0x31",
        "note": "SET BEFORE POWER-ON. UI cannot change DIP switches."
      },
      "rs485_termination": {
        "enabled": false,
        "note": "120Ω termination resistor. Enable on last device on RS485 bus."
      },
      "rs485_tx_rx_source": {
        "value": "unknown",
        "note": "Consult board silkscreen for DIP mapping."
      }
    },
    "rs485_modbus": {
      "mode": "disabled",
      "slave_address_offset": 1,
      "baudrate": 9600,
      "stop_bits": 1,
      "parity": "none",
      "calculated_modbus_address": "(stack_id + offset)",
      "note": "Software config via CLI: 24b8vin <id> cfg485wr <mode> <offset> <baud> <stop> <parity>"
    }
  }
}
```

**Notes on Physical Settings:**
- **UI Constraint:** Cannot toggle DIP switches in software. UI should:
  - Display expected/documented DIP positions
  - Allow tech to record actual DIP positions during commissioning
  - Warn if mismatch detected (e.g., software stack_id=0 but I2C address=0x32)

---

### C) App-Level Settings (Not Hardware Features)

```json
{
  "app_settings": {
    "ui_refresh_rate_hz": 2.0,
    "read_units": "volts",
    "sampling_config": {
      "acquisition_loop_rate_hz": 10.0,
      "adc_sample_rate_code": 0,
      "adc_sample_rate_sps": 250,
      "note": "ADC sample rate is UNKNOWN if controllable via I2C register 43. Needs CLI testing."
    },
    "channel_display": {
      "show_disabled_channels": false,
      "show_gain_ranges": true,
      "show_raw_adc_counts": false
    }
  }
}
```

**Notes on App Settings:**
- **`ui_refresh_rate_hz`:** How often UI polls board for updates (app-level, not hardware)
- **`acquisition_loop_rate_hz`:** Background thread read rate (app-level)
- **`adc_sample_rate_code`:** If writable via I2C register 43, include in hardware settings. Otherwise, treat as read-only diagnostic.

---

## Implementation Notes for UI Development

### 1. Python Library Detection

**Recommended Approach:**
```python
import importlib.util

# Check if SM24b8vin is installed
spec = importlib.util.find_spec("SM24b8vin")
if spec is None:
    raise ImportError("SM24b8vin library not installed. Run: sudo pip3 install SM24b8vin")

import SM24b8vin
```

**Fallback:** If Python library is not available, use CLI commands via `subprocess`:
```python
import subprocess
result = subprocess.run(["24b8vin", "0", "vinrd", "1"], capture_output=True, text=True)
voltage = float(result.stdout.strip())
```

---

### 2. Service Layer (Backend)

**Create:** `src/hw/board_24b8vin_service.py`

```python
import SM24b8vin
import logging

class Board24b8vinService:
    def __init__(self, stack_id=0, i2c_bus=1):
        self.stack_id = stack_id
        self.i2c_bus = i2c_bus
        try:
            self.board = SM24b8vin.SM24b8vin(stack=stack_id, i2c=i2c_bus)
            self.online = True
        except Exception as e:
            logging.error(f"24b8vin board (stack {stack_id}) not detected: {e}")
            self.online = False
            self.board = None
    
    def is_online(self):
        return self.online
    
    def read_channel(self, channel):
        """Read voltage for channel 1..8"""
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.get_u_in(channel)
    
    def read_all_channels(self):
        """Read all 8 channels, return list of voltages"""
        if not self.online:
            raise RuntimeError("Board offline")
        return [self.board.get_u_in(ch) for ch in range(1, 9)]
    
    def set_gain(self, channel, gain_code):
        """Set gain code (0..7) for channel 1..8"""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.set_gain(channel, gain_code)
    
    def get_gain(self, channel):
        """Get gain code for channel 1..8"""
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.get_gain(channel)
    
    def get_firmware_version(self):
        """Get firmware version string"""
        if not self.online:
            return "N/A"
        return self.board.get_version()
    
    # Add methods for LEDs, RTC, watchdog, etc.
```

---

### 3. Flask Routes (API Endpoints)

**Add to:** `src/app/routes.py`

```python
from flask import jsonify, request
from src.hw.board_24b8vin_service import Board24b8vinService

# Initialize service (stack_id from config)
board_24b8vin = Board24b8vinService(stack_id=0, i2c_bus=1)

@app.route('/api/24b8vin/status', methods=['GET'])
def get_24b8vin_status():
    return jsonify({
        'online': board_24b8vin.is_online(),
        'stack_id': board_24b8vin.stack_id,
        'i2c_address': hex(0x31 + board_24b8vin.stack_id),
        'firmware_version': board_24b8vin.get_firmware_version()
    })

@app.route('/api/24b8vin/channels', methods=['GET'])
def get_24b8vin_channels():
    voltages = board_24b8vin.read_all_channels()
    gains = [board_24b8vin.get_gain(ch) for ch in range(1, 9)]
    return jsonify({
        'channels': [
            {'channel': ch, 'voltage': voltages[ch-1], 'gain_code': gains[ch-1]}
            for ch in range(1, 9)
        ]
    })

@app.route('/api/24b8vin/channel/<int:channel>/gain', methods=['POST'])
def set_24b8vin_gain(channel):
    gain_code = request.json.get('gain_code')
    board_24b8vin.set_gain(channel, gain_code)
    # Log change
    return jsonify({'success': True})
```

---

### 4. Confirmed Functions vs UNKNOWN

#### ✅ CONFIRMED (from Python library source code):
- `get_u_in(channel)` → Read voltage
- `set_gain(channel, gain_code)` / `get_gain(channel)` → Gain control
- `set_led()` / `get_led()` / `set_all_leds()` / `get_all_leds()` → LED control
- `get_rtc()` / `set_rtc()` → RTC read/write
- `wdt_*()` methods → Watchdog control
- `get_version()` → Firmware version

#### ❌ UNKNOWN / NEEDS CLI TESTING:
- **ADC sample rate control:** I2C register exists (address 43), but no Python method. Test CLI: `24b8vin -h` to find command.
- **Calibration procedure:** `calstat` command exists, but full calibration command set unknown. Test CLI: `24b8vin -h`.
- **Diagnostics (temperature, Pi voltage):** I2C registers exist, but not exposed in Python library. Requires direct I2C read.
- **Channel enable/disable:** No hardware method found. Implement as app-level "ignore channel".
- **RS485 DIP mapping:** Not documented. Consult board silkscreen or hardware user guide.

#### 🔬 ACTION REQUIRED (Before UI Implementation):
1. Run `24b8vin -h` on Pi to discover all CLI commands
2. Test calibration commands (if exist)
3. Test sample rate commands (if exist)
4. Verify RS485 DIP switch labels on physical board
5. Test diagnostics registers (temperature, Pi voltage) via direct I2C read

---

## References

- **Product Page:** https://sequentmicrosystems.com/products/eight-24-bit-analog-inputs-daq-8-layer-stackable-hat-for-raspberry-pi
- **GitHub Repo:** https://github.com/SequentMicrosystems/24b8vin-rpi
- **Python Library (PyPI):** https://pypi.org/project/SM24b8vin/
- **Source Code (Vendor):** `.vendor/24b8vin-rpi/` (local copy)
- **Modbus Documentation:** `.vendor/24b8vin-rpi/MODBUS.md`

---

**Document Version:** 1.0  
**Last Updated:** December 17, 2025  
**Next Review:** After CLI testing complete
