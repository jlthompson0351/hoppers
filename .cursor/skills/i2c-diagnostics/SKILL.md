---
name: i2c-diagnostics
description: Diagnose I2C hardware communication issues with Sequent boards. Use when user reports "I/O OFFLINE", board detection failures, hardware errors, or can't connect to boards.
---

# I2C Hardware Diagnostics

## Purpose
Troubleshoot I2C communication issues between Raspberry Pi and Sequent boards (24b8vin DAQ, MegaIND).

## When to Use
- Dashboard shows "I/O OFFLINE"
- User reports board detection failures
- Hardware errors in logs
- Service fails to start with I2C errors
- Keywords: "hardware not working", "boards offline", "I2C error", "can't detect", "hardware fault"

## Expected Hardware Configuration

| Board | I2C Address | Purpose |
|-------|-------------|---------|
| 24b8vin | 0x31 | 8-channel 24-bit DAQ (load cell inputs) |
| MegaIND | 0x52 (Stack 2) | Analog output to PLC, digital I/O |

Both boards should appear on I2C bus 1.

## Steps

### 1. Verify Pi Connectivity
```powershell
# Test if Pi is reachable
ping 172.16.190.25

# Test SSH connection
plink -pw depor pi@172.16.190.25 "echo 'SSH OK'"
```

### 2. Generate Diagnostic Script
Create comprehensive diagnostic:

```bash
#!/bin/bash
# i2c_full_diagnostics.sh

echo "=========================================="
echo "I2C Hardware Diagnostics"
echo "Date: $(date)"
echo "=========================================="

echo -e "\n=== Service Status ==="
sudo systemctl status loadcell-transmitter --no-pager | head -20

echo -e "\n=== I2C Bus Scan ==="
sudo i2cdetect -y 1

echo -e "\n=== Expected Devices ==="
echo "24b8vin DAQ should appear at: 0x31"
echo "MegaIND I/O should appear at: 0x52 (stack 2; base 0x50 + 2)"

echo -e "\n=== Checking 24b8vin (0x31) ==="
if sudo i2cdetect -y 1 | grep -q "31"; then
    echo "✅ 24b8vin detected at 0x31"
    # Try to read firmware version
    24b8vin 0 cfgrd 2 2>/dev/null || echo "Could not read firmware"
else
    echo "❌ 24b8vin NOT detected at 0x31"
fi

echo -e "\n=== Checking MegaIND (0x52) ==="
if sudo i2cdetect -y 1 | grep -q "52"; then
    echo "✅ MegaIND detected at 0x52 (stack 2)"
    megaind 2 cfgrd 2 2>/dev/null || echo "Could not read firmware"
else
    echo "❌ MegaIND NOT detected at 0x52"
fi

echo -e "\n=== Recent Errors in Logs ==="
sudo journalctl -u loadcell-transmitter --since "30 minutes ago" 2>/dev/null | grep -i "error\|fail\|fault" | tail -20

echo -e "\n=== I2C Kernel Module ==="
lsmod | grep i2c

echo -e "\n=== Power Check (24V) ==="
echo "Cannot check remotely - verify 24V supply is connected"
echo "LED indicators on boards should be lit"

echo -e "\n=========================================="
echo "Diagnostics Complete"
echo "=========================================="
```

### 3. Run Diagnostics
Provide commands to run:
```powershell
# Run full diagnostics
plink -pw depor pi@172.16.190.25 "bash -c 'sudo i2cdetect -y 1; sudo systemctl status loadcell-transmitter --no-pager | head -10'"
```

### 4. Interpret Results

**Scenario A: Both Boards Detected (0x31 and 0x52 visible)**
```
Service issue, not hardware. Check:
- Python syntax errors in recent changes
- Missing dependencies
- Database corruption
- Permission issues
```

**Scenario B: No Boards Detected (empty scan)**
```
Power or physical connection issue:
1. Check 24V power supply connected
2. Check board stack order (24b8vin bottom, MegaIND top)
3. Reseat boards on Pi GPIO header
4. Check for bent GPIO pins
5. Verify I2C enabled: sudo raspi-config
```

**Scenario C: Only One Board Detected**
```
Specific board issue:
- Check stack ID jumpers/DIP switches
- Check board-specific power requirements
- Try different stack position
- Board may be faulty
```

**Scenario D: Wrong Addresses**
```
Stack ID configuration issue:
- 24b8vin: Stack 0 = 0x31, Stack 1 = 0x32, etc.
- MegaIND: Stack 0 = 0x50, Stack 1 = 0x51, etc.
- Check DIP switches match expected stack ID
```

### 5. Generate Fix Commands
Based on diagnosis:

**Restart I2C subsystem:**
```bash
sudo modprobe -r i2c_bcm2835
sudo modprobe i2c_bcm2835
```

**Enable I2C if disabled:**
```bash
sudo raspi-config nonint do_i2c 0
sudo reboot
```

**Reinstall Python dependencies:**
```bash
cd /opt/loadcell-transmitter
source .venv/bin/activate
pip install --force-reinstall smbus2
```

**Reset service:**
```bash
sudo systemctl restart loadcell-transmitter
sudo journalctl -u loadcell-transmitter -f
```

### 6. Document Resolution
If issue resolved, remind user to add to `docs/MaintenanceAndTroubleshooting.md`:
```markdown
### I2C Detection Failure - [Date]
**Symptom**: I/O OFFLINE, boards not detected
**Root Cause**: [what was wrong]
**Solution**: [what fixed it]
**Prevention**: [how to avoid]
```

## Output
- Diagnostic script or commands
- Interpretation of results
- Specific fix commands
- Documentation reminder

## Related Docs
- `docs/CONNECTION_GUIDE.md`
- `docs/WiringAndCommissioning.md`
- `docs/Architecture.md` (Section 1.2 - I2C Configuration)
- `docs/MaintenanceAndTroubleshooting.md`
