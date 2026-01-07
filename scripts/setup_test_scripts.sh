#!/usr/bin/env bash
# Make all test scripts executable
# Run this once on the Pi after copying the repo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Making test scripts executable..."

chmod +x "$SCRIPT_DIR/test_hardware_basic.sh"
chmod +x "$SCRIPT_DIR/test_24b8vin_channels.sh"
chmod +x "$SCRIPT_DIR/test_megaind_output.sh"
chmod +x "$SCRIPT_DIR/verify_calibration.py"
chmod +x "$SCRIPT_DIR/analog_output_test_log.py"
chmod +x "$SCRIPT_DIR/install_pi.sh"
chmod +x "$SCRIPT_DIR/run_pi.sh"

echo "✓ All test scripts are now executable"
echo ""
echo "Available test scripts:"
echo "  - test_hardware_basic.sh       : Basic I2C and board detection"
echo "  - test_24b8vin_channels.sh     : Read all DAQ channels"
echo "  - test_megaind_output.sh       : Test analog output voltage"
echo "  - verify_calibration.py        : Interactive calibration verification"
echo "  - analog_output_test_log.py    : Automated output test with logging"
echo ""
