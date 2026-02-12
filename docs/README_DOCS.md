# Documentation Index

## 🎯 LIVE DASHBOARD

# 👉 http://172.16.190.25:8080

Open in any browser to view live load cell readings.

---

## ✅ System Status (December 18, 2025)

| Component | Status | Details |
|-----------|--------|---------|
| **Dashboard** | ✅ LIVE | http://172.16.190.25:8080 |
| **Flask Service** | ✅ Running | Auto-starts on boot |
| **24b8vin** (8x ADC) | ✅ Online | I2C 0x31, Firmware 1.4 |
| **MegaIND** (Industrial I/O) | ✅ Online | I2C 0x50, Firmware 4.08 |
| **Hardware Mode** | ✅ REAL | Live hardware readings |

**Pi:** `Hoppers` at `172.16.190.25` — See `CONNECTION_GUIDE.md` for SSH/dashboard access

---

## 🚀 TODAY: Real Hardware Test

**Start here for today's hardware test:**

1. **`CONNECTION_GUIDE.md`** — How to SSH/connect to the Pi from Windows
2. **`TODAY_SUMMARY.md`** — Executive summary and checklist
3. **`HardwareTestReadiness_TODAY.md`** — Complete runbook (main document)
4. **`QUICK_START_HARDWARE_TEST.md`** — One-page quick reference

**Test scripts** (in `../scripts/`):
- `setup_test_scripts.sh` — Make scripts executable
- `test_hardware_basic.sh` — I2C + board detection
- `test_24b8vin_channels.sh` — Read DAQ channels
- `test_megaind_output.sh` — Voltage sweep test
- `verify_calibration.py` — Calibration verification helper
- `analog_output_test_log.py` — Output test with pass/fail report

---

## 📚 System Documentation

### ⭐ Current Implementation (Pre-Overhaul Reference)
- **`CURRENT_IMPLEMENTATION.md`** — Complete system state before UI overhaul
- **`CURRENT_UI_REFERENCE.md`** — UI pages, routes, API endpoints reference
- **`AUTO_ARMED_OUTPUT_CHANGE.md`** — Auto-armed output change (Feb 12, 2026)

### Architecture & Requirements
- **`Architecture.md`** — System architecture and design
- **`SRS.md`** — Software Requirements Specification

### Hardware Documentation
- **`WiringAndCommissioning.md`** — Hardware setup and wiring guide
- **`24b8vin_Quick_Reference.md`** — DAQ board quick reference
- **`24b8vin_Hardware_Reference.md`** — Detailed DAQ specs
- **`24b8vin_Documentation_Summary.md`** — DAQ overview
- **`24b8vin_Implementation_Notes.md`** — DAQ implementation details
- **`24b8vin_Settings_Schema.json`** — DAQ configuration schema
- **`MegaIND_QuickRef.md`** — MegaIND quick reference
- **`MegaIND_DOCUMENTATION_SUMMARY.md`** — MegaIND overview
- **`MegaIND_Settings_SPEC.md`** — MegaIND configuration spec
- **`MegaIND_Capabilities_Diagram.md`** — MegaIND feature map

### Zero, Tare & Drift Compensation
- **`ZERO_VS_TARE_FIX.md`** — How ZERO and TARE work, drift compensation explained
- **`DRIFT_COMPENSATION_DIAGRAM.md`** — Visual diagrams showing signal flow and zero tracking
- **`ZERO_TRACKING_OPERATOR_GUIDE.md`** — Complete operator guide: settings, troubleshooting, and verification tests

### Procedures & Configuration
- **`CalibrationProcedure.md`** — Operator calibration procedure (current runtime behavior)
- **`CALIBRATION_CURRENT_STATE.md`** — Code-backed calibration behavior and hardening direction
- **`TestPlan.md`** — Comprehensive test plan (bench + production)
- **`MaintenanceAndTroubleshooting.md`** — Maintenance and troubleshooting guide
- **`HDMI_KIOSK_RUNBOOK.md`** — Setup and operation of the HDMI operator interface
- **`PLC_OUTPUT_VERIFICATION.md`** — PLC output testing and verification procedures
- **`DEPLOYMENT_LOG.md`** — Deployment history and change log

### Risk & Planning
- **`RiskRegister.md`** — Project risk register

---

## 📖 Quick Navigation

