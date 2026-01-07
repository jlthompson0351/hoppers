#!/usr/bin/env bash
# Basic hardware smoke test script
# Run this after bootstrap to verify I2C and basic board communication

set -euo pipefail

echo "=== Load Cell Transmitter - Hardware Smoke Test ==="
echo ""

# Check if running on Linux
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "❌ ERROR: This script must run on Linux (Raspberry Pi)"
    exit 1
fi

# Check if i2cdetect exists
if ! command -v i2cdetect &> /dev/null; then
    echo "❌ ERROR: i2cdetect not found. Install i2c-tools:"
    echo "   sudo apt install i2c-tools"
    exit 1
fi

echo "Step 1: I2C Bus Scan"
echo "-------------------"
echo "Expected devices:"
echo "  - 0x30: Super Watchdog (if present)"
echo "  - 0x31: 24b8vin DAQ (stack 0)"
echo "  - 0x50: MegaIND (stack 0)"
echo ""

i2cdetect -y 1

echo ""
echo "Step 2: Detect Sequent Boards"
echo "----------------------------"

FOUND_DAQ=0
FOUND_MEGAIND=0
FOUND_WDT=0

# Parse i2cdetect output
while IFS= read -r line; do
    if [[ $line =~ 31 ]]; then
        FOUND_DAQ=1
    fi
    if [[ $line =~ 50 ]]; then
        FOUND_MEGAIND=1
    fi
    if [[ $line =~ 30 ]]; then
        FOUND_WDT=1
    fi
done < <(i2cdetect -y 1)

if [[ $FOUND_DAQ -eq 1 ]]; then
    echo "✓ 24b8vin DAQ detected at 0x31"
else
    echo "✗ 24b8vin DAQ NOT detected (expected at 0x31)"
fi

if [[ $FOUND_MEGAIND -eq 1 ]]; then
    echo "✓ MegaIND detected at 0x50"
else
    echo "✗ MegaIND NOT detected (expected at 0x50)"
fi

if [[ $FOUND_WDT -eq 1 ]]; then
    echo "✓ Super Watchdog detected at 0x30"
else
    echo "○ Super Watchdog not detected (optional)"
fi

echo ""
echo "Step 3: Check Service Status"
echo "---------------------------"

if systemctl is-active --quiet loadcell-transmitter; then
    echo "✓ loadcell-transmitter service is running"
    echo ""
    echo "Dashboard should be accessible at: http://$(hostname -I | awk '{print $1}'):8080"
else
    echo "✗ loadcell-transmitter service is NOT running"
    echo "  Start with: sudo systemctl start loadcell-transmitter"
fi

echo ""
echo "=== Smoke Test Complete ==="
echo ""

if [[ $FOUND_DAQ -eq 1 && $FOUND_MEGAIND -eq 1 ]]; then
    echo "✓ All required boards detected. Proceed to calibration."
    exit 0
else
    echo "✗ Missing required boards. Check hardware connections."
    exit 1
fi
