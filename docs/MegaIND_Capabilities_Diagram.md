# MegaIND Capabilities Visual Reference

**Board:** Sequent Microsystems Industrial Automation HAT (megaind-rpi)  
**Purpose:** Quick visual reference for MegaIND I/O capabilities

---

## Physical Board Position

```
        ┌─────────────────────────────────────┐
        │      24b8vin HAT (TOP)              │
        │   8x 24-bit Load Cell Inputs        │
        │   Stack ID: 0..7                    │
        ├─────────────────────────────────────┤
        │      MegaIND HAT (BOTTOM)           │
        │   Industrial I/O Board              │
        │   Stack ID: 0..7                    │
        ├─────────────────────────────────────┤
        │      Raspberry Pi 4B                │
        └─────────────────────────────────────┘
                  ↓ I2C Bus (shared)
```

**Key Facts:**
- MegaIND is closest to Pi (bottom of stack)
- Both boards on same I2C bus
- No address conflict (different address ranges)
- Both can use Stack ID 0 simultaneously

---

## Analog I/O (8 Channels Total)

### Inputs (4 Channels)

```
┌─────────────────────────────────────────────────────┐
│  ANALOG INPUTS                                      │
├─────────────────────────────────────────────────────┤
│  CH1  [0-10V OR ±10V] ◄── JUMPER SELECT (per ch)  │
│  CH2  [0-10V OR ±10V] ◄── JUMPER SELECT            │
│  CH3  [0-10V OR ±10V] ◄── JUMPER SELECT            │
│  CH4  [0-10V OR ±10V] ◄── JUMPER SELECT            │
│                                                     │
│  CH1  [4-20mA]        ◄── Fixed range              │
│  CH2  [4-20mA]                                     │
│  CH3  [4-20mA]                                     │
│  CH4  [4-20mA]                                     │
└─────────────────────────────────────────────────────┘

⚠️  CRITICAL: Voltage input range is PHYSICAL JUMPER
    - Cannot change in software
    - Must power down to change jumper
    - Software must use correct read function
```

### Outputs (4 Channels)

```
┌─────────────────────────────────────────────────────┐
│  ANALOG OUTPUTS                                     │
├─────────────────────────────────────────────────────┤
│  CH1  [0-10V]  ──► Software controllable           │
│  CH2  [0-10V]      Value: 0..10V                   │
│  CH3  [0-10V]      Typical: PLC analog input       │
│  CH4  [0-10V]                                      │
│                                                     │
│  CH1  [4-20mA] ──► Software controllable           │
│  CH2  [4-20mA]     Value: 4..20mA                  │
│  CH3  [4-20mA]     Typical: PLC analog input       │
│  CH4  [4-20mA]                                     │
└─────────────────────────────────────────────────────┘

🔒  SAFETY: Requires ARM OUTPUTS = ON to write
```

---

## Digital I/O (8 Channels Total)

### Opto-Isolated Inputs (4 Channels)

```
┌─────────────────────────────────────────────────────┐
│  OPTO INPUTS (Isolated)                             │
├─────────────────────────────────────────────────────┤
│  CH1  [OPTO] ──► State (0/1)                       │
│          └──► Counter (0..65535)                   │
│          └──► Frequency (Hz)                       │
│          └──► Edge Counting (rising/falling enable)│
│                                                     │
│  CH2  [OPTO] ──► (same features)                   │
│  CH3  [OPTO] ──► (same features)                   │
│  CH4  [OPTO] ──► (same features)                   │
└─────────────────────────────────────────────────────┘

Use Cases: Operator buttons, limit switches, encoders
```

### Open-Drain Outputs (4 Channels)

```
┌─────────────────────────────────────────────────────┐
│  OPEN-DRAIN OUTPUTS                                 │
├─────────────────────────────────────────────────────┤
│  CH1  [OD] ──► On/Off                              │
│          └──► PWM Duty (0..100%)                   │
│          └──► PWM Freq (10..6400 Hz)               │
│                                                     │
│  CH2  [OD] ──► (same features)                     │
│  CH3  [OD] ──► (same features)                     │
│  CH4  [OD] ──► (same features)                     │
└─────────────────────────────────────────────────────┘

Use Cases: Relays, solenoids, indicator LEDs
🔒  SAFETY: Requires ARM OUTPUTS = ON to write
```

