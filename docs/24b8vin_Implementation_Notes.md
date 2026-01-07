# 24b8vin Implementation Notes
**For Settings Page Development (Backend + Frontend)**

**Document Version:** 1.1  
**Date:** December 19, 2025  
**Status:** Implemented (core DAQ settings integrated into `/settings`; some board-only features remain CLI-only)

---

## Summary

This document records the 24b8vin (8-channel analog input DAQ) settings implementation status and remaining gaps. Core DAQ settings are now integrated into the main `/settings` page.

**Related Documents:**
- `24b8vin_Hardware_Reference.md` — Complete hardware specifications
- `24b8vin_Settings_Schema.json` — JSON schema for settings structure

---

## Key Facts (Quick Reference)

### What 24b8vin IS:
- ✅ 8-channel differential analog **INPUT** DAQ
- ✅ 24-bit ADC resolution (IEEE 754 floating-point output)
- ✅ Software-selectable gain per channel (8 ranges: ±24V down to ±0.18V)
- ✅ Stackable up to 8 boards (stack IDs 0..7)
- ✅ I2C communication (addresses 0x31..0x38)

### What 24b8vin is NOT:
- ❌ NO analog outputs (no 0–10V, no 4–20mA outputs)
- ❌ NO excitation outputs
- ❌ NO digital I/O (no opto inputs, no open-drain outputs)

**If you need outputs, use MegaIND board** (separate settings page).

---

## Python Library: SM24b8vin

### Installation Verification
```python
import importlib.util

spec = importlib.util.find_spec("SM24b8vin")
if spec is None:
    print("SM24b8vin not installed. Run: sudo pip3 install SM24b8vin")
else:
    print("SM24b8vin library available")
    import SM24b8vin
```

### Basic Initialization
```python
import SM24b8vin

try:
    # Initialize board (stack=0, i2c_bus=1)
    board = SM24b8vin.SM24b8vin(stack=0, i2c=1)
    print("Board online")
except Exception as e:
    print(f"Board offline: {e}")
```

### Confirmed API Methods (from source code analysis)

| Method | Parameters | Returns | Notes |
|--------|------------|---------|-------|
| `get_u_in(channel)` | channel=1..8 | float (volts) | ✅ CONFIRMED |
| `get_gain(channel)` | channel=1..8 | int (0..7) | ✅ CONFIRMED |
| `set_gain(channel, gain)` | channel=1..8, gain=0..7 | None | ✅ CONFIRMED |
| `get_led(led)` | led=1..8 | int (0 or 1) | ✅ CONFIRMED |
| `set_led(led, state)` | led=1..8, state=0 or 1 | None | ✅ CONFIRMED |
| `get_all_leds()` | None | int (bitmask) | ✅ CONFIRMED |
| `set_all_leds(bitmask)` | bitmask=0..255 | None | ✅ CONFIRMED |
| `get_rtc()` | None | tuple (y, mo, d, h, m, s) | ✅ CONFIRMED |
| `set_rtc(year, month, day, hour, minute, second)` | Full year (e.g., 2025) | None | ✅ CONFIRMED |
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

### Features NOT in Python API (Require CLI or Direct I2C)

| Feature | I2C Register | Access Method | Status |
|---------|--------------|---------------|--------|
| **ADC Sample Rate** | Address 43 | CLI: `24b8vin <id> srrd` / `24b8vin <id> srwr <code>` or direct I2C | ✅ CONFIRMED (CLI) |
| **Board Temperature** | Address 43 | Direct I2C read | ❓ NOT in Python API |
| **Pi Voltage** | Address 44-45 | Direct I2C read | ❓ NOT in Python API |
| **Calibration** | Addresses 86-92 | CLI: `24b8vin <id> calstat` | ❓ UNKNOWN full procedure |
| **RS485 Config** | Address 81+ | CLI: `24b8vin <id> cfg485wr ...` | ✅ CONFIRMED (CLI only) |

**ACTION REQUIRED (Before UI Implementation):**
1. Run `24b8vin -h` on Raspberry Pi to discover all CLI commands
2. Test calibration commands (if exist)
3. Test sample rate commands (`srrd` / `srwr`)
4. Document CLI command syntax for missing features

---

## Backend Service Layer

### Suggested File Structure
```
src/hw/
├── board_24b8vin_service.py       ← Service class (hardware abstraction)
└── interfaces.py                   ← Interface definitions

src/db/
└── board_24b8vin_repo.py          ← Repository for settings persistence

src/app/
└── routes.py                       ← Flask routes for 24b8vin API
```

