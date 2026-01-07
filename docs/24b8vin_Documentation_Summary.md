# 24b8vin Documentation Summary

**Date:** December 17, 2025  
**Author:** Cursor AI Documentation Engineer  
**Status:** ✅ Complete — Ready for CLI Testing & Implementation

---

## Executive Summary

Complete documentation package created for **Sequent Microsystems 24b8vin** (8-channel 24-bit analog input DAQ). All documentation is based on verified source code analysis and vendor documentation.

**Key Corrections Applied:**
1. ✅ **Clarified:** 24b8vin is **INPUT-ONLY** (no outputs of any kind)
2. ✅ **Corrected I2C addressing:** Base 0x31 (not 0x68), addresses 0x31..0x38 for stack IDs 0..7
3. ✅ **Documented gain codes:** 8 ranges from ±24V down to ±0.18V
4. ✅ **Separated settings:** Hardware-controllable vs physical-only (DIP switches) vs app-level
5. ✅ **Identified unknowns:** ADC sample rate, calibration procedure, diagnostics (require CLI testing)

---

## Deliverables (4 Documents Created)

### 1. **24b8vin_Hardware_Reference.md** (COMPREHENSIVE SPEC)
**Location:** `docs/24b8vin_Hardware_Reference.md`  
**Length:** ~1000 lines

**Contents:**
- **CRITICAL corrections:** What board IS and is NOT
- **Hardware stack configuration:** Physical order, I2C addressing table (0x31..0x38)
- **Complete feature list:**
  - 8 analog inputs (24-bit ADC, IEEE 754 float output)
  - Gain codes (0..7) with ranges ±24V..±0.18V
  - 8 LEDs (onboard indicators)
  - RTC (battery-backed real-time clock)
  - Watchdog (Pi power-cycle capability)
  - Firmware version
  - Diagnostics (temperature, Pi voltage — NOT in Python API)
  - RS485/MODBUS (optional, CLI-configured)
- **"Not Supported" section:** Explicitly lists NO outputs, NO excitation, NO digital I/O
- **Python library API:** Complete method list with confirmed signatures
- **CLI commands:** Basic commands + unknowns requiring testing
- **Troubleshooting guide:** I2C detection, voltage readings, address conflicts, watchdog

**Use Case:** Primary reference for developers and technicians

---

### 2. **24b8vin_Settings_Schema.json** (JSON SCHEMA)
**Location:** `docs/24b8vin_Settings_Schema.json`  
**Length:** ~300 lines JSON

**Contents:**
- **Formal JSON schema** with three sections:
  1. **hardware_settings:** I2C bus, stack ID, channels (enable, gain, label), LEDs, RTC, watchdog, firmware version, diagnostics
  2. **physical_settings:** DIP switches (stack ID, RS485 termination, TX/RX source), RS485/MODBUS config
  3. **app_settings:** UI refresh rate, read units, sampling config, channel display, logging
- **Commissioning section:** Installation date, technician, wiring notes, DIP photo, verification tests
- **Validation rules:** min/max, enums, required fields

**Use Case:** Backend developers implementing settings persistence and API

---

### 3. **24b8vin_Implementation_Notes.md** (DEV GUIDE)
**Location:** `docs/24b8vin_Implementation_Notes.md`  
**Length:** ~800 lines

**Contents:**
- **Python library detection:** How to check if SM24b8vin is installed
- **Service layer template:** Complete `Board24b8vinService` class with exception handling
- **Flask API routes:** 15+ endpoint examples (status, channels, gain, LEDs, RTC, watchdog)
- **Repository layer:** Suggested DB schema for settings persistence
- **Testing requirements:** 24-item commissioning checklist
- **Unknown features:** ADC sample rate, calibration, diagnostics (require CLI testing)
- **Safety rules:** Exception handling, gain changes, watchdog, channel enable/disable
- **UI layout suggestions:** Wireframe for settings page

**Use Case:** Backend/frontend developers implementing the settings page

---

### 4. **24b8vin_Quick_Reference.md** (TECH CHEAT SHEET)
**Location:** `docs/24b8vin_Quick_Reference.md`  
**Length:** ~300 lines

