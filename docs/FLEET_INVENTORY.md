# Fleet Inventory

**Last Updated**: 2026-02-11

This document tracks all deployed Pi systems running the Load Cell Scale Transmitter software.

## Active Sites

| Site Name | Pi IP | Hostname | Version | Hopper Type | Capacity | Installed | Last Update | Status |
|-----------|-------|----------|---------|-------------|----------|-----------|-------------|--------|
| Site A - Line 1 | 172.16.190.25 | Hoppers | v1.0.0+ | 4-leg | 250 lb | 2025-01-15 | 2026-02-11 | ✅ Online |

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

**Network:**
- Network: Magni-Guest
- SSH: Enabled, port 22
- Credentials: pi / depor

**I2C Configuration:**
- 24b8vin DAQ: 0x31 (Stack 0)
- MegaIND I/O: 0x50 (Stack 0)

**Notes:**
- Primary pilot installation
- Fully commissioned and calibrated
- Zero tracking enabled
- Excitation monitoring can now be toggled ON/OFF from Settings Quick Setup

**Maintenance History:**
| Date | Action | Notes |
|------|--------|-------|
| 2025-01-15 | Initial installation | Hardware setup and basic config |
| 2025-01-30 | Configuration update | Added rules, skills, subagents |
| 2026-02-11 | Runtime update | Added excitation monitoring toggle to prevent false safe-output clamp during commissioning |

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

### SSH to Site
```powershell
plink -pw depor pi@172.16.190.25
```

### View Dashboard
- Site A: http://172.16.190.25:8080