### Service Class Template

**File:** `src/hw/board_24b8vin_service.py`

```python
import SM24b8vin
import logging
from typing import Optional, List, Tuple

class Board24b8vinService:
    """
    Service class for 24b8vin board (8-channel analog input DAQ).
    Provides hardware abstraction and exception handling.
    """
    
    def __init__(self, stack_id: int = 0, i2c_bus: int = 1):
        self.stack_id = stack_id
        self.i2c_bus = i2c_bus
        self.i2c_address = 0x31 + stack_id
        self.board: Optional[SM24b8vin.SM24b8vin] = None
        self.online = False
        self._initialize()
    
    def _initialize(self):
        """Initialize board connection."""
        try:
            self.board = SM24b8vin.SM24b8vin(stack=self.stack_id, i2c=self.i2c_bus)
            self.online = True
            logging.info(f"24b8vin board initialized (stack {self.stack_id}, address 0x{self.i2c_address:02x})")
        except Exception as e:
            self.online = False
            logging.error(f"24b8vin board NOT detected (stack {self.stack_id}): {e}")
    
    def is_online(self) -> bool:
        """Check if board is online."""
        return self.online
    
    def get_i2c_address(self) -> str:
        """Get I2C address as hex string."""
        return f"0x{self.i2c_address:02x}"
    
    # --- Analog Inputs ---
    
    def read_channel(self, channel: int) -> float:
        """
        Read voltage for channel 1..8.
        Raises RuntimeError if board offline.
        """
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.get_u_in(channel)
    
    def read_all_channels(self) -> List[float]:
        """
        Read all 8 channels.
        Returns list of 8 voltages [ch1, ch2, ..., ch8].
        """
        if not self.online:
            raise RuntimeError("Board offline")
        return [self.board.get_u_in(ch) for ch in range(1, 9)]
    
    # --- Gain Control ---
    
    def set_gain(self, channel: int, gain_code: int):
        """Set gain code (0..7) for channel 1..8."""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.set_gain(channel, gain_code)
        logging.info(f"24b8vin: Set CH{channel} gain={gain_code}")
    
    def get_gain(self, channel: int) -> int:
        """Get gain code for channel 1..8."""
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.get_gain(channel)
    
    def get_all_gains(self) -> List[int]:
        """Get gain codes for all 8 channels."""
        if not self.online:
            raise RuntimeError("Board offline")
        return [self.board.get_gain(ch) for ch in range(1, 9)]
    
    @staticmethod
    def gain_code_to_range(gain_code: int) -> str:
        """Convert gain code to human-readable range string."""
        ranges = {
            0: "±24V",
            1: "±12V",
            2: "±6V",
            3: "±3V",
            4: "±1.5V",
            5: "±0.75V",
            6: "±0.37V",
            7: "±0.18V"
        }
        return ranges.get(gain_code, "Unknown")
    
    # --- LEDs ---
    
    def set_led(self, led: int, state: bool):
        """Set LED 1..8 on/off."""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.set_led(led, 1 if state else 0)
    
    def get_led(self, led: int) -> bool:
        """Get LED 1..8 state."""
        if not self.online:
            raise RuntimeError("Board offline")
        return bool(self.board.get_led(led))
    
    def set_all_leds(self, bitmask: int):
        """Set all LEDs at once (0..255)."""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.set_all_leds(bitmask)
    
    def get_all_leds(self) -> int:
        """Get all LED states as bitmask."""
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.get_all_leds()
    
    # --- RTC ---
    
    def get_rtc(self) -> Tuple[int, int, int, int, int, int]:
        """Get RTC date/time: (year, month, day, hour, minute, second)."""
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.get_rtc()
    
    def set_rtc(self, year: int, month: int, day: int, hour: int, minute: int, second: int):
        """Set RTC date/time."""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.set_rtc(year, month, day, hour, minute, second)
        logging.info(f"24b8vin: RTC set to {year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}")
    
    # --- Watchdog ---
    
    def wdt_reload(self):
        """Reload (pet) watchdog timer."""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.wdt_reload()
    
    def wdt_get_period(self) -> int:
        """Get watchdog period (seconds)."""
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.wdt_get_period()
    
    def wdt_set_period(self, period: int):
        """Set watchdog period (seconds). 65000=disable."""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.wdt_set_period(period)
        logging.info(f"24b8vin: Watchdog period set to {period}s")
    
    def wdt_get_reset_count(self) -> int:
        """Get watchdog reset count."""
        if not self.online:
            raise RuntimeError("Board offline")
        return self.board.wdt_get_reset_count()
    
    def wdt_clear_reset_count(self):
        """Clear watchdog reset count."""
        if not self.online:
            raise RuntimeError("Board offline")
        self.board.wdt_clear_reset_count()
        logging.info("24b8vin: Watchdog reset count cleared")
    
    # --- Firmware Version ---
    
    def get_firmware_version(self) -> str:
        """Get firmware version string (e.g., '1.1')."""
        if not self.online:
            return "N/A"
        return self.board.get_version()
```