**Contents:**
- **Critical facts:** What board is/is not (1 page)
- **I2C addressing table:** Stack ID → I2C address mapping
- **Gain codes table:** 8 ranges with typical use cases
- **Python API cheat sheet:** Essential methods
- **CLI commands:** Basic usage examples
- **Troubleshooting:** 3 common issues with solutions
- **Commissioning checklist:** 12-item quick list
- **Default values table**

**Use Case:** Print-friendly reference for technicians and developers

---

## Key Facts (Hardware Truth)

### What 24b8vin IS:
- ✅ **8-channel differential analog INPUT DAQ**
- ✅ **24-bit ADC resolution** (IEEE 754 floating-point output in volts)
- ✅ **Software-selectable gain per channel** (8 ranges: ±24V .. ±0.18V)
- ✅ **Stackable up to 8 boards** (stack IDs 0..7)
- ✅ **I2C communication** (addresses 0x31..0x38)
- ✅ **LEDs, RTC, Watchdog, Firmware version**

### What 24b8vin is NOT:
- ❌ **NO analog outputs** (no 0–10V, no 4–20mA)
- ❌ **NO excitation outputs** (use external source like SlimPak Ultra)
- ❌ **NO digital I/O** (no opto inputs, no open-drain outputs)
- ❌ **NO load cell signal conditioning** (it's a raw differential voltage DAQ)

**For outputs → use MegaIND board** (separate settings page already documented)

---

## I2C Addressing (CORRECTED)

**⚠️ IMPORTANT CORRECTION:**  
User mentioned 0x68–0x6F, but source code confirms **0x31** base address.

**Verified from source code:**
```c
#define SLAVE_OWN_ADDRESS_BASE 0x31
```

**Calculation:**
```
I2C_Address = 0x31 + Stack_ID
```

**Table:**

| Stack ID | DIP (ID2 ID1 ID0) | I2C Address | Decimal |
|----------|-------------------|-------------|---------|
| 0 | OFF OFF OFF | 0x31 | 49 |
| 1 | OFF OFF ON  | 0x32 | 50 |
| 2 | OFF ON  OFF | 0x33 | 51 |
| 3 | OFF ON  ON  | 0x34 | 52 |
| 4 | ON  OFF OFF | 0x35 | 53 |
| 5 | ON  OFF ON  | 0x36 | 54 |
| 6 | ON  ON  OFF | 0x37 | 55 |
| 7 | ON  ON  ON  | 0x38 | 56 |

---

## Settings Schema (3-Level Separation)

### A) Hardware-Level Settings (Software-Controllable via I2C/Python)

| Setting | Writable? | Range | Notes |
|---------|-----------|-------|-------|
| **stack_id** | No (physical DIP) | 0..7 | Must match DIP switches |
| **channel[1..8].gain_code** | Yes | 0..7 | 8 ranges: ±24V..±0.18V |
| **channel[1..8].enabled** | App-level | true/false | Hardware always samples; software ignores if disabled |
| **leds[1..8]** | Yes | on/off | Onboard indicators |
| **rtc** | Yes | date/time | Battery-backed |
| **watchdog.period** | Yes | 10..65000s | 65000 = disabled |
| **firmware_version** | No (read-only) | "major.minor" | e.g., "1.1" |

### B) Physical-Only Settings (DIP Switches — UI Display/Record ONLY)

| Setting | UI Can Change? | Notes |
|---------|----------------|-------|
| **Stack ID DIPs (ID2, ID1, ID0)** | ❌ NO | Set BEFORE power-on. UI warns if mismatch. |
| **RS485 Termination** | ❌ NO | 120Ω resistor enable (last device on bus) |
| **RS485 TX/RX Source** | ❌ NO | Board-specific DIP (consult silkscreen) |

**⚠️ UI Constraint:** DIP switches are **PHYSICAL**. UI should:
- Display expected DIP configuration
- Allow tech to record actual DIP positions during commissioning
- Warn if software stack_id ≠ calculated stack_id from DIPs

### C) App-Level Settings (Not Hardware Features)

| Setting | Default | Notes |
|---------|---------|-------|
| **ui_refresh_rate_hz** | 2.0 | How often UI polls board |
| **acquisition_loop_rate_hz** | 10.0 | Background thread rate |
| **adc_sample_rate_code** | 0 (250sps) | **UNKNOWN** if writable via I2C register 43 |
| **show_disabled_channels** | false | Display grayed-out in UI |
| **log_gain_changes** | true | Log to events table |

---

## Python API (Confirmed from Source Code)

### Installation
```bash
sudo pip3 install SM24b8vin
```

### Confirmed Methods (from `SM24b8vin/__init__.py`)

| Method | Parameters | Returns | Status |
|--------|------------|---------|--------|
| `get_u_in(channel)` | ch=1..8 | float (volts) | ✅ CONFIRMED |
| `set_gain(channel, gain)` | ch=1..8, gain=0..7 | None | ✅ CONFIRMED |
| `get_gain(channel)` | ch=1..8 | int (0..7) | ✅ CONFIRMED |
| `set_led(led, state)` | led=1..8, state=0/1 | None | ✅ CONFIRMED |
| `get_led(led)` | led=1..8 | int (0/1) | ✅ CONFIRMED |
| `set_all_leds(bitmask)` | bitmask=0..255 | None | ✅ CONFIRMED |
| `get_all_leds()` | None | int (bitmask) | ✅ CONFIRMED |
| `get_rtc()` | None | tuple (y,mo,d,h,m,s) | ✅ CONFIRMED |
| `set_rtc(year, month, day, hour, minute, second)` | Full year | None | ✅ CONFIRMED |
| `wdt_reload()` | None | None | ✅ CONFIRMED |
| `wdt_get_period()` | None | int (seconds) | ✅ CONFIRMED |
| `wdt_set_period(period)` | period (seconds) | None | ✅ CONFIRMED |
| `wdt_get_init_period()` | None | int (seconds) | ✅ CONFIRMED |
| `wdt_set_init_period(period)` | period (seconds) | None | ✅ CONFIRMED |
| `wdt_get_off_period()` | None | int (seconds) | ✅ CONFIRMED |
| `wdt_set_off_period(period)` | period (seconds) | None | ✅ CONFIRMED |
| `wdt_get_reset_count()` | None | int | ✅ CONFIRMED |
| `wdt_clear_reset_count()` | None | None | ✅ CONFIRMED |
| `get_version()` | None | str ("major.minor") | ✅ CONFIRMED |

**Total:** 20 confirmed methods

---

## Features NOT in Python API (Require CLI or Direct I2C)

| Feature | I2C Register | Access Method | Status |
|---------|--------------|---------------|--------|
| **ADC Sample Rate** | Address 43 | Direct I2C write or CLI | ❓ UNKNOWN if CLI command exists |
| **Board Temperature** | Address 43 | Direct I2C read | ❓ NOT in Python API |
| **Pi Voltage** | Address 44-45 | Direct I2C read | ❓ NOT in Python API |
| **Calibration Procedure** | Addresses 86-92 | CLI: `24b8vin <id> calstat` | ❓ UNKNOWN full procedure |
| **RS485 Config** | Address 81+ | CLI: `24b8vin <id> cfg485wr ...` | ✅ CONFIRMED (CLI only) |

---

## ACTION REQUIRED (Before UI Implementation)

### 🔬 CLI Testing (CRITICAL)

**Run on Raspberry Pi:**
```bash
# 1. Get full CLI help
24b8vin -h
# → Document all commands

# 2. Test sample rate commands (if exist)
24b8vin 0 <sample_rate_command> ?

# 3. Test calibration commands
24b8vin 0 calstat          # Already confirmed
24b8vin 0 <calibrate_command> ?

# 4. Test diagnostics commands (temperature, Pi voltage)
24b8vin 0 <diag_command> ?

# 5. Verify RS485 config
24b8vin 0 cfg485rd         # Read current config
24b8vin 0 cfg485wr 1 1 9600 1 0  # Write config
```

**Document Results:**
- Create: `docs/24b8vin_CLI_Commands.md`
- List all discovered commands with syntax and examples
- Update implementation plan based on CLI capabilities

---

## Implementation Phases

### Phase 1: Backend (Service + API)
1. Install Python library: `sudo pip3 install SM24b8vin`
2. Create `src/hw/board_24b8vin_service.py` (service class)
3. Create `src/db/board_24b8vin_repo.py` (repository class)
4. Add Flask routes to `src/app/routes.py` (15+ endpoints)
5. Extend DB schema with 24b8vin tables
6. Unit tests (simulated hardware mode)

### Phase 2: Frontend (Settings Page)
1. Create template: `src/app/templates/scale_settings_24b8vin.html`
2. Implement sections:
   - Board status (online, firmware, I2C address)
   - Analog inputs (8 channels with live readings + gain dropdowns)
   - LEDs (8 toggles)
   - RTC (current time + sync button)
   - Watchdog (period, reset count, reload button)
   - Physical settings (DIP display + warning if mismatch)
3. Add JavaScript for live updates (polling or SSE)
4. Implement logging (log every gain change, I2C error)

### Phase 3: Integration & Testing
1. Test on bench with simulated hardware
2. Test on Pi with real 24b8vin hardware (24-item checklist)
3. Test all 8 channels with precision voltage source
4. Test all 8 gain codes
5. Verify LEDs, RTC, watchdog
6. Commission on-site with real load cells
7. Train maintenance technicians

### Phase 4: Documentation Updates
1. Update `24b8vin_CLI_Commands.md` after testing
2. Add screenshots to maintenance manual
3. Create operator training materials (if needed)

---

## Testing Checklist (24 Items)

### Commissioning Tests
- [ ] I2C enabled: `sudo raspi-config`
- [ ] I2C detect: `sudo i2cdetect -y 1`
- [ ] Board appears at expected address (0x31 + stack_id)
- [ ] Python library installed: `pip3 list | grep SM24b8vin`
- [ ] DIP switches match software stack_id
- [ ] Photo of DIP switches taken

### Analog Input Tests (per channel)
- [ ] Connect precision voltage source
- [ ] Test gain code 0 (±24V) with 10V input
- [ ] Test gain code 2 (±6V) with 5V input
- [ ] Test gain code 6 (±0.37V) with 100mV input
- [ ] Test gain code 7 (±0.18V) with 50mV input
- [ ] Verify readings match expected within ±1%
- [ ] Test all 8 channels with same procedure

### LED Tests
- [ ] Toggle each LED 1..8 individually
- [ ] Test `set_all_leds()` with bitmask 0b10101010
- [ ] Verify LEDs visible on physical board

### RTC Tests
- [ ] Set RTC to known date/time
- [ ] Read back and verify
- [ ] Power-cycle Pi
- [ ] Verify RTC retained time (battery-backed)

### Watchdog Tests
- [ ] Set period to 30s
- [ ] Call `wdt_reload()` every 20s for 2 minutes
- [ ] Verify Pi does NOT power-cycle
- [ ] Stop calling `wdt_reload()`
- [ ] Verify Pi DOES power-cycle after 30s
- [ ] Check reset count incremented

### Firmware Version
- [ ] Read firmware version: `board.get_version()`
- [ ] Document version in commissioning record

---

## Safety & Best Practices

### 1. Exception Handling
```python
try:
    voltage = board.get_u_in(1)
except Exception as e:
    logging.error(f"I2C error reading CH1: {e}")
    # Increment diagnostics.i2c_errors_count
    # Display error in UI
```

### 2. Gain Code Changes
```python
# Before changing gain, warn if signal will clip
current_voltage = board.get_u_in(channel)
new_range = gain_code_to_range(new_gain_code)
if abs(current_voltage) > new_range:
    warn_user(f"Signal {current_voltage}V will clip at {new_range}V")

# Log every gain change
log_event("24b8vin", "gain_change", channel, old_gain, new_gain, user, timestamp)
```

### 3. Watchdog Safety
```python
# Default: DISABLED
default_period = 65000  # Special value to disable

# Enable only after confirming background service will reload
if enable_watchdog:
    warn_user("Watchdog will power-cycle Pi if not reloaded every N seconds")
    board.wdt_set_period(120)  # 2 minutes
```

### 4. Channel Enable/Disable
```python
# App-level only — hardware always samples
if channel_config["enabled"]:
    voltage = board.get_u_in(channel)
    # Process voltage (filtering, totals, etc.)
else:
    # Ignore channel (hardware still samples, but software doesn't use it)
    pass
```

### 5. DIP Switch Mismatch Warning
```python
software_stack_id = config["stack_id"]
dip_stack_id = (id2 << 2) | (id1 << 1) | id0

if software_stack_id != dip_stack_id:
    warn_user(f"⚠️ DIP mismatch: Software={software_stack_id}, DIPs={dip_stack_id}")
```

---

## Frequently Asked Questions

### Q: Can I control analog outputs with 24b8vin?
**A:** ❌ **NO.** 24b8vin is INPUT-ONLY. For outputs, use MegaIND board.

### Q: What's the I2C address for stack ID 0?
**A:** `0x31` (decimal 49). Formula: `0x31 + stack_id`.

### Q: Can I change gain code without stopping acquisition?
**A:** ✅ **YES.** Gain changes take effect immediately. ADC continues sampling.

### Q: How do I disable a channel?
**A:** **App-level only.** Set `channel_enabled=false` in config. Hardware continues sampling; software ignores the data.

### Q: Can I change DIP switches in software?
**A:** ❌ **NO.** DIP switches are PHYSICAL. UI can only display expected values and warn if mismatch detected.

### Q: What's the default watchdog period?
**A:** **Disabled** (period = 65000, special value). Enable by setting period <65000.

### Q: Can I read board temperature via Python API?
**A:** ❌ **NOT in Python API.** Requires direct I2C read from register 43. (Action required: test CLI for temperature command)

---

## References

### New Documents (This Deliverable)
- **Hardware Ref:** `docs/24b8vin_Hardware_Reference.md` (comprehensive spec)
- **Settings Schema:** `docs/24b8vin_Settings_Schema.json` (JSON schema)
- **Implementation:** `docs/24b8vin_Implementation_Notes.md` (dev guide)
- **Quick Ref:** `docs/24b8vin_Quick_Reference.md` (cheat sheet)
- **This Summary:** `docs/24b8vin_Documentation_Summary.md` (executive summary)

### External References
- **Product Page:** https://sequentmicrosystems.com/products/eight-24-bit-analog-inputs-daq-8-layer-stackable-hat-for-raspberry-pi
- **GitHub Repo:** https://github.com/SequentMicrosystems/24b8vin-rpi
- **PyPI Package:** https://pypi.org/project/SM24b8vin/
- **Source Code (Local):** `.vendor/24b8vin-rpi/` (vendor-provided)
- **Modbus Docs:** `.vendor/24b8vin-rpi/MODBUS.md`

---

## Approval & Sign-Off

**Documentation Review:**
- [ ] Maintenance Team Lead: _____________________ Date: _______
- [ ] Electrical/Controls Engineer: _____________________ Date: _______
- [ ] Software Lead: _____________________ Date: _______
- [ ] Project Manager: _____________________ Date: _______

**Action Items Before Implementation:**
- [ ] **CLI Testing Complete:** All commands documented
- [ ] **Calibration Procedure Confirmed:** Step-by-step instructions
- [ ] **Sample Rate Control Verified:** CLI command or direct I2C
- [ ] **Diagnostics Access Tested:** Temperature, Pi voltage

**Implementation Authorization:**
- [ ] Approved to proceed with Phase 1 (Backend)
- [ ] Approved to proceed with Phase 2 (Frontend)
- [ ] Approved to proceed with Phase 3 (Integration & Testing)

---

**Document Version:** 1.0  
**Last Updated:** December 17, 2025  
**Next Review:** After CLI testing complete
