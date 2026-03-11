# Test Plan

> **🚀 For complete hardware test deployment, see:**
> - **`docs/HardwareTestReadiness_TODAY.md`** — Complete runbook for fresh Pi → production
> - **`docs/TODAY_SUMMARY.md`** — Executive summary and checklist
> - **`scripts/test_*.sh`** and **`scripts/*_test_log.py`** — Automated test scripts

This document describes the general test strategy. For a step-by-step deployment and testing procedure with real hardware, use the Hardware Test Readiness runbook above.

---

## 1. Test Environment
### 1.1 Bench (No process equipment)
- Raspberry Pi with Sequent boards connected
- DMM or loop calibrator for analog output verification
- Optional: test PLC analog input

### 1.2 Production (Installed)
- Load cells mounted in final mechanical configuration
- SlimPak excitation wired and measured
- PLC analog input wired

## 2. Bench Tests (Simulated Mode)
### TP-01 Startup and UI
- Start: `python -m src.app`
- Verify:
  - UI loads
  - dashboard shows live updates
  - config page can save JSON and persists across restart

### TP-02 Stability Detector
- Vary vibration/noise environment.
- Verify stability transitions:
  - stable on steady load
  - unstable during vibration or movement

### TP-03 Calibration Point Enforcement
- Attempt to add calibration point while unstable.
- Verify:
  - point rejected
  - warning event logged

### TP-04 PLC Profile Point Storage
- Add several points for both modes.
- Verify points appear on PLC Profile page and persist.

### TP-05 Fault Safe Output (Excitation Monitoring Enabled)
- Ensure **Enable Excitation Monitoring** is ON.
- Force excitation below fault threshold (disconnect excitation source or use variable supply).
- Verify:
  - fault flag set
  - output command forced to safe value (0V or 4mA)
  - event logged

## 3. Raspberry Pi Bench Tests (No Load Cells)
### TP-06 Service Under systemd
- Install unit and start service.
- Verify:
  - service restarts on stop
  - logs show expected startup messages

### TP-07 SD-card Wear Considerations
- Verify trend logging rate and DB size growth is reasonable.
- Verify export script works and doesn’t lock DB for long durations.

## 4. Production Tests (Installed)

> **💡 Use automated test scripts for faster verification:**
> ```bash
> # Hardware smoke test
> ./scripts/test_hardware_basic.sh
> 
> # DAQ channel verification
> ./scripts/test_24b8vin_channels.sh
> 
> # Analog output verification
> ./scripts/test_megaind_output.sh
> python3 scripts/analog_output_test_log.py
> 
> # Calibration verification
> python3 scripts/verify_calibration.py
> ```

### TP-08 Excitation Measurement
- Verify excitation readback in UI matches DMM within tolerance.
- Verify warning and fault thresholds trigger at expected voltages.
- Toggle **Enable Excitation Monitoring** OFF and verify excitation no longer drives fault-safe output.
- **Automated helper**: `test_hardware_basic.sh` checks board presence

### TP-09 Load Cell Channel Sanity
- For each channel:
  - apply small known load on that corner/point
  - verify raw mV changes with expected polarity
  - verify disabled channels have no effect on total
- **Automated helper**: `test_24b8vin_channels.sh` reads all channels

### TP-10 Multi-Point Calibration
- Perform 3–10 point calibration.
- Verify:
  - UI weight accuracy within site goal (0–5 lb typical)
  - repeatability under vibration is acceptable after tuning
- **Automated helper**: `python3 scripts/verify_calibration.py` for interactive verification

### TP-11 PLC Scaling Verification
- If PLC scaling is legacy/unknown:
  - build PLC profile curve
  - verify PLC displayed weight matches true weight across range
- **Automated helper**: `python3 scripts/analog_output_test_log.py` for systematic testing

### TP-12 Dump Detection and Totals
- Run several real dump cycles.
- Verify:
  - dumps detected at appropriate thresholds
  - totals accumulate correctly for day/week/month/year
  - false positives are minimal

### TP-13 Board Discovery & Hardware Status
- Start system on Pi with hardware connected.
- Verify Settings → System shows **I/O LIVE** and "Boards Online: 2/2".
- Disconnect power/stack from one board (simulate failure).
- Verify:
  - Dashboard shows "Boards Online: 1/2" (red pill for missing board).
  - Fault flag set.
  - Settings/System + logs indicate missing board (and dashboard pill shows missing/offline).
- **Automated helper**: `test_hardware_basic.sh` verifies I2C and board presence

## 5. Regression Checklist (After Any Change)
- UI starts and loads all pages
- acquisition loop stays alive for 1+ hour
- DB schema migrates cleanly on existing DB
- safe output behavior works when fault conditions occur

## 6. Completed Job Webhook Tests (March 2026)

### TP-14 Job Transition Completion Payload
- Send normal job A then normal job B for the same `line_id` + `machine_id`.
- Verify:
  - one completed-job payload is produced for job A
  - payload shape matches integration contract
  - values include dump count, totals, averages, and final set weight

### TP-15 Manual Override Attribution
- During active normal job A, apply HDMI manual override.
- Then send normal job B to close A.
- Verify:
  - `override_seen=true` in completed payload for A
  - override value is reflected in summary fields
  - orphan overrides (no active normal job) do not create completion payloads

### TP-16 Durable Outbox Retry
- Configure completed-job webhook URL to an unavailable endpoint.
- Trigger a completed job.
- Verify:
  - row appears in `job_completion_outbox`
  - `attempt_count` increments and `next_retry_at_utc` advances
  - once endpoint is restored, row transitions to sent

### TP-17 Basket Dump Opto Counting
- Map one or more MegaIND opto inputs to **Basket Dump Count** (Settings → Buttons).
- During an active normal job, trigger rising-edge pulses on the mapped opto(s).
- Send a new normal job ID to close the prior job.
- Verify:
  - `counted_events` table contains rows with `event_type='basket_dump'` and correct `source_channel`
  - completed-job payload includes `basket_dump_count` matching the job window total