---

## Flask API Routes

### Suggested Routes

**File:** `src/app/routes.py` (add to existing routes)

```python
from flask import jsonify, request
from src.hw.board_24b8vin_service import Board24b8vinService

# Initialize service (stack_id from config or DB)
board_24b8vin = Board24b8vinService(stack_id=0, i2c_bus=1)

# --- Status & Diagnostics ---

@app.route('/api/24b8vin/status', methods=['GET'])
def get_24b8vin_status():
    """Get board status (online, firmware version, I2C address)."""
    return jsonify({
        'online': board_24b8vin.is_online(),
        'stack_id': board_24b8vin.stack_id,
        'i2c_address': board_24b8vin.get_i2c_address(),
        'firmware_version': board_24b8vin.get_firmware_version()
    })

# --- Analog Inputs ---

@app.route('/api/24b8vin/channels', methods=['GET'])
def get_24b8vin_channels():
    """Get all channel readings (voltage + gain)."""
    try:
        voltages = board_24b8vin.read_all_channels()
        gains = board_24b8vin.get_all_gains()
        return jsonify({
            'channels': [
                {
                    'channel': ch,
                    'voltage': voltages[ch-1],
                    'gain_code': gains[ch-1],
                    'gain_range': board_24b8vin.gain_code_to_range(gains[ch-1])
                }
                for ch in range(1, 9)
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/24b8vin/channel/<int:channel>', methods=['GET'])
def get_24b8vin_channel(channel):
    """Get single channel reading."""
    try:
        voltage = board_24b8vin.read_channel(channel)
        gain_code = board_24b8vin.get_gain(channel)
        return jsonify({
            'channel': channel,
            'voltage': voltage,
            'gain_code': gain_code,
            'gain_range': board_24b8vin.gain_code_to_range(gain_code)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Gain Control ---

@app.route('/api/24b8vin/channel/<int:channel>/gain', methods=['POST'])
def set_24b8vin_gain(channel):
    """Set gain code for channel."""
    gain_code = request.json.get('gain_code')
    if gain_code is None or not (0 <= gain_code <= 7):
        return jsonify({'error': 'Invalid gain_code (must be 0..7)'}), 400
    try:
        board_24b8vin.set_gain(channel, gain_code)
        # TODO: Log change to events table
        return jsonify({'success': True, 'channel': channel, 'gain_code': gain_code})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- LEDs ---

@app.route('/api/24b8vin/leds', methods=['GET'])
def get_24b8vin_leds():
    """Get all LED states."""
    try:
        bitmask = board_24b8vin.get_all_leds()
        leds = {f'led_{i}': bool(bitmask & (1 << (i-1))) for i in range(1, 9)}
        return jsonify(leds)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/24b8vin/led/<int:led>', methods=['POST'])
def set_24b8vin_led(led):
    """Set single LED on/off."""
    state = request.json.get('state')
    if state is None:
        return jsonify({'error': 'Missing state (true/false)'}), 400
    try:
        board_24b8vin.set_led(led, bool(state))
        return jsonify({'success': True, 'led': led, 'state': bool(state)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- RTC ---

@app.route('/api/24b8vin/rtc', methods=['GET'])
def get_24b8vin_rtc():
    """Get RTC date/time."""
    try:
        year, month, day, hour, minute, second = board_24b8vin.get_rtc()
        return jsonify({
            'year': year,
            'month': month,
            'day': day,
            'hour': hour,
            'minute': minute,
            'second': second,
            'iso_8601': f"{year}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/24b8vin/rtc/sync-to-system', methods=['POST'])
def sync_24b8vin_rtc_to_system():
    """Sync RTC to Raspberry Pi system time."""
    import datetime
    try:
        now = datetime.datetime.now()
        board_24b8vin.set_rtc(now.year, now.month, now.day, now.hour, now.minute, now.second)
        return jsonify({'success': True, 'synced_to': now.isoformat()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- Watchdog ---

@app.route('/api/24b8vin/watchdog', methods=['GET'])
def get_24b8vin_watchdog():
    """Get watchdog status."""
    try:
        return jsonify({
            'period_seconds': board_24b8vin.wdt_get_period(),
            'reset_count': board_24b8vin.wdt_get_reset_count()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/24b8vin/watchdog/reload', methods=['POST'])
def reload_24b8vin_watchdog():
    """Reload (pet) watchdog."""
    try:
        board_24b8vin.wdt_reload()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/24b8vin/watchdog/period', methods=['POST'])
def set_24b8vin_watchdog_period():
    """Set watchdog period."""
    period = request.json.get('period_seconds')
    if period is None or not (10 <= period <= 65000):
        return jsonify({'error': 'Invalid period (10..65000 seconds)'}), 400
    try:
        board_24b8vin.wdt_set_period(period)
        return jsonify({'success': True, 'period_seconds': period})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

---

## Repository Layer (Settings Persistence)

### Suggested Schema Extension

**File:** `src/db/schema.py` (add new tables)

```python
# 24b8vin board settings table
CREATE TABLE IF NOT EXISTS board_24b8vin_settings (
    id INTEGER PRIMARY KEY,
    stack_id INTEGER NOT NULL,
    i2c_bus INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# 24b8vin channel configuration
CREATE TABLE IF NOT EXISTS board_24b8vin_channels (
    id INTEGER PRIMARY KEY,
    channel INTEGER NOT NULL CHECK(channel >= 1 AND channel <= 8),
    enabled BOOLEAN DEFAULT 1,
    gain_code INTEGER DEFAULT 0 CHECK(gain_code >= 0 AND gain_code <= 7),
    label TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# 24b8vin commissioning record
CREATE TABLE IF NOT EXISTS board_24b8vin_commissioning (
    id INTEGER PRIMARY KEY,
    installation_date DATE,
    installed_by TEXT,
    physical_location TEXT,
    wiring_notes TEXT,
    dip_switch_photo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

# 24b8vin events log
CREATE TABLE IF NOT EXISTS board_24b8vin_events (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,  -- 'gain_change', 'i2c_error', 'watchdog_reload', etc.
    channel INTEGER,
    old_value TEXT,
    new_value TEXT,
    user TEXT,
    notes TEXT
);
```

---

## Testing Requirements (Before Production)

### Commissioning Tests

1. **I2C Detection**
   - [ ] Run `sudo i2cdetect -y 1`
   - [ ] Verify board appears at expected address (0x31 + stack_id)
   - [ ] Verify no address conflicts

2. **Analog Input Tests**
   - [ ] Connect precision voltage source to CH1
   - [ ] Test all 8 gain codes with known reference voltages
   - [ ] Verify readings match expected values within tolerance
   - [ ] Test all 8 channels with same procedure

3. **Gain Code Verification**
   ```python
   # Test gain code 6 (±370mV range) with 100mV input
   board.set_gain(1, 6)
   voltage = board.get_u_in(1)
   assert 0.095 <= voltage <= 0.105, f"Expected ~0.1V, got {voltage}V"
   ```

4. **LED Test**
   - [ ] Toggle each LED 1..8 individually
   - [ ] Test `set_all_leds()` with various bitmasks
   - [ ] Verify LEDs visible on physical board

5. **RTC Test**
   - [ ] Set RTC to known date/time
   - [ ] Read back and verify
   - [ ] Power-cycle Pi
   - [ ] Verify RTC retained time (battery-backed)

6. **Watchdog Test**
   - [ ] Set watchdog period to 30s
   - [ ] Call `wdt_reload()` every 20s
   - [ ] Verify Pi does NOT power-cycle
   - [ ] Stop calling `wdt_reload()`
   - [ ] Verify Pi DOES power-cycle after 30s

7. **Firmware Version**
   - [ ] Read firmware version
   - [ ] Document version in commissioning record

---

## Unknown Features (Requires CLI Testing)

### Action Required: Run These Tests on Pi

```bash
# 1. Get full CLI help
24b8vin -h

# Expected output: list of all commands
# Document any commands not in Python API

# 2. Test sample rate commands (sample rate control)
24b8vin 0 srrd        # Read current sample rate (Hz)
24b8vin 0 srwr 2      # Example: set sample rate code to 2 (1 kHz)

# 3. Test calibration commands
24b8vin 0 calstat          # Already confirmed
24b8vin 0 <calibrate_command> ?

# 4. Test diagnostics commands (temperature, Pi voltage)
24b8vin 0 <diag_command> ?

# 5. Test RS485 config
24b8vin 0 cfg485rd         # Read current config
24b8vin 0 cfg485wr 1 1 9600 1 0  # Write config
```

**Document Results:**
- Create file: `docs/24b8vin_CLI_Commands.md`
- List all discovered commands with syntax and examples
- Update implementation plan based on CLI capabilities

---

## Safety & Best Practices

### 1. Exception Handling
- **Always** wrap board calls in try/except
- Log I2C errors to events table
- Display user-friendly error messages in UI
- Increment `diagnostics.i2c_errors_count` on error

### 2. Gain Code Changes
- **Always** log gain code changes (who, when, old, new)
- Warn user if gain change will clip current input signal
- Example: CH1 reads 5V with gain 0 (±24V). If user sets gain 4 (±1.5V), warn that signal will clip.

### 3. Watchdog Safety
- **Default:** Watchdog DISABLED (period = 65000)
- Enable watchdog ONLY after confirming background service will call `wdt_reload()`
- Warn user: "Watchdog will power-cycle Pi if not reloaded every N seconds"

### 4. Channel Enable/Disable
- **App-level only** — hardware cannot disable channels
- When channel disabled: ignore in acquisition loop, totals, filtering, drift checks
- Display disabled channels as grayed-out in UI

### 5. DIP Switch Mismatch Warning
- If `hardware_settings.stack_id != physical_settings.calculated_stack_id`:
  - Display warning banner: "⚠️ DIP switch mismatch detected. Software expects stack ID X, but DIPs are set to Y."
  - Prompt user to correct DIPs or update software config

---

## UI Layout Suggestions (Implemented)

### Settings Page Structure

**Page:** `/settings`

**Layout:**
```
┌─────────────────────────────────────────┐
│ Settings → DAQ Channels tab             │
│ (24b8vin channel enable/role/gain)      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Analog Inputs (8 Channels)              │
│ ┌─────────────────────────────────────┐ │
│ │ CH1: [✓] Label: [Load Cell FL    ] │ │
│ │      Voltage: 0.028 V               │ │
│ │      Gain: [6] ±0.37V               │ │
│ │      [Change Gain ▼]                │ │
│ └─────────────────────────────────────┘ │
│ (repeat for CH2..CH8)                   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ LEDs                                   │
│ Present in Settings (disableable)       │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ RTC (Real-Time Clock)                   │
│ Current Time: 2025-12-17 14:32:05      │
│ [Sync to System Time]                   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Watchdog Timer                          │
│ Present in Settings (disableable)       │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Physical Settings (DIP Switches)        │
│ ⚠️ These settings are PHYSICAL and     │
│    cannot be changed in software.      │
│                                         │
│ Stack ID DIPs: ID2[OFF] ID1[OFF] ID0[OFF]│
│ Calculated: Stack ID 0, I2C 0x31       │
│ [Record Actual DIP Positions]          │
└─────────────────────────────────────────┘
```

---

## Next Steps

1. **CLI Testing** (CRITICAL)
   - Run `24b8vin -h` on Raspberry Pi
   - Document all commands
   - Test sample rate, calibration, diagnostics commands

2. **Backend Implementation**
   - Create `Board24b8vinService` class
   - Create Flask API routes
   - Extend DB schema for settings persistence

3. **Frontend Implementation**
   - Create settings page template
   - Implement live channel readings (polling or SSE)
   - Implement gain code dropdowns with range display
   - Implement LED toggles
   - Implement RTC sync button
   - Implement watchdog controls

4. **Testing**
   - Commission test (24-item checklist)
   - Integration test with acquisition loop
   - Multi-board test (if stacking multiple 24b8vin boards)

5. **Documentation Updates**
   - Update `24b8vin_CLI_Commands.md` after testing
   - Update implementation notes with discovered features
   - Create user manual for maintenance technicians

---

**Document Version:** 1.1  
**Last Updated:** December 19, 2025  
**Status:** Implemented (core DAQ settings); remaining items tracked for future work