---

## Additional Features

### LEDs (4 Onboard)

```
┌─────────────────────────────────────────────────────┐
│  ONBOARD LEDs                                       │
├─────────────────────────────────────────────────────┤
│  LED1  [●] ──► On/Off (software control)           │
│  LED2  [●]                                          │
│  LED3  [●]                                          │
│  LED4  [●]                                          │
└─────────────────────────────────────────────────────┘

Use Case: Visual diagnostics, status indication
```

### Watchdog Timer

```
┌─────────────────────────────────────────────────────┐
│  WATCHDOG TIMER                                     │
├─────────────────────────────────────────────────────┤
│  Period:        10..65000 s (65000 = disabled)     │
│  Default:       120 s (if not set)                 │
│  Boot Period:   10..64999 s (allows Pi to boot)    │
│  Off Interval:  10..4147200 s (~48 days max)       │
│  Reset Count:   0..65535 (number of Pi re-powers)  │
│                                                     │
│  Action:        Power-cycles Pi if not reloaded    │
└─────────────────────────────────────────────────────┘

⚠️  Must call wdtReload() regularly to prevent power-cycle
```

### RS485 / MODBUS

```
┌─────────────────────────────────────────────────────┐
│  RS485 / MODBUS RTU                                 │
├─────────────────────────────────────────────────────┤
│  Mode:          Disabled / Modbus RTU Slave        │
│  Baudrate:      1200..920600 bps                   │
│  Stop Bits:     1 or 2                             │
│  Parity:        None / Even / Odd                  │
│  Slave Addr:    1..255 (Stack ID + offset)         │
└─────────────────────────────────────────────────────┘

⚠️  May require PHYSICAL JUMPERS (board-rev dependent)
```

### RTC (Real-Time Clock)

```
┌─────────────────────────────────────────────────────┐
│  RTC (Hardware Clock)                               │
├─────────────────────────────────────────────────────┤
│  Date/Time:     Year (2000..2255), Month, Day,     │
│                 Hour, Minute, Second               │
│  Battery:       Retains time across power cycles   │
└─────────────────────────────────────────────────────┘

Use Case: Timekeeping when Pi offline or NTP unavailable
```

### One-Wire Bus (DS18B20 Temperature Sensors)

```
┌─────────────────────────────────────────────────────┐
│  ONE-WIRE BUS                                       │
├─────────────────────────────────────────────────────┤
│  Sensors:       Up to 16x DS18B20 temperature      │
│  Resolution:    0.01°C                             │
│  ROM Code:      64-bit unique ID per sensor        │
│  Auto-detect:   Scan bus to enumerate sensors      │
└─────────────────────────────────────────────────────┘

Use Case: Ambient/equipment temperature monitoring
```

### Diagnostics

```
┌─────────────────────────────────────────────────────┐
│  DIAGNOSTICS (Read-Only)                            │
├─────────────────────────────────────────────────────┤
│  Firmware Ver:    e.g., "1.1.8"                    │
│  Power Supply:    External 24V supply voltage      │
│  Pi Voltage:      5V rail voltage (warn if <4.75V) │
│  CPU Temp:        Pi CPU temperature (warn >70°C)  │
└─────────────────────────────────────────────────────┘
```

---

## Configuration Summary Table

| Feature | Software Config | Hardware Jumper | Notes |
|---------|-----------------|-----------------|-------|
| **Voltage Input Range** | ❌ | ✅ | 0–10V OR ±10V per channel |
| **Voltage Input Value** | ✅ Read | N/A | Use correct function (get0_10In vs getpm10In) |
| **Current Input Value** | ✅ Read | N/A | get4_20In() |
| **Voltage Output Value** | ✅ Read/Write | N/A | set0_10Out() |
| **Current Output Value** | ✅ Read/Write | N/A | set4_20Out() |
| **Opto Input State** | ✅ Read | N/A | getOptoCh() |
| **Opto Counter** | ✅ Read/Reset | N/A | getOptoCount(), rstOptoCount() |
| **Opto Edge Counting** | ✅ Enable/Disable | N/A | setOptoRisingCountEnable(), setOptoFallingCountEnable() |
| **Opto Frequency** | ✅ Read | N/A | getOptoFrequency() |
| **Open-Drain Output** | ✅ On/Off + PWM | N/A | setOdPWM(duty), CLI for freq |
| **LEDs** | ✅ On/Off | N/A | setLed() |
| **Watchdog** | ✅ Period/Reload | N/A | wdtSetPeriod(), wdtReload() |
| **RS485 Mode** | ✅ Config | ⚠️ Maybe | CLI rs485wr + jumpers (board-rev dependent) |
| **RTC** | ✅ Read/Write | N/A | rtcGet(), rtcSet() |
| **One-Wire** | ✅ Scan/Read | N/A | owbScan(), owbGetTemp() |
| **Calibration** | ✅ 2-Point | N/A | CLI: uincal, iincal, uoutcal, ioutcal (call twice) |

