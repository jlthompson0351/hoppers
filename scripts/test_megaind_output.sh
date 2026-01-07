#!/usr/bin/env bash
# Test MegaIND analog output with voltage sweep
# Use with a multimeter to verify output

set -euo pipefail

STACK=${1:-0}
VENDOR_DIR="/opt/loadcell-transmitter/.vendor/megaind-rpi"
CLI_TOOL="$VENDOR_DIR/megaind"

echo "=== MegaIND Analog Output Test ==="
echo "Stack ID: $STACK"
echo ""

# Check if CLI tool exists
if [[ ! -f "$CLI_TOOL" ]]; then
    echo "❌ CLI tool not found at: $CLI_TOOL"
    echo "Building megaind CLI tool..."
    cd "$VENDOR_DIR"
    make
    echo ""
fi

if [[ ! -f "$CLI_TOOL" ]]; then
    echo "❌ Failed to build CLI tool"
    exit 1
fi

echo "⚠️  Connect multimeter between MegaIND AO+ and AO- terminals"
echo "⚠️  Press Enter to start voltage sweep..."
read -r

echo ""
echo "Voltage Sweep Test (0-10V)"
echo "--------------------------"

for voltage in 0 2.5 5.0 7.5 10.0; do
    echo ""
    echo "Setting output to: ${voltage}V"
    "$CLI_TOOL" -stack "$STACK" uout "$voltage"
    
    echo "Measure voltage and verify: ~${voltage}V"
    echo "Press Enter to continue..."
    read -r
done

echo ""
echo "Returning output to 0V (safe state)"
"$CLI_TOOL" -stack "$STACK" uout 0
echo "✓ Output set to 0V"

echo ""
echo "=== Test Complete ==="
echo ""
echo "To manually set output voltage:"
echo "  $CLI_TOOL -stack $STACK uout <voltage>"
echo ""
echo "For 4-20mA mode testing, use:"
echo "  $CLI_TOOL -stack $STACK iout <milliamps>"
echo ""
