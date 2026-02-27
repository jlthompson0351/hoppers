#!/usr/bin/env bash
# Basic hardware smoke test script
# Run this after bootstrap to verify I2C and basic board communication

set -euo pipefail

echo "=== Load Cell Transmitter - Hardware Smoke Test ==="
echo ""

# Default stack IDs for the deployed production unit.
# Override as needed: DAQ_STACK=0 MEGAIND_STACK=2 ./scripts/test_hardware_basic.sh
DAQ_STACK="${DAQ_STACK:-0}"
MEGAIND_STACK="${MEGAIND_STACK:-2}"

# Convert stack IDs to expected I2C addresses.
DAQ_ADDR="$(printf '%02X' "$((0x31 + DAQ_STACK))")"
MEGAIND_ADDR="$(printf '%02X' "$((0x50 + MEGAIND_STACK))")"
WDT_ADDR="30"

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
echo "  - 0x$WDT_ADDR: Super Watchdog (if present)"
echo "  - 0x$DAQ_ADDR: 24b8vin DAQ (stack $DAQ_STACK)"
echo "  - 0x$MEGAIND_ADDR: MegaIND (stack $MEGAIND_STACK)"
echo ""

I2C_SCAN="$(i2cdetect -y 1)"
echo "$I2C_SCAN"

echo ""
echo "Step 2: Detect Sequent Boards"
echo "----------------------------"

FOUND_DAQ=0
FOUND_MEGAIND=0
FOUND_WDT=0

# Extract detected address tokens (skip headers + row labels like "50:").
DETECTED="$(
    echo "$I2C_SCAN" \
      | tail -n +2 \
      | awk '{for (i=2; i<=NF; i++) if ($i != "--") print $i}' \
      | tr '[:lower:]' '[:upper:]'
)"

if echo "$DETECTED" | grep -qx "$DAQ_ADDR"; then
    FOUND_DAQ=1
fi
if echo "$DETECTED" | grep -qx "$MEGAIND_ADDR"; then
    FOUND_MEGAIND=1
fi
if echo "$DETECTED" | grep -qx "$WDT_ADDR"; then
    FOUND_WDT=1
fi

if [[ $FOUND_DAQ -eq 1 ]]; then
    echo "✓ 24b8vin DAQ detected at 0x$DAQ_ADDR (stack $DAQ_STACK)"
else
    echo "✗ 24b8vin DAQ NOT detected (expected at 0x$DAQ_ADDR, stack $DAQ_STACK)"
fi

if [[ $FOUND_MEGAIND -eq 1 ]]; then
    echo "✓ MegaIND detected at 0x$MEGAIND_ADDR (stack $MEGAIND_STACK)"
else
    echo "✗ MegaIND NOT detected (expected at 0x$MEGAIND_ADDR, stack $MEGAIND_STACK)"
fi

if [[ $FOUND_WDT -eq 1 ]]; then
    echo "✓ Super Watchdog detected at 0x$WDT_ADDR"
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