### For Today's Testing
→ Start with `TODAY_SUMMARY.md`  
→ Follow `HardwareTestReadiness_TODAY.md`  
→ Use `QUICK_START_HARDWARE_TEST.md` for quick reference

### For Connecting to Pi
→ `CONNECTION_GUIDE.md` — SSH, plink, SCP from Windows

### For Hardware Setup
→ `WiringAndCommissioning.md`  
→ `24b8vin_Quick_Reference.md`  
→ `MegaIND_QuickRef.md`

### For Calibration
→ `CalibrationProcedure.md`  
→ `CALIBRATION_CURRENT_STATE.md`  
→ Use helper script: `../scripts/verify_calibration.py`

### For Zero/Tare & Drift Issues
→ `ZERO_VS_TARE_FIX.md` — Complete explanation of zero vs tare  
→ `DRIFT_COMPENSATION_DIAGRAM.md` — Visual signal flow diagrams

### For Troubleshooting
→ `MaintenanceAndTroubleshooting.md`  
→ `HardwareTestReadiness_TODAY.md` (Troubleshooting section)

### For HDMI / Kiosk Operation
→ `HDMI_KIOSK_RUNBOOK.md` — Setup, boot behavior, emergency relaunch, and current 800x480 layout details (centered weight card + zero diagnostics + daily/shift placeholder)

### For Testing
→ `TestPlan.md`  
→ Use test scripts in `../scripts/`

---

## 🎯 Document Workflow

```
New Deployment:
  1. TODAY_SUMMARY.md (understand what's happening)
  2. WiringAndCommissioning.md (physical setup)
  3. HardwareTestReadiness_TODAY.md (testing procedure)
  4. CalibrationProcedure.md (calibration)

System Understanding:
  1. Architecture.md (overview)
  2. SRS.md (requirements)
  3. Hardware quick references (24b8vin, MegaIND)

Maintenance:
  1. MaintenanceAndTroubleshooting.md
  2. TestPlan.md (regression tests)
  3. CalibrationProcedure.md + CALIBRATION_CURRENT_STATE.md (re-calibration)
```

---

## 📂 File Organization

```
docs/
├── README_DOCS.md (this file)
│
├── ⭐ Pre-Overhaul Reference
│   ├── CURRENT_IMPLEMENTATION.md   ← Libraries, Kalman, config options
│   └── CURRENT_UI_REFERENCE.md     ← UI pages, routes, API endpoints
│
├── TODAY: Real Hardware Test
│   ├── TODAY_SUMMARY.md
│   ├── HardwareTestReadiness_TODAY.md
│   └── QUICK_START_HARDWARE_TEST.md
│
├── System Documentation
│   ├── Architecture.md
│   ├── SRS.md
│   └── RiskRegister.md
│
├── Zero/Tare & Drift
│   ├── ZERO_VS_TARE_FIX.md           ← How ZERO fixes drift
│   └── DRIFT_COMPENSATION_DIAGRAM.md ← Visual signal flow
│
├── Hardware Reference
│   ├── 24b8vin_*.md
│   ├── MegaIND_*.md
│   └── WiringAndCommissioning.md
│
└── Procedures
    ├── CalibrationProcedure.md
    ├── TestPlan.md
    ├── MaintenanceAndTroubleshooting.md
    └── HDMI_KIOSK_RUNBOOK.md         ← Setup and operation of HDMI UI
```

---

## 🔧 Related Resources

### Scripts (`../scripts/`)
- Test scripts (bash + Python)
- Installation scripts
- Export/backup utilities

### Source Code (`../src/`)
- `app/` — Flask web UI
- `core/` — Filtering, zeroing, and zero-tracking logic
- `hw/` — Hardware interfaces (real + simulated)
- `db/` — SQLite schema + repositories
- `services/` — Acquisition loop, output writer

### Vendor Documentation (`.vendor/`)
- 24b8vin-rpi — DAQ board vendor code
- megaind-rpi — MegaIND vendor code

---

**Last Updated**: February 12, 2026  
**For**: Production deployment with drift compensation  
**Hardware Verified**: December 18, 2025 — Both boards (24b8vin @ 0x31, MegaIND @ 0x50) online and working  
**Drift Fix**: December 23, 2025 — ZERO button now properly compensates for drift (see `ZERO_VS_TARE_FIX.md`)  
**Auto-Armed Outputs**: February 12, 2026 — PLC outputs now default to ARMED on startup (see `AUTO_ARMED_OUTPUT_CHANGE.md`)
