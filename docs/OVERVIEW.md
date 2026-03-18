# Documentation Index

## 🎯 LIVE DASHBOARD

# 👉 http://172.16.190.25:8080

Open in any browser to view live load cell readings.

---

## ✅ System Status (March 17, 2026)

| Component | Status | Details |
|-----------|--------|---------|
| **Version** | ✅ tracked repo state | Completed-job webhook runtime verified live on Mar 17; remaining basket/floor/re-zero behavior still needs direct line validation |
| **Dashboard** | ✅ LIVE | http://172.16.190.25:8080 \| Tailscale: hoppers.tail840434.ts.net |
| **Flask Service** | ✅ Running | Auto-starts on boot |
| **24b8vin** (8x ADC) | ✅ Online | I2C 0x31, Firmware 1.4 |
| **MegaIND** (Industrial I/O) | ✅ Online | I2C 0x52 (Stack 2), Firmware 4.8 |
| **Hardware Mode** | ✅ REAL | Live hardware readings |
| **Zero System** | ✅ Stable | Manual ZERO + tracking flow; floor configurable via `zero_target_lb` |
| **Completed Job Webhook** | ✅ LIVE | Verified on `PLP6`; outbox row `60` sent successfully and backend accepted real-payload replays |
| **Basket Dump Opto** | 🟡 Partially verified | `basket_dump_count` field is live; non-zero pulse validation still pending |
| **Between-Jobs Re-Zero Warning** | 🟡 Partially verified | Expanded diagnostic fields are live; smaller stable-drift capture update was staged on Mar 18 and still needs restart/live validation |
| **HDMI Tare Removal** | 🟡 Staged only | HDMI tare controls removed locally and copied to Pi on Mar 18; not live until restart |
| **HDMI Touch Controls** | 🟡 Staged only | Enlarged `ZERO`, `CLEAR ZERO`, and `OVERRIDE` controls copied to Pi on Mar 18; not live until restart |

**Pi:** `Hoppers` at `172.16.190.25` / `hoppers.tail840434.ts.net` — See `CONNECTION_GUIDE.md` for SSH/dashboard access  
**Note:** Production Pi is active; completed-job payload runtime is live, but remaining floor/basket/re-zero behavior still needs line validation in an approved window. Additional Mar 18 HDMI/tare updates are staged on the Pi but not running live yet.

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
- **`APPROVED_WINDOW_CHECKLIST.md`** — Single restart-window activation and live-validation checklist
- **`SET_WEIGHT_PERSISTENCE_RUNBOOK.md`** — Durable set-weight persistence + migration checks
- **`JOB_COMPLETION_WEBHOOK_RUNBOOK.md`** — Completed-job webhook contract, examples, and retry outbox behavior
- **`SCALE_IMAGE_PREPARATION_RUNBOOK.md`** — How to scrape current Pi state, capture a fresh baseline, and create a cloneable image safely

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
→ `APPROVED_WINDOW_CHECKLIST.md` for the next approved service restart

### For Backup / Clone Preparation
→ `SD_CARD_DISASTER_RECOVERY_RUNBOOK.md`
→ `SCALE_IMAGE_PREPARATION_RUNBOOK.md`

### For HDMI / Kiosk Operation
→ `HDMI_KIOSK_RUNBOOK.md` — Setup, boot behavior, emergency relaunch, and current 800x480 layout details (centered weight card + zero diagnostics + large `ZERO` / `CLEAR ZERO` / `OVERRIDE` controls)

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
├── OVERVIEW.md (this file)
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
    ├── HDMI_KIOSK_RUNBOOK.md         ← Setup and operation of HDMI UI
    ├── SET_WEIGHT_PERSISTENCE_RUNBOOK.md
    ├── JOB_COMPLETION_WEBHOOK_RUNBOOK.md
    ├── SCALE_IMAGE_PREPARATION_RUNBOOK.md
    └── TODO_BACKLOG.md
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

**Last Updated**: March 18, 2026  
**Current Version**: live Feb 27 baseline plus Mar 5/6/16 live/staged runtime updates and Mar 18 staged-only HDMI/tare refinements  
**Status**: Production in use; Mar 18 drift/tare/HDMI UI changes are staged on the Pi and await the next approved restart  
**Deployment**: Pi `172.16.190.25` / `hoppers.tail840434.ts.net` currently active; avoid reboot/reset during production  

**Recent Milestones:**
- **Basket Dump Opto (Mar 6, 2026):**
  - Added `basket_dump` opto action; rising-edge pulses stored in `counted_events` table.
  - Completed-job payload includes `basket_dump_count`. Schema v7 migration.
- **Configurable Floor (Mar 6, 2026):**
  - `scale.zero_target_lb` and `job_control.legacy_floor_signal_value` for operator-editable floor.
- **Completed Job Webhook (Mar 5, 2026):**
  - Added completed-job lifecycle tracking + durable outbox retry delivery.
  - Added schema v6 migration (`record_time_set_utc`, lifecycle/outbox tables).
  - Added manual override attribution to active job windows.
- **Between-Jobs Re-Zero Warning (Mar 16, 2026):**
  - Added operator warning banner + completed-job re-zero diagnostics.
  - Staged on Pi; still requires approved restart to become live.
- **HDMI Tare Removal + Tare Tracing (Mar 18, 2026):**
  - Removed tare controls from HDMI and added source attribution to tare-related events.
  - Copied to Pi; still requires approved restart to become live.
- **HDMI Touch Target Resize (Mar 18, 2026):**
  - Enlarged bottom-row `ZERO`, `CLEAR ZERO`, and `OVERRIDE` controls for easier operation on the 800x480 screen.
  - Copied to Pi; still requires approved restart to become live.
- **v3.1** (Feb 15, 2026): Critical zeroing architecture fix - zero_offset_mv now canonical, manual ZERO works instantly
- **Hardware Verified** (Feb 15, 2026): Both boards (24b8vin @ 0x31, MegaIND @ 0x52) online and working
- **Auto-Armed Outputs** (Feb 12, 2026): PLC outputs default to ARMED on startup
- **v3.0 Zero Tracking** (Feb 13, 2026): Dual-path zero tracker with fast negative correction
