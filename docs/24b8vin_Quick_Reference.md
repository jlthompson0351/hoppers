# 24b8vin Quick Reference Card

**Sequent Microsystems 8-Channel 24-Bit Analog Input DAQ**

---

## 🎯 LIVE DASHBOARD: http://172.16.190.15:8080

---

## ✅ DEPLOYED & RUNNING (December 18, 2025)

| Property | Value |
|----------|-------|
| **Dashboard** | http://172.16.190.15:8080 |
| **I2C Address** | **0x31** (stack 0) |
| **Firmware** | v1.4 |
| **Status** | ✅ Online, readings live in dashboard |
| **Pi Hostname** | `Hoppers` |
| **Pi IP** | `172.16.190.15` |
| **CLI Tool** | `24b8vin` |
| **Python Module** | `SM24b8vin` |

---

## CRITICAL: What This Board Is

✅ **INPUT-ONLY DAQ:** 8 differential analog inputs, 24-bit resolution  
❌ **NO OUTPUTS:** No 0–10V, no 4–20mA, no excitation, no digital I/O

**If you need outputs → use MegaIND board** (separate settings page)

---

## Hardware Stack

```
┌─────────────────┐
│ 24b8vin (TOP)   │ ← This board (inputs only)
├─────────────────┤
│ MegaIND (BOTTOM)│ ← Outputs board
├─────────────────┤
│ Raspberry Pi 4B │
└─────────────────┘
```

---

## I2C Addressing

**Base:** 0x31  
**Calculation:** `I2C_Address = 0x31 + Stack_ID`

| Stack ID | DIPs (ID2 ID1 ID0) | I2C Address |
|----------|--------------------|-------------|
| 0 | OFF OFF OFF | 0x31 |
| 1 | OFF OFF ON  | 0x32 |
| 2 | OFF ON  OFF | 0x33 |
| 3 | OFF ON  ON  | 0x34 |
| 4 | ON  OFF OFF | 0x35 |
| 5 | ON  OFF ON  | 0x36 |
| 6 | ON  ON  OFF | 0x37 |
| 7 | ON  ON  ON  | 0x38 |

**Verify:** `sudo i2cdetect -y 1` (should show device at expected address)

---

## Gain Codes (8 Ranges)

| Code | Full Scale | Typical Use |
|------|------------|-------------|
| 0 | ±24V | High-voltage industrial |
| 1 | ±12V | Standard industrial |
| 2 | ±6V | Mid-range sensors |
| 3 | ±3V | Low-voltage sensors |
| 4 | ±1.5V | Precision sensors |
| 5 | ±0.75V | High-resolution |
| 6 | **±0.37V** | **Load cells (mV)** |
| 7 | **±0.18V** | **High-gain load cells** |

**For load cells (~3 mV/V, 10V excitation):**
- Use gain code **6** or **7**
- Example: 0..30mV signal → gain 6 or 7

---

## Python API Cheat Sheet

### Installation
```bash
sudo pip3 install SM24b8vin
```

### Basic Usage
```python
import SM24b8vin

# Initialize (stack=0, i2c_bus=1)
board = SM24b8vin.SM24b8vin(stack=0, i2c=1)

# Read channel 1
voltage = board.get_u_in(1)

# Set gain code for channel 1 to ±0.37V
board.set_gain(1, 6)

# Read all channels
for ch in range(1, 9):
    v = board.get_u_in(ch)
    g = board.get_gain(ch)
    print(f"CH{ch}: {v:.6f}V (gain={g})")
```

### Essential Methods

| Method | Parameters | Returns |
|--------|------------|---------|
| `get_u_in(channel)` | ch=1..8 | float (volts) |
| `set_gain(channel, gain)` | ch=1..8, gain=0..7 | None |
| `get_gain(channel)` | ch=1..8 | int (0..7) |
| `set_led(led, state)` | led=1..8, state=0/1 | None |
| `get_rtc()` | None | tuple (y,mo,d,h,m,s) |
| `wdt_reload()` | None | None (pet watchdog) |
| `get_version()` | None | str ("1.1") |

---

## CLI Commands

```bash
# Help
24b8vin -h

# Read channel 1 on board 0
24b8vin 0 vinrd 1

# Read all 8 channels
24b8vin 0 vinrd

# Get gain code for channel 2
24b8vin 0 grd 2

# Set gain code to 6 for channel 2
24b8vin 0 gwr 2 6

# Calibration status
24b8vin 0 calstat

# RS485 config (mode, offset, baud, stop, parity)
24b8vin 0 cfg485wr 1 1 9600 1 0
```

---

## Troubleshooting

### Board Not Detected

**Check:**
1. I2C enabled: `sudo raspi-config`
2. Scan bus: `sudo i2cdetect -y 1`
3. DIP switches match stack ID in software
4. HAT seated properly on GPIO header

