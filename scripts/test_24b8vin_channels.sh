#!/usr/bin/env bash
# Test all 24b8vin channels and display readings
# Run this to verify load cell connections

set -euo pipefail

STACK=${1:-0}
VENDOR_DIR="/opt/loadcell-transmitter/.vendor/24b8vin-rpi"
CLI_TOOL="$VENDOR_DIR/24b8vin"

echo "=== 24b8vin Channel Test ==="
echo "Stack ID: $STACK"
echo ""

# Check if CLI tool exists
if [[ ! -f "$CLI_TOOL" ]]; then
    echo "❌ CLI tool not found at: $CLI_TOOL"
    echo "Building 24b8vin CLI tool..."
    cd "$VENDOR_DIR"
    make
    echo ""
fi

if [[ ! -f "$CLI_TOOL" ]]; then
    echo "❌ Failed to build CLI tool"
    exit 1
fi

echo "Reading all 8 channels:"
echo "-----------------------"

for ch in {1..8}; do
    echo -n "Channel $ch: "
    
    # Try to read channel
    if output=$("$CLI_TOOL" -stack "$STACK" rd "$ch" 2>&1); then
        echo "$output"
    else
        echo "ERROR - $output"
    fi
done

echo ""
echo "=== Expected Behavior ==="
echo "Active channels (with load cells): Should show mV values (typically -50 to +50 mV when unloaded)"
echo "Inactive channels: May show near 0 or stable value"
echo ""
echo "To test a specific channel:"
echo "  $CLI_TOOL -stack $STACK rd <channel_number>"
echo ""
