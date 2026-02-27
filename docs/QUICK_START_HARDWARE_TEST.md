# Quick Start: Hardware Test — TODAY

**Full runbook**: See `HardwareTestReadiness_TODAY.md` for detailed steps.

---

## 🎯 SYSTEM IS LIVE (December 18, 2025)

# 👉 Dashboard: http://172.16.190.25:8080

---

## ✅ Deployed System Status

| Component | Status | Details |
|-----------|--------|---------|
| **Dashboard** | ✅ LIVE | http://172.16.190.25:8080 |
| **Flask Service** | ✅ Running | `loadcell-transmitter.service` |
| **24b8vin** (8x ADC) | ✅ Online | I2C 0x31, Firmware 1.4 |
| **MegaIND** (Industrial I/O) | ✅ Online | I2C 0x52 (Stack 2), Firmware 4.8 |
| **Hardware Mode** | ✅ REAL | Live readings from load cells |

**Pi:** `Hoppers` at `172.16.190.25` | **See:** `CONNECTION_GUIDE.md` for SSH/dashboard access

---

## Prerequisites (Justin's tasks)
- [ ] Raspberry Pi with fresh Raspberry Pi OS installed
- [ ] SSH access enabled (Justin provides IP address)
- [ ] Hardware stack assembled: Pi → 24b8vin → MegaIND
- [ ] Load cells connected to 24b8vin (CH1-CH4)
- [ ] Excitation wired from SlimPak (recommended for monitoring; can be disabled in software if not wired yet)
- [ ] Known calibration weights available (e.g., 25 lb, 50 lb, 100 lb)
- [ ] Multimeter for analog output testing

---

## Phase 1: Bootstrap (30-45 min)

```bash
# SSH in
ssh pi@<IP>

# Update OS
sudo apt update && sudo apt upgrade -y

# Enable I2C
sudo raspi-config
# → Interface Options → I2C → Yes → Reboot

# Install packages
sudo apt install -y i2c-tools python3-dev python3-pip python3-venv python3-smbus git vim

# Create app directory
sudo mkdir -p /opt/loadcell-transmitter
sudo chown pi:pi /opt/loadcell-transmitter
```

**From Windows machine (PowerShell):**
```powershell
scp -r C:\Users\jthompson\Desktop\hoppers pi@<IP>:/tmp/hoppers
```

**Back on Pi:**
```bash
cp -r /tmp/hoppers/* /opt/loadcell-transmitter/
cd /opt/loadcell-transmitter
./scripts/install_pi.sh

# Setup data directory
sudo mkdir -p /var/lib/loadcell-transmitter
sudo chown pi:pi /var/lib/loadcell-transmitter

# Install systemd service
sudo cp systemd/loadcell-transmitter.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable loadcell-transmitter
sudo systemctl start loadcell-transmitter
sudo systemctl status loadcell-transmitter
```

**Access dashboard**: `http://<PI_IP>:8080`

---

## Phase 2: Hardware Smoke Tests (15-30 min)

```bash
# I2C scan — SEND SCREENSHOT
sudo i2cdetect -y 1  # if command not found: sudo /usr/sbin/i2cdetect -y 1
# Expected: 0x31 (24b8vin DAQ), 0x52 (MegaIND stack 2)
# Note: 0x30 would be Super Watchdog if present

# Run automated smoke test
cd /opt/loadcell-transmitter
chmod +x scripts/test_hardware_basic.sh
./scripts/test_hardware_basic.sh

# Test 24b8vin channels
chmod +x scripts/test_24b8vin_channels.sh
./scripts/test_24b8vin_channels.sh
# SEND OUTPUT

# Test MegaIND output
chmod +x scripts/test_megaind_output.sh
./scripts/test_megaind_output.sh
# Follow prompts with multimeter
```

**Check dashboard**: "Boards Online: 2/2" should show green

---

## Phase 3: Calibration (45-60 min)

**Dashboard → Config:**
1. Enable channels 1-4
2. Set stack levels (DAQ=0, MegaIND=2)
3. Tune stability settings if needed

**Dashboard → Calibration:**
1. **Zero point**: Empty scale → wait for STABLE → add point (0 lb)
2. **Span points**: 
   - Place 25 lb → STABLE → add point (25 lb)
   - Place 50 lb → STABLE → add point (50 lb)
   - Place 100 lb → STABLE → add point (100 lb)
   - Etc.

**Verification helper:**
```bash
cd /opt/loadcell-transmitter
chmod +x scripts/verify_calibration.py
python3 scripts/verify_calibration.py
```

**Reboot test:**
```bash
sudo reboot
# Wait 60s, verify dashboard still shows correct readings
```

---

## Phase 4: Analog Output Test (30-45 min)

**Dashboard → Calibration Hub:**
- Set output mode: 0-10V
- Train PLC profile points (e.g., 0 lb = 0.0V, 150 lb = 10.0V)
- System interpolates between trained points

**Automated test log:**
```bash
cd /opt/loadcell-transmitter
chmod +x scripts/analog_output_test_log.py
python3 scripts/analog_output_test_log.py
```

Follow prompts to test multiple weight points with multimeter.

**Manual verification (example with 0 lb = 0V, 150 lb = 10V profile):**
| Weight | Expected Voltage (linear interpolation) |
|--------|------------------------------------------|
| 0 lb   | 0.0 V                                   |
| 37.5 lb| 2.5 V                                   |
| 75 lb  | 5.0 V                                   |
| 112.5 lb| 7.5 V                                  |
| 150 lb | 10.0 V                                  |

---

## Quick Commands

```bash
# Service management
sudo systemctl status loadcell-transmitter
sudo systemctl restart loadcell-transmitter
sudo journalctl -u loadcell-transmitter -f

# I2C check
i2cdetect -y 1

# CLI tools (installed globally)
24b8vin 0 rd 1           # Read analog input CH1
megaind 0 uoutwr 1 5.0   # Set 0-10V output CH1 to 5V

# Backup database
cp /var/lib/loadcell-transmitter/app.sqlite3 ~/backup-$(date +%Y%m%d-%H%M%S).sqlite3
```

---

## Final Checklist

- [ ] Bootstrap: Dashboard accessible and survives reboot
- [ ] Hardware: I2C scan shows all boards, "Boards Online: 2/2"
- [ ] Calibration: Zero + 2+ span points, readings within ±2 lb
- [ ] Analog output: All test points within ±0.2V
- [ ] Stability: STABLE/UNSTABLE toggles correctly
- [ ] Database backed up

---

## Troubleshooting

**"Boards Online: 0/2" or "I/O OFFLINE":**
- Check `i2cdetect -y 1` output
- Verify wiring and I2C connections
- Check `sudo journalctl -u loadcell-transmitter -n 100`
- System auto-retries every 5 seconds when hardware is offline

**Can't add calibration point:**
- Wait for STABLE indicator
- Increase stability threshold in Config

**Output voltage wrong:**
- Verify PLC profile points trained in Calibration Hub
- Check weight calibration is loaded (dashboard shows correct weight first)
- Measure directly at MegaIND AO terminals
- If no profile points, system uses internal 0-250 lb fallback

---

**Timeline**: ~2.5-3.5 hours total

**Support**: See full runbook `HardwareTestReadiness_TODAY.md` for detailed troubleshooting