**Expected at address:**
- Stack ID 0 → 0x31 (row 30, column 1)
- Stack ID 1 → 0x32 (row 30, column 2)

---

### Incorrect Voltage Readings

**Causes:**
- **Wrong gain code:** Signal exceeds range → clipped
- **Open wiring:** Check differential IN+/IN− connections
- **Needs calibration:** Run `24b8vin 0 calstat`

**Gain Selection:**
```
Signal Range → Gain Code
±20V        → 0 (±24V)
±10V        → 1 (±12V)
±5V         → 2 (±6V)
±2V         → 3 (±3V)
±1V         → 4 (±1.5V)
±0.5V       → 5 (±0.75V)
±0.3V       → 6 (±0.37V)
±0.1V       → 7 (±0.18V)
```

---

### Watchdog Resets Pi

**Solutions:**
- Call `board.wdt_reload()` periodically (before period expires)
- Increase init period: `board.wdt_set_init_period(180)` (allow Pi to boot)
- Disable: `board.wdt_set_period(65000)` (special value)

---

## Settings Schema Summary

### Hardware-Controllable
- **I2C bus, stack ID**
- **Channels 1..8:** enable/disable (app-level), gain code (0..7), label, notes
- **LEDs 1..8:** on/off
- **RTC:** date/time read/write
- **Watchdog:** period, init period, off period, reset count
- **Firmware version:** read-only

### Physical-Only (DIP Switches)
- **Stack ID DIPs (ID2, ID1, ID0):** Set BEFORE power-on
- **RS485 termination:** 120Ω resistor enable
- **RS485 TX/RX source:** Board-specific

⚠️ **UI CANNOT CHANGE DIP SWITCHES** — only display and warn if mismatch

### App-Level
- **UI refresh rate:** How often to poll board
- **Acquisition loop rate:** Background thread
- **Channel display options:** Show disabled, show gain ranges

---

## Safety Rules

1. **No Outputs on This Board**
   - 24b8vin is INPUT-ONLY
   - For outputs, use MegaIND board

2. **Gain Code Changes**
   - Log every change (who, when, old, new)
   - Warn if signal will clip with new gain

3. **Watchdog**
   - Default: DISABLED (period = 65000)
   - Enable only after confirming background service will reload

4. **Channel Enable/Disable**
   - App-level only (hardware always samples all channels)
   - Ignore disabled channels in processing

---

## Common Wiring

### Load Cell Input
```
Load Cell Signal+  →  24b8vin CH1 IN+
Load Cell Signal−  →  24b8vin CH1 IN−

Set gain code 6 (±370mV) or 7 (±180mV)
```

### Differential Sensor
```
Sensor OUT+  →  24b8vin CH1 IN+
Sensor OUT−  →  24b8vin CH1 IN−
Sensor GND   →  Common/GND

Set gain code based on sensor output range
```

---

## Commissioning Checklist

- [ ] I2C enabled: `sudo raspi-config`
- [ ] I2C detect: `sudo i2cdetect -y 1`
- [ ] Board appears at expected address (0x31 + stack_id)
- [ ] DIP switches match software stack_id
- [ ] Python library installed: `sudo pip3 install SM24b8vin`
- [ ] Test all 8 channels with known voltage source
- [ ] Test all 8 gain codes
- [ ] Verify LEDs toggle
- [ ] Set RTC to system time
- [ ] Test watchdog (if using)
- [ ] Document wiring in commissioning record
- [ ] Take photo of DIP switches

---

## Default Values

| Setting | Default |
|---------|---------|
| Stack ID | 0 |
| I2C Bus | 1 |
| Gain Code | 0 (±24V) |
| LEDs | All OFF |
| Watchdog | DISABLED (65000) |
| RS485 | Disabled (mode 0) |

---

## Features NOT in Python API

**Requires CLI or Direct I2C:**
- ADC sample rate (register 43)
- Board temperature (register 43)
- Pi voltage (register 44-45)
- Calibration procedure (CLI: `24b8vin 0 calstat`)
- RS485 config (CLI: `24b8vin 0 cfg485wr ...`)

**Action Required:** Run `24b8vin -h` to discover all CLI commands

---

## References

- **Product:** https://sequentmicrosystems.com/products/eight-24-bit-analog-inputs-daq-8-layer-stackable-hat-for-raspberry-pi
- **GitHub:** https://github.com/SequentMicrosystems/24b8vin-rpi
- **PyPI:** https://pypi.org/project/SM24b8vin/
- **Full Docs:** `docs/24b8vin_Hardware_Reference.md`
- **Settings Schema:** `docs/24b8vin_Settings_Schema.json`
- **Implementation:** `docs/24b8vin_Implementation_Notes.md`

---

**Version:** 1.0  
**Date:** December 17, 2025  
**Format:** Print-friendly reference card
