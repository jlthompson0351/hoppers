# Opto Input Monitoring — Basket Dump Detection

## Status: ACTIVE IN PRODUCTION (since 2026-03-24)

## Overview
Channel 1 of the MegaInd (stack 2) opto-isolated digital input is wired to the basket dump mechanism. Each basket dump cycle produces **two** signal transitions:
1. Basket rotates down to dump → signal goes HIGH
2. Basket rotates back up → signal goes LOW

**Therefore: every 2 transitions = 1 actual basket dump.**

## Hardware Setup

| Item | Value |
|------|-------|
| Board | Sequent MegaInd, stack ID 2, I2C addr 0x52, firmware 4.8 |
| Input Channel | 1 (opto-isolated digital input) |
| Signal Voltage | 24V DC from PLC |
| Wiring (IMPORTANT) | **VEX1 = POSITIVE (+24V), IN1 = NEGATIVE (ground)** |
| Polarity Note | This is REVERSED from what the V5.0 schematic shows. The schematic says IN=anode, VEX=cathode but the actual board requires VEX=positive, IN=negative to light the LED. Confirmed working 2026-03-24. |
| Signal Duration | Brief pulse (~10-15 seconds per dump rotation, two pulses per dump cycle) |
| Edge Detection | Set to mode 3 (both rising and falling edges) |

## Software Setup

### Hardware Edge Counter
The MegaInd has a built-in hardware transition counter that catches pulses even if they're too brief for polling to detect:
```bash
# Enable edge detection (both rising + falling)
megaind 2 edgewr 1 3

# Read transition count
megaind 2 countrd 1

# Reset counter (DO NOT DO IN PRODUCTION WITHOUT REASON)
megaind 2 countrst 1

# Read current state
megaind 2 optord 1
```

### Monitor Script
A background Python script runs on the Pi to log all transitions:
- **Location on Pi:** `/tmp/opto_monitor.py`
- **Source:** `/root/.openclaw/workspace-argus/scripts/opto_monitor.py` (on VPS)
- **Log file:** `/tmp/opto_ch1_log.csv`
- **PID:** Started manually, not yet a systemd service
- **Poll interval:** 250ms

### CSV Log Format
```
timestamp_utc,counter,delta,estimated_dumps
2026-03-24T16:49:17.980205+00:00,1,1,0
2026-03-24T16:49:24.069663+00:00,2,1,1
```

## Known Issues
1. **Counter resets:** The hardware counter appears to auto-reset periodically (possibly when the acquisition loop reads it via the Python library). This causes negative deltas in the CSV. The transitions are still captured — just need smarter accounting in the monitor script.
2. **Not yet a systemd service:** Monitor script was started with `nohup` — will not survive a Pi reboot. Needs to be converted to a proper systemd service.
3. **Not yet integrated into the main acquisition loop:** Currently running as a standalone script alongside the main `loadcell-transmitter` service.

## Future Work
- [ ] Convert monitor to a systemd service so it survives reboots
- [ ] Integrate opto signal into the main acquisition loop (`src/services/acquisition.py`)
- [ ] Use the opto signal as a hard dump trigger instead of relying on weight curve detection
- [ ] Correlate opto transitions with weight data to validate dump detection accuracy
- [ ] Debounce logic: pair transitions into dump events (2 transitions within ~30s = 1 dump)
- [ ] Dashboard: show opto-based dump count alongside weight-based dump count
- [ ] Wire additional channels for future hopper lines

## Commands Reference (MegaInd CLI)
```bash
megaind 2 optord 1        # Read channel 1 state (0 or 1)
megaind 2 optord           # Read all channels as bitmask
megaind 2 countrd 1        # Read channel 1 transition count
megaind 2 countrst 1       # Reset channel 1 counter
megaind 2 edgerd 1         # Read edge detection mode (0=off, 1=rising, 2=falling, 3=both)
megaind 2 edgewr 1 3       # Set edge detection to both
megaind 2 ifrd 1           # Read frequency on channel 1
```

## ⚠️ PRODUCTION WARNINGS
- **DO NOT** reset the counter or restart services without Justin's approval
- **DO NOT** modify the acquisition loop without testing
- The monitor script is standalone and does not interfere with the main loadcell-transmitter service
- The opto input wiring is live — do not disconnect or rewire without powering down
