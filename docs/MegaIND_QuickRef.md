# MegaIND Quick Reference Card

**Hardware Stack:** Raspberry Pi → MegaIND (ID 0..7) → 24b8vin (top)  
**I2C Bus:** 1 (`/dev/i2c-1`)  
**I2C Base Address:** **0x50** (stack 0) — Address = 0x50 + stack_id  
**Python Package:** `SMmegaind` (PyPI) — import as `import megaind`  
**CLI Command:** `megaind <id> <command> [args]`

---

## 🎯 LIVE DASHBOARD: http://172.16.190.25:8080

---

## ✅ DEPLOYED & RUNNING (December 18, 2025)

| Property | Value |
|----------|-------|
| **Dashboard** | http://172.16.190.25:8080 |
| **I2C Address** | **0x50** (stack 0) |
| **Firmware Version** | 04.08 |
| **Status** | ✅ Online, connected to Flask service |
| **CPU Temperature** | 41°C |
| **Power Source** | 24.13V |
| **Pi Voltage** | 5.23V |
| **Pi Hostname** | `Hoppers` |
| **Pi IP Address** | `172.16.190.25` |

**Verified via SSH on December 18, 2025:**
```
$ sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
30: -- 31 -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: 50 -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 

$ megaind 0 board
Firmware ver 04.08, CPU temperature 41 C, Power source 24.13 V, Raspberry 5.23 V
```

---

## CRITICAL CORRECTIONS

❌ **WRONG:** MegaIND has 8 load cell inputs  
✅ **CORRECT:** 24b8vin has 8 load cell inputs. MegaIND has 4 analog voltage/current I/O channels.

❌ **WRONG:** Analog input range (0–10V vs ±10V) is software-selectable  
✅ **CORRECT:** Range is selected by PHYSICAL JUMPERS per channel. Software only reads via correct function.

---

## Hardware Capabilities at a Glance

| Feature | Qty | Range/Type | Config |
|---------|-----|------------|--------|
| Voltage Inputs | 4 | 0–10V **OR** ±10V | **JUMPER** |
| Current Inputs | 4 | 4–20mA | Read-only |
| Voltage Outputs | 4 | 0–10V | Software |
| Current Outputs | 4 | 4–20mA | Software |
| Opto Inputs | 4 | Binary + counter + freq | Software |
| Open-Drain Outputs | 4 | On/Off + PWM 0–100% | Software |
| LEDs | 4 | On/Off | Software |
| Watchdog | 1 | 10–65000s (65000=off) | Software |
| RS485/MODBUS | 1 | Slave mode | Jumper + Software |
| RTC | 1 | Date/Time | Software |
| One-Wire Bus | 1 | Up to 16 DS18B20 | Auto-detect |

---

## Hidden Capabilities (Deep Research Findings)

**1. RS485 Modbus Master**
- **Feature:** Can act as a Modbus Master to control other industrial devices.
- **Use Case:** Daisy-chain laser sensors, VFDs, or other PLCs.

**2. Real-Time Clock (RTC)**
- **Feature:** Battery-backed timekeeping.
- **Use Case:** Redundant time source if Watchdog HAT fails.

---

## Essential Python API

