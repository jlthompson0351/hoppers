# Raspberry Pi Connection Guide
**Target System:** Hoppers (Load Cell Scale Transmitter)

**Document Version:** 1.2  
**Date:** February 13, 2026  
**Purpose:** How to connect to the Raspberry Pi for development and maintenance

---

## 🎯 LIVE DASHBOARD

# 👉 http://172.16.190.25:8080

Open this URL in any browser on your network to view live load cell readings.

---

## ✅ Verified System Status (December 18, 2025)

| Component | Status | Details |
|-----------|--------|---------|
| **Dashboard** | ✅ LIVE | http://172.16.190.25:8080 |
| **Flask Service** | ✅ Running | `loadcell-transmitter.service` |
| **24b8vin DAQ** | ✅ Online | I2C 0x31, Firmware 1.4 |
| **MegaIND** | ✅ Online | I2C 0x52 (Stack 2), Firmware 4.8 |
| **Hardware Mode** | ✅ REAL | Live hardware readings |

## ✅ Connection Details

| Property | Value |
|----------|-------|
| **Hostname** | `Hoppers` |
| **IP Address** | `172.16.190.25` |
| **Dashboard URL** | http://172.16.190.25:8080 |
| **Username** | `pi` |
| **Password** | *(provided separately)* |
| **SSH Port** | 22 (default) |
| **Network** | `Magni-Guest` |
| **OS** | Debian GNU/Linux, Kernel 6.12.47+rpt-rpi-v8 (aarch64) |

---

## Connection Methods

### Method 1: Windows — PuTTY/Plink (Recommended for Automation)

**Plink** is PuTTY's command-line SSH tool. Use it for scripted/automated SSH commands from Windows.

#### Single Command Execution
```powershell
plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD "hostname"
```

#### Multiple Commands
```powershell
plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD "hostname && uname -a && uptime"
```

#### Run Remote Script
```powershell
plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD "cd /opt/loadcell-transmitter && ./scripts/test_hardware_basic.sh"
```

#### Interactive Session
```powershell
plink -ssh pi@172.16.190.25
```
Then enter password when prompted.

**Note:** First connection will prompt to accept the host key. Enter `y` to cache it.

---

### Method 2: Windows — OpenSSH (Built into Windows 10/11)

#### Interactive Session
```powershell
ssh pi@172.16.190.25
```

#### Single Command
```powershell
ssh pi@172.16.190.25 "hostname && uptime"
```

---

### Method 3: Windows — PuTTY GUI

1. Open PuTTY
2. Enter Host Name: `172.16.190.25`
3. Port: `22`
4. Connection Type: SSH
5. Click "Open"
6. Login as: `pi`
7. Enter password when prompted

**Save Session:** Enter a name in "Saved Sessions" and click "Save" for quick access later.

---

### Method 4: Desktop Commander MCP (Cursor IDE)

For use within Cursor IDE with the Desktop Commander MCP extension:

```javascript
// Start SSH process
start_process({ command: "plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD \"your_command\"" })

// Example: Read analog inputs
start_process({ command: "plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD \"24b8vin 0 rd 1\"" })

// Example: Check board status
start_process({ command: "plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD \"megaind 0 board\"" })
```

---

### Method 5: SCP — File Transfer

#### Copy file TO Pi:
```powershell
scp C:\path\to\local\file.txt pi@172.16.190.25:/home/pi/
```

#### Copy file FROM Pi:
```powershell
scp pi@172.16.190.25:/home/pi/file.txt C:\path\to\local\
```

#### Copy entire directory TO Pi:
```powershell
scp -r C:\Users\jthompson\Desktop\hoppers pi@172.16.190.25:/tmp/
```

---

## Quick Command Reference

### System Status
```bash
# Check hostname
hostname

# System info
uname -a

# Uptime
uptime

# Disk usage
df -h

# Memory usage
free -h
```

### I2C / Hardware
```bash
# Scan I2C bus
sudo i2cdetect -y 1

# Expected result:
#      0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
# 30: -- 31 -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 50: 50 -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
# 
# 0x31 = 24b8vin (8x analog inputs DAQ)
# 0x52 = MegaIND (industrial I/O, stack 2)
```

### 24b8vin (Analog Inputs DAQ)
```bash
# Check board status
24b8vin 0 board

# Read single channel (1-8)
24b8vin 0 rd 1

# Read all channels
24b8vin 0 rd 1; 24b8vin 0 rd 2; 24b8vin 0 rd 3; 24b8vin 0 rd 4
24b8vin 0 rd 5; 24b8vin 0 rd 6; 24b8vin 0 rd 7; 24b8vin 0 rd 8

# Get gain code for channel
24b8vin 0 grd 1

# Set gain code (0-7) for channel
24b8vin 0 gwr 1 6    # Set CH1 to gain 6 (±0.37V range)
```

### MegaIND (Industrial I/O)
```bash
# Check board status
megaind 0 board

# Read 0-10V output channel (1-4)
megaind 0 uoutrd 1

# Set 0-10V output (0.0 to 10.0)
megaind 0 uoutwr 1 5.0

# Read 4-20mA output channel (1-4)
megaind 0 ioutrd 1

# Set 4-20mA output (4.0 to 20.0)
megaind 0 ioutwr 1 12.0
```

### Python Libraries
```bash
# Test 24b8vin Python library
python3 -c "import SM24b8vin; a=SM24b8vin.SM24b8vin(0); print(a.get_u_in(1))"

# Test MegaIND Python library
python3 -c "import megaind; print(megaind.getFwVer(0))"
```