---

## Python API Quick Reference

### Import
```python
import megaind
STACK = 0  # Stack level (0..7)
```

### Essential Functions

| Function | Returns | Description |
|----------|---------|-------------|
| `megaind.get0_10In(STACK, ch)` | float (V) | Read 0–10V input (ch=1..4) |
| `megaind.getpm10In(STACK, ch)` | float (V) | Read ±10V input (ch=1..4) |
| `megaind.get4_20In(STACK, ch)` | float (mA) | Read 4–20mA input (ch=1..4) |
| `megaind.set0_10Out(STACK, ch, val)` | None | Set 0–10V output (val=0..10) |
| `megaind.set4_20Out(STACK, ch, val)` | None | Set 4–20mA output (val=4..20) |
| `megaind.getOptoCh(STACK, ch)` | int (0/1) | Read opto input (ch=1..4) |
| `megaind.getOptoCount(STACK, ch)` | int | Read opto counter (ch=1..4) |
| `megaind.rstOptoCount(STACK, ch)` | None | Reset opto counter |
| `megaind.setOptoRisingCountEnable(STACK, ch, state)` | None | Enable rising edge counting (state=0/1) |
| `megaind.setOdPWM(STACK, ch, duty)` | None | Set open-drain PWM (duty=0..100%) |
| `megaind.getOdPWM(STACK, ch)` | int (%) | Read open-drain PWM duty |
| `megaind.setLed(STACK, ch, val)` | None | Set LED (ch=1..4, val=0/1) |
| `megaind.wdtReload(STACK)` | None | Reload (pet) watchdog |
| `megaind.wdtSetPeriod(STACK, val)` | None | Set watchdog period (val=10..65000, 65000=disable) |
| `megaind.rtcGet(STACK)` | tuple | Get RTC (year, month, day, hour, min, sec) |
| `megaind.getFwVer(STACK)` | str | Get firmware version |
| `megaind.getPowerVolt(STACK)` | float (V) | Get power supply voltage |
| `megaind.getRaspVolt(STACK)` | float (V) | Get Pi 5V rail voltage |
| `megaind.getCpuTemp(STACK)` | float (°C) | Get Pi CPU temperature |

### CLI-Only (Use subprocess)
```bash
# Calibration (two-point, call twice with different values)
megaind <id> uincal <ch> <value>      # Voltage input
megaind <id> iincal <ch> <value>      # Current input
megaind <id> uoutcal <ch> <value>     # Voltage output
megaind <id> ioutcal <ch> <value>     # Current output

# Reset calibration to factory
megaind <id> uincalrst <ch>           # Voltage input
megaind <id> iincalrst <ch>           # Current input
megaind <id> uoutcalrst <ch>          # Voltage output
megaind <id> ioutcalrst <ch>          # Current output

# RS485 config
megaind <id> rs485rd                  # Read config
megaind <id> rs485wr <mode> <baud> <stop> <parity> <addr>

# Watchdog
megaind <id> wdtrcrd                  # Get reset count
megaind <id> wdtrcclr                 # Clear reset count
```

---

## Safety Checklist

### Before Enabling Outputs
- [ ] Verify all wiring is correct and secure
- [ ] Verify equipment is in safe state for testing
- [ ] Verify output polarity and voltage/current range matches equipment input
- [ ] Verify analog common/reference grounding is correct
- [ ] Note: ARM OUTPUTS defaults to ON (as of 2026-02-12) - disarm manually if needed during initial testing
- [ ] Use "Test Output" toggle for initial testing (START holds until STOP)