```python
import megaind

# Diagnostics
megaind.getFwVer(stack)
megaind.getPowerVolt(stack)
megaind.getRaspVolt(stack)
megaind.getCpuTemp(stack)

# Analog Inputs (ch = 1..4)
megaind.get0_10In(stack, ch)      # 0–10V (jumper must be in 0–10V)
megaind.getpm10In(stack, ch)      # ±10V (jumper must be in ±10V)
megaind.get4_20In(stack, ch)      # 4–20mA

# Analog Outputs (ch = 1..4)
megaind.set0_10Out(stack, ch, value)   # value = 0..10V
megaind.get0_10Out(stack, ch)
megaind.set4_20Out(stack, ch, value)   # value = 4..20mA
megaind.get4_20Out(stack, ch)

# Opto Inputs (ch = 1..4)
megaind.getOptoCh(stack, ch)      # 0 or 1
megaind.getOptoCount(stack, ch)   # counter 0..65535
megaind.rstOptoCount(stack, ch)
megaind.setOptoRisingCountEnable(stack, ch, state)  # state = 0 or 1
megaind.setOptoFallingCountEnable(stack, ch, state)
megaind.getOptoFrequency(stack, ch)  # Hz

# Open-Drain Outputs (ch = 1..4)
megaind.setOdPWM(stack, ch, duty)  # duty = 0..100%
megaind.getOdPWM(stack, ch)

# LEDs (ch = 1..4)
megaind.setLed(stack, ch, val)    # val = 0 or 1
megaind.getLed(stack, ch)

# Watchdog
megaind.wdtReload(stack)          # Pet the watchdog (also enables it)
megaind.wdtGetPeriod(stack)
megaind.wdtSetPeriod(stack, val)  # val = 10..65000 (65000 = disable)
megaind.wdtGetResetCount(stack)

# RTC
megaind.rtcGet(stack)             # Returns (year, month, day, hour, minute, second)
megaind.rtcSet(stack, y, mo, d, h, m, s)

# One-Wire (sensor = 1..16)
megaind.owbScan(stack)
megaind.owbGetSensorNo(stack)
megaind.owbGetTemp(stack, sensor)
```

---

## CLI-Only Commands (use subprocess)

### Calibration (Two-Point Required)

**Voltage Inputs (points must be ≥5V apart):**
```bash
megaind <id> uincal <ch> <value>      # Capture point (call twice)
megaind <id> uincalrst <ch>           # Reset to factory
```

**Current Inputs (points must be ≥10mA apart):**
```bash
megaind <id> iincal <ch> <value>
megaind <id> iincalrst <ch>
```

**Voltage Outputs (points must be ≥5V apart):**
```bash
megaind <id> uoutcal <ch> <value>
megaind <id> uoutcalrst <ch>
```

**Current Outputs (points must be ≥10mA apart):**
```bash
megaind <id> ioutcal <ch> <value>
megaind <id> ioutcalrst <ch>
```

### RS485 / MODBUS

```bash
# Read current settings
megaind <id> rs485rd

# Write settings (mode, baud, stop, parity, slave_addr)
megaind <id> rs485wr 1 9600 1 0 1     # Modbus RTU, 9600, 1 stop, no parity, addr=1
megaind <id> rs485wr 0                # Disable
```

### Watchdog

```bash
megaind <id> wdtrcrd                  # Get reset count
megaind <id> wdtrcclr                 # Clear reset count
```

---

## Safety Rules for UI Implementation

1. **ARM OUTPUTS Toggle:**  
   - Default: **ON** (auto-armed on startup as of 2026-02-12)  
   - ALL analog and digital output writes require ARM = ON  
   - Display large red/green toggle  
   - Log every state change  
   - Manual disarm available for maintenance/troubleshooting

2. **Output Change Confirmation:**  
   - Require explicit modal confirmation for any output change  
   - Show old value → new value  
   - Log: timestamp, user, channel, old/new, reason

3. **Physical Jumper Warnings:**  
   - Analog input range: "⚠️ Set by PHYSICAL JUMPER — not software"  
   - RS485 mode: "⚠️ May require PHYSICAL JUMPERS for bus control"

4. **Watchdog Warning:**  
   - "⚠️ Will power-cycle Pi if not reloaded within period"  
   - Show countdown timer if watchdog is active

5. **Calibration Guidance:**  
   - Display step-by-step instructions  
   - Enforce minimum point separation (5V or 10mA)  
   - Show "Reset to Factory" button prominently

---

## Logging Requirements

**Log every:**
- ARM OUTPUTS state change
- Analog output write
- Calibration point capture or reset
- Watchdog config change or reload
- RS485 config change
- Opto counter reset
- Edge counting enable/disable
- Open-drain output change
- LED change
- RTC set
- I2C communication error

