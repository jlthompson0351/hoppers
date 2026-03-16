# Fleet Inventory

**Last Updated**: 2026-03-16

This document tracks all deployed Pi systems running the Load Cell Scale Transmitter software.

## Active Sites

| Site Name | Pi IP | Hostname | Version | Hopper Type | Capacity | Installed | Last Update | Status |
|-----------|-------|----------|---------|-------------|----------|-----------|-------------|--------|
| Site A - Line 1 | 172.16.190.25 | Hoppers | Feb 27 live baseline + Mar 5/6/16 staged runtime updates pending restart | 4-leg | 300 lb | 2025-01-15 | 2026-03-16 | ✅ Operational |

## Planned Sites

| Site Name | Planned IP | Hopper Type | Capacity | Target Date | Notes |
|-----------|------------|-------------|----------|-------------|-------|
| _None planned_ | - | - | - | - | - |

---

## Site Details

### Site A - Line 1 (Primary Installation)

| Property | Value |
|----------|-------|
| **Pi IP** | 172.16.190.25 |
| **Hostname** | Hoppers |
| **Location** | [Update with physical location] |
| **Dashboard URL** | http://172.16.190.25:8080 |
| **Install Date** | 2025-01-15 |
| **Commissioned By** | jthompson |

**Hardware Configuration:**
- Hopper Type: 4-leg
- Capacity: 250 lb
- Load Cell Channels: 1, 2, 3, 4 (4 active)
- Excitation: 10V nominal
- PLC Output: 0-10V, 25 lb/V scaling
- Display: QDtech MPI5001 5" 800x480 HDMI touchscreen (USB touch, ID 0484:5750)
- Display Mounting: Inverted (upside down), rotated 180° via kernel framebuffer

**Network:**
- Network: Magni-Guest
- SSH: Enabled, port 22
- Credentials: stored separately; do not hardcode in new docs or agent instructions

**I2C Configuration:**
- 24b8vin DAQ: 0x31 (Stack 0)
- MegaIND I/O: 0x52 (Stack 2)

**Display Rotation Config:**
- Kernel framebuffer: `video=HDMI-A-1:800x480@60,rotate=180` in `/boot/firmware/cmdline.txt`
- Touchscreen calibration: udev rule at `/etc/udev/rules.d/98-touchscreen-rotate.rules`
  - `ATTRS{idVendor}=="0484", ATTRS{idProduct}=="5750", ENV{LIBINPUT_CALIBRATION_MATRIX}="-1 0 1 0 -1 1"`
- Note: Do NOT use `wlr-randr --transform 180` (labwc compositor rotation) — it conflicts with touch calibration

**Notes:**
- Primary pilot installation
- Fully commissioned and calibrated
- Zero tracking enabled
- Excitation monitoring can now be toggled ON/OFF from Settings Quick Setup
- Display mounted upside down for enclosure fit; rotation handled at kernel + udev level

**Maintenance History:**
| Date | Action | Notes |
|------|--------|-------|
| 2025-01-15 | Initial installation | Hardware setup and basic config |
| 2025-01-30 | Configuration update | Added rules, skills, subagents |
| 2026-02-11 | Runtime update | Added excitation monitoring toggle to prevent false safe-output clamp during commissioning |
| 2026-02-13 | Display rotation | Screen mounted upside down for enclosure fit; added kernel framebuffer rotate=180 and udev touchscreen calibration rule |
| 2026-02-13 | Fast negative auto-zero | v3.0 zero tracking: dual-path ZeroTracker with fast negative correction for hopper dump cycles. Negative weight now auto-zeroed in ~1s instead of never firing. |
| 2026-02-15 | **Canonical mV Zeroing Patch** | **v3.1 deployed**. Fixed catastrophic bug: zero_offset_mv now stores mV (not lbs). Manual ZERO works instantly. Zero tracking converges reliably. System stable. User confirms: "Working like a champ." |
| 2026-02-20 | Hardware Upgrade | Added 4th load cell, full recalibration (9-point), new PLC profile (17-point), zero floor (3lb) |
| 2026-02-24 | System Snapshot | **v3.3.2**. Verified live settings: Zero Offset 32.68 lb, PLC 0-10V linear 10-400lb. System healthy. |
| 2026-02-27 | Job-target webhook live rollout | Public webhook path + HDMI target UI became the known live baseline. |
| 2026-03-05 to 2026-03-16 | Staged runtime updates | Completed-job webhook, floor threshold, basket dump, and re-zero warning are staged on Pi and still require approved restart/validation. |

**Backup Status:**
| Backup | Date | Includes Rotation Config | Location | Status |
|--------|------|--------------------------|----------|--------|
| Full image | 2026-02-12 | No | `backups/scale-project-backup-20260212.img` | Historical only; stale for cloning current production state |
| Baseline bundle | 2026-02-15 | Yes | `backups/pi-baseline-172.16.190.25-20260215-140649/` | Latest documented structured baseline pull |
| Fresh full image | Pending | TBD | TBD | Still needs to be captured after repo/runtime truth is confirmed |

> **Current backup note:** the Feb 15 baseline bundle is the best documented recovery snapshot in the repo today, but it is not the same thing as a fresh cloneable full image. A new full image backup is still needed before building another scale from this system.

---

## How to Update This Document

### When to Update
- After any deployment (version change)
- After adding a new site
- After significant configuration change
- After maintenance activity

### Required Fields for New Sites
1. Site Name (descriptive)
2. Pi IP (static or DHCP reserved)
3. Hostname
4. Current Version
5. Hopper Type (2-leg, 4-leg, etc.)
6. Capacity (lb)
7. Install Date
8. Status (✅ Online, ⚠️ Issues, 🔴 Offline)

### Status Indicators
- ✅ Online - System operating normally
- ⚠️ Issues - System running but needs attention
- 🔴 Offline - System down or unreachable
- 📋 Planned - Not yet installed

---

## Quick Access Commands

### Check All Sites Status
```powershell
# Ping all sites
ping 172.16.190.25
# Add more IPs as fleet grows
```

### SSH / agent access to Site
```powershell
# For humans, use your approved SSH method and credentials provided separately.
# For Cursor/OpenClaw agent work, prefer Desktop Commander + plink workflows.
```

### View Dashboard
- Site A: http://172.16.190.25:8080