### Service Management
```bash
# Check service status
sudo systemctl status loadcell-transmitter

# Restart service
sudo systemctl restart loadcell-transmitter

# View logs (follow mode)
sudo journalctl -u loadcell-transmitter -f

# View last 50 log lines
sudo journalctl -u loadcell-transmitter -n 50
```

---

## Troubleshooting

### SSH Connection Refused
```bash
# Verify SSH service is running on Pi
sudo systemctl status ssh

# Enable SSH if disabled
sudo systemctl enable ssh
sudo systemctl start ssh
```

### Permission Denied (Password)
- Verify password is correct
- Check username is `pi` (lowercase)
- Verify SSH allows password authentication

### Host Key Verification Failed
```powershell
# Windows: Clear known hosts entry
ssh-keygen -R 172.16.190.25

# Or for plink, accept the new key when prompted
```

### I2C Devices Not Detected
```bash
# Verify I2C is enabled
ls /dev/i2c-*
# Should show: /dev/i2c-1

# If missing, enable I2C:
sudo raspi-config
# → Interface Options → I2C → Yes → Reboot
```

---

## Network Information

| Property | Value |
|----------|-------|
| **Pi IP** | `172.16.190.25` |
| **Network** | `Magni-Guest` |
| **Gateway** | *(depends on network)* |

**To find Pi on network:**
```powershell
# Windows: Ping to verify connectivity
ping 172.16.190.25

# If IP unknown, scan network (requires nmap or similar)
nmap -sn 172.16.190.0/24
```

---

## Verified Hardware Stack

```
┌─────────────────────────────────┐
│   24b8vin HAT (TOP)             │ ← I2C: 0x31, Firmware 1.4
│   8x 24-bit Analog Inputs       │
├─────────────────────────────────┤
│   MegaIND HAT (TOP)             │ ← I2C: 0x52 (Stack 2), Firmware 4.8
│   Industrial Automation I/O     │
├─────────────────────────────────┤
│   Raspberry Pi 4B               │ ← Hostname: Hoppers
│   IP: 172.16.190.25             │
├─────────────────────────────────┤
│   QDtech MPI5001 5" Touchscreen │ ← HDMI + USB touch (0484:5750)
│   800x480, mounted upside down  │
└─────────────────────────────────┘
```

## Display Rotation (Upside-Down Mounting)

The touchscreen is mounted inverted to fit the enclosure. Two config files handle this:

**1. Framebuffer rotation** — `/boot/firmware/cmdline.txt`:
```
video=HDMI-A-1:800x480@60,rotate=180
```
Appended to the end of the existing kernel command line.

**2. Touchscreen calibration** — `/etc/udev/rules.d/98-touchscreen-rotate.rules`:
```
ATTRS{idVendor}=="0484", ATTRS{idProduct}=="5750", ENV{LIBINPUT_CALIBRATION_MATRIX}="-1 0 1 0 -1 1"
```

**Important:** Do NOT use `wlr-randr --transform 180` (Wayland compositor rotation). It conflicts with the udev touch calibration and breaks touch input.

---

## Session Examples

### Example 1: Quick Hardware Check
```powershell
plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD "sudo /usr/sbin/i2cdetect -y 1 && echo '---' && 24b8vin 0 board && echo '---' && megaind 0 board"
```

### Example 2: Read All Analog Inputs
```powershell
plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD "for ch in 1 2 3 4 5 6 7 8; do echo CH$ch:; 24b8vin 0 rd $ch; done"
```

### Example 3: Test Analog Output
```powershell
# Set output to 5V
plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD "megaind 0 uoutwr 1 5.0"

# Read back
plink -ssh pi@172.16.190.25 -pw YOUR_PASSWORD "megaind 0 uoutrd 1"
```

---

---

## 🖥️ Dashboard Access

The Load Cell Scale Transmitter runs as a web server on the Pi. Access it from any browser on the network:

### From Windows/Mac/Phone:
1. Open any web browser (Chrome, Edge, Firefox, Safari)
2. Go to: **http://172.16.190.25:8080**
3. View live load cell readings, calibration, and settings

### How It Works:
```
┌─────────────────────────────────┐
│  Your Device (PC/Phone/Tablet) │
│  Browser → http://172.16.190.25:8080
└──────────────┬──────────────────┘
               │ (WiFi: Magni-Guest)
               ▼
┌─────────────────────────────────┐
│  Raspberry Pi "Hoppers"         │
│  Flask Web Server (port 8080)   │
│  ↕                              │
│  24b8vin (8x ADC) + MegaIND     │
│  ↕                              │
│  Load Cells                     │
└─────────────────────────────────┘
```

---

## 🔧 Service Management

### Check Service Status
```bash
sudo systemctl status loadcell-transmitter
```

### View Live Logs
```bash
sudo journalctl -u loadcell-transmitter -f
```

### Restart Service
```bash
sudo systemctl restart loadcell-transmitter
```

### Stop Service
```bash
sudo systemctl stop loadcell-transmitter
```

### Start Service
```bash
sudo systemctl start loadcell-transmitter
```

### Disable Auto-Start on Boot
```bash
sudo systemctl disable loadcell-transmitter
```

### Enable Auto-Start on Boot
```bash
sudo systemctl enable loadcell-transmitter
```

---

## 📁 File Locations

| Path | Description |
|------|-------------|
| `/opt/loadcell-transmitter/` | Application code |
| `/opt/loadcell-transmitter/src/` | Python source |
| `/opt/loadcell-transmitter/.venv/` | Python virtual environment |
| `/var/lib/loadcell-transmitter/` | Data directory (SQLite DB) |
| `/etc/systemd/system/loadcell-transmitter.service` | Systemd service file |

---

**Document Version:** 1.2  
**Last Updated:** February 13, 2026  
**System Deployed:** December 18, 2025