**Log Schema:**
```
timestamp, user, event_type, board_type, stack_level, 
subsystem, channel, old_value, new_value, reason
```

---

## Default Values & Behavior

| Setting | Default |
|---------|---------|
| Watchdog Period | 120s (if not set) |
| Watchdog at Boot | Disabled (must call wdtReload to enable) |
| RS485 Mode | Disabled (mode = 0) |
| Analog Outputs | 0V / 4mA (safe state) |
| Open-Drain Outputs | 0% duty (off) |
| Opto Edge Counting | Disabled |
| LEDs | Off |

---

## Common Pitfalls

❌ **Reading ±10V input with jumper in 0–10V position:** Returns incorrect value  
✅ **Solution:** Document jumper positions in config DB; display in UI; use correct read function

❌ **Setting output without ARM OUTPUTS enabled:** Silently ignored or error  
✅ **Solution:** Check armed state before every write; display error if not armed

❌ **Calling calibration command only once:** Incomplete calibration  
✅ **Solution:** Two-point calibration requires **two calls** with different reference values

❌ **Forgetting to reload watchdog:** Pi power-cycles unexpectedly  
✅ **Solution:** Background service must call wdtReload() every N seconds (N < period)

❌ **Mixing stack levels:** Reading from wrong board  
✅ **Solution:** Prominently display selected stack level in UI; verify board online before operations

---

## Testing Checklist (Before Production)

- [ ] Verify all 4 analog voltage inputs with precision source (both 0–10V and ±10V jumper positions)
- [ ] Verify all 4 analog current inputs with precision current source
- [ ] Test analog voltage outputs with multimeter (0V, 5V, 10V)
- [ ] Test analog current outputs with ammeter (4mA, 12mA, 20mA)
- [ ] Verify opto inputs with switch/signal generator
- [ ] Test opto counters (rising and falling edge modes)
- [ ] Test open-drain outputs with LED or relay
- [ ] Test PWM duty cycle (0%, 50%, 100%)
- [ ] Calibrate one channel of each type (voltage in, current in, voltage out, current out)
- [ ] Reset calibration to factory
- [ ] Test watchdog: set period, reload, verify no power-cycle
- [ ] Test watchdog timeout: set short period, don't reload, verify power-cycle
- [ ] Test RS485 mode (if using Modbus)
- [ ] Test RTC: set time, read back, power-cycle, verify persistence
- [ ] Test one-wire bus with DS18B20 sensor
- [ ] Verify all logging events are captured
- [ ] Test ARM OUTPUTS interlock (verify writes blocked when disarmed)

---

## Quick Troubleshooting

**Board not detected (I2C error):**
- Check I2C enabled: `sudo raspi-config`
- Check address jumpers match stack level
- Check physical connection (HAT seated properly)
- Run: `i2cdetect -y 1` (should see device at 0x20 + stack_level)

**Analog input reads wrong value:**
- Verify jumper position (0–10V vs ±10V)
- Use correct read function (get0_10In vs getpm10In)
- Check calibration (reset to factory if suspect)
- Verify input wiring (correct polarity, no short)

**Analog output doesn't change:**
- Verify ARM OUTPUTS = ON
- Check readback value (should match set value within tolerance)
- Verify output wiring and load impedance
- Check power supply voltage (must be adequate for output range)

**Watchdog keeps resetting Pi:**
- Verify reload period is sufficient for boot + app startup
- Check default period (wdtGetDefaultPeriod) — must be >60s for safe boot
- Ensure background service is calling wdtReload() regularly
- Disable watchdog temporarily: wdtSetPeriod(stack, 65000)

---

## References

- **Full Spec:** `docs/MegaIND_Settings_SPEC.md`
- **PyPI Package:** https://pypi.org/project/SMmegaind/
- **Sequent Microsystems Product:** https://sequentmicrosystems.com/products/industrial-automation-for-raspberry-pi
- **Source Code:** `.vendor/megaind-rpi/` (for advanced troubleshooting)

---

**Document Version:** 1.0  
**Last Updated:** December 17, 2025