### Before Commissioning
- [ ] Document all physical jumper positions (analog input ranges)
- [ ] Document stack level (0..7)
- [ ] Run `i2cdetect -y 1` and verify board appears on bus
- [ ] Test firmware version read: `megaind <id> board`
- [ ] Test diagnostics (power voltage, Pi voltage, CPU temp)
- [ ] Test all inputs with known reference sources
- [ ] Calibrate all channels to be used (two-point procedure)
- [ ] Test all outputs with multimeter/oscilloscope
- [ ] Test watchdog (set short period, verify reload prevents power-cycle)
- [ ] Document in commissioning record

---

## Common Wiring Examples

### Excitation Voltage Monitoring (Typical Use Case)
```
SlimPak Ultra (Excitation Supply)
    EXC+ ──────────┬─► Load Cell EXC+ (all cells)
                   │
                   └─► MegaIND Analog Input CH1 (0–10V)
                       (Jumper: 0–10V position)
    
    EXC− ──────────┬─► Load Cell EXC− (all cells)
                   │
                   └─► MegaIND Analog Input CH1 REF
```

### PLC Output (0–10V Mode)
```
MegaIND (Stack ID 2, addr 0x52)
    AO_CH1+ ───────► PLC Analog Input+ (AI0)
    AO_CH1− ───────► PLC Analog Input− (AI0 COM)

Python:
    megaind.set0_10Out(2, 1, 5.0)  # 5V output on CH1 (stack 2)
```

### PLC Output (4–20mA Mode)
```
MegaIND (Stack ID 2, addr 0x52)
    AO_CH2+ ───────► PLC Analog Input+ (AI1, current mode)
    AO_CH2− ───────► PLC Analog Input− (AI1 COM)

Python:
    megaind.set4_20Out(0, 2, 12.0)  # 12mA output on CH2
```

### Opto Input (Operator Button)
```
Operator Button (NO contact)
    Terminal 1 ────► MegaIND OPTO_CH1+
    Terminal 2 ────► MegaIND OPTO_CH1− (24V return)

Python:
    state = megaind.getOptoCh(0, 1)
    # state = 1 when button pressed, 0 when released
```

### Open-Drain Output (Relay Drive)
```
MegaIND OD_CH1 ───────┬─► Relay Coil+ (24VDC relay)
                      │
24V Supply+ ─────────►│
                      │
Relay Coil− ─────────► 24V Supply− (common)

Python:
    megaind.setOdPWM(0, 1, 100)  # 100% duty = relay ON
    megaind.setOdPWM(0, 1, 0)    # 0% duty = relay OFF
```

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| Board not detected on I2C | Jumper mismatch, poor connection | Run `i2cdetect -y 1`, check jumpers match stack ID |
| Analog input reads 0V | Wrong jumper position | Check jumper: 0–10V vs ±10V, use correct read function |
| Analog input reads wrong value | Needs calibration | Run 2-point calibration: `megaind <id> uincal <ch> <value>` (twice) |
| Analog output doesn't change | ARM OUTPUTS = OFF (or fault state) | Check ARM OUTPUTS toggle (defaults to ON). Check for I/O faults. |
| Watchdog keeps resetting Pi | Period too short, reload not called | Increase period or ensure background service calls wdtReload() |
| RS485 not working | Missing jumper, wrong mode | Check board revision for jumper requirements, verify rs485wr config |
| Opto counter not incrementing | Edge counting disabled | Enable: setOptoRisingCountEnable() or setOptoFallingCountEnable() |
| PWM not working | Duty=0, outputs not armed | Set duty >0%, enable ARM OUTPUTS |

---

## Document Cross-References

- **Full Spec:** `MegaIND_Settings_SPEC.md` (comprehensive 60+ page spec)
- **Quick Ref:** `MegaIND_QuickRef.md` (cheat sheet)
- **Summary:** `MegaIND_DOCUMENTATION_SUMMARY.md` (executive summary)
- **This Diagram:** `MegaIND_Capabilities_Diagram.md` (visual reference)

---

**Version:** 1.0  
**Last Updated:** December 17, 2025  
**Format:** Print-friendly, single-page reference per section
