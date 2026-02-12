# Hardware Deep Research Findings: Sequent Microsystems HATs

**Date:** February 2, 2026  
**Agent:** Hardware Specialist  
**Purpose:** Consolidate all technical findings, register maps, and hidden capabilities discovered during the deep research of the Sequent Microsystems hardware stack.

---

## 1. Hardware Stack Overview

| Board | Role | I2C Address (Base) | Stack ID Range | Driver | Status |
|-------|------|-------------------|----------------|--------|--------|
| **Multichemistry Watchdog** | UPS, Watchdog, RTC | `0x30` (Fixed) | N/A | `src/hw/sequent_watchdog.py` | ✅ Implemented |
| **Eight 24-Bit ADC (24b8vin)** | Load Cell Inputs | `0x31` | 0..7 | `src/hw/sequent_24b8vin.py` | ✅ Implemented |
| **Industrial Automation (MegaIND)** | Relays, Analog I/O | `0x50` | 0..7 | `src/hw/sequent_megaind.py` | ✅ Implemented |

---

## 2. Hidden Capabilities Discovered

These features were not initially documented or used but are available in the hardware registers.

### 🕒 A. Real-Time Clock (RTC)
**Availability:** ALL THREE BOARDS (Watchdog, DAQ, Industrial).
**Register Map (Common):**
- Year: `0x39` (57)
- Month: `0x3A` (58)
- Day: `0x3B` (59)
- Hour: `0x3C` (60)
- Minute: `0x3D` (61)
- Second: `0x3E` (62)
**Impact:** Allows offline timekeeping. Critical for logging when internet is lost.
**Action:** Sync system time from Watchdog HAT on boot.

### 💡 B. Programmable Status LEDs
**Availability:** DAQ HAT (8 LEDs), Industrial HAT (4 LEDs).
**DAQ Register:** `I2C_MEM_LEDS = 0` (1 byte, bitmask).
**Impact:** "Headless" diagnostics.
- **Green (LED 1):** System Healthy.
- **Red (LED 8):** Fault.
- **Chasing:** Booting.

### 🔘 C. Safe Shutdown Button
**Availability:** Watchdog HAT.
**Register:** `I2C_POWER_SW_STATUS_ADD = 30` (0x1E).
**Impact:** Detects button press. Can trigger graceful `shutdown -h now` to prevent SD card corruption.

### ⚡ D. Variable Sample Rate (DAQ)
**Availability:** DAQ HAT.
**Register:** `I2C_MEM_SR_SEL = 52` (0x34).
**Values:**
- `0`: 3.75 SPS
- `1`: 7.5 SPS
- `2`: 15 SPS
- `3`: 30 SPS (Default)
**Impact:** Lower rates = higher stability/lower noise. Higher rates = faster transient detection.

### 🔌 E. RS485 / Modbus Master
**Availability:** Industrial HAT.
**Impact:** Can daisy-chain external industrial sensors (laser distance, VFDs) into the system.

---

## 3. Register Maps (Technical Reference)

### A. Multichemistry Watchdog (`0x30`)

| Register Name | Address (Dec) | Address (Hex) | Type | Description |
|---------------|---------------|---------------|------|-------------|
| `I2C_WDT_RELOAD` | 0 | 0x00 | Byte | Write 1 to kick |
| `I2C_5V_IN` | 12 | 0x0C | Word (mV) | Input Voltage |
| `I2C_VBAT` | 22 | 0x16 | Word (mV) | Battery Voltage |
| `I2C_TEMP` | 26 | 0x1A | Byte (C) | Temperature |
| `I2C_POWER_SW_STATUS` | 30 | 0x1E | Byte | Button Status |
| `I2C_CHARGE_END_MV` | 52 | 0x34 | Word (mV) | End Charge Voltage |

### B. Eight 24-Bit ADC (`0x31` + Stack)

| Register Name | Address (Dec) | Address (Hex) | Type | Description |
|---------------|---------------|---------------|------|-------------|
| `I2C_MEM_LEDS` | 0 | 0x00 | Byte | LED Bitmask (1-8) |
| `I2C_U_IN_VAL1` | 12 | 0x0C | Float (4B) | Ch1 Voltage |
| `I2C_U_IN_VAL2` | 16 | 0x10 | Float (4B) | Ch2 Voltage |
| ... | ... | ... | ... | ... |
| `I2C_GAIN_CH1` | 44 | 0x2C | Byte | Ch1 Gain Code |
| ... | ... | ... | ... | ... |
| `I2C_MEM_SR_SEL` | 52 | 0x34 | Byte | Sample Rate |

### C. Industrial Automation (`0x50` + Stack)

| Register Name | Address (Dec) | Address (Hex) | Type | Description |
|---------------|---------------|---------------|------|-------------|
| `I2C_MEM_RELAY` | 1 | 0x01 | Byte | Relay Bitmask |
| `I2C_MEM_OPTO` | 3 | 0x03 | Byte | Digital In Bitmask |
| `I2C_MEM_AO_1` | 4 | 0x04 | Word (mV) | 0-10V Out Ch1 |
| ... | ... | ... | ... | ... |
| `I2C_MEM_AI_1` | 28 | 0x1C | Word (mV) | 0-10V In Ch1 |

---

## 4. Implementation Plan (Next Steps)

1.  **RTC Sync:** Add `src/services/time_sync.py` to read Watchdog RTC on boot.
2.  **LED Manager:** Add `src/services/led_manager.py` to indicate system status on DAQ LEDs.
3.  **Button Monitor:** Add `src/services/power_monitor.py` to watch Watchdog button and trigger shutdown.
4.  **Sample Rate Config:** Expose `sample_rate` in `config.json` and apply to DAQ register 52.

---

**References:**
- [Sequent GitHub - Watchdog](https://github.com/SequentMicrosystems/wdt-rpi)
- [Sequent GitHub - 24b8vin](https://github.com/SequentMicrosystems/24b8vin-rpi)
- [Sequent GitHub - MegaIND](https://github.com/SequentMicrosystems/megaind-rpi)
