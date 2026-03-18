# Deployment Log

This document records all deployments to production Pi systems.

---

## 2026-03-18 - Staged: HDMI Tare Removal + Tare Tracing + HDMI Touch Target Update (No Restart)

**Prepared By**: jthompson (with AI assistance)  
**Sites Updated**: Pi `hoppers.tail840434.ts.net` (Tailscale node `100.114.238.54`) — runtime files staged to `/opt/loadcell-transmitter`  
**Version**: main branch working tree (Mar 18 hopper bundle)

**Scope Staged**:
- **Smaller Stable-Drift Capture**: between-jobs re-zero warning flow now captures smaller stable drift into the warning/job payload path instead of waiting only for large threshold-matching cases.
- **HDMI Tare Removal**: removed `TARE` and `CLEAR TARE` from the HDMI operator page while keeping tare on the main dashboard.
- **Tare Source Tracing**: tare-related event logs now capture whether the trigger came from web/API requests or from opto input, plus request surface/channel context.
- **HDMI Touch Target Update**: enlarged bottom HDMI controls for `ZERO`, `CLEAR ZERO`, and `OVERRIDE`.

**Production Safety Constraint**:
- Service **not** restarted; Pi is still running the previous in-memory code.
- No reboot, reset, or service bounce performed while the line is in use.
- Runtime files were copied over Tailscale to `/tmp`, then installed into `/opt/loadcell-transmitter` with `sudo cp` because runtime files are root-owned.

**Files Staged**:
- `src/services/acquisition.py`
- `src/app/routes.py`
- `src/app/templates/hdmi.html`
- `tests/test_api_tare.py`
- `tests/test_rezero_warning.py`
- `docs/CURRENT_UI_REFERENCE.md`
- `docs/HDMI_KIOSK_RUNBOOK.md`
- `docs/CURRENT_IMPLEMENTATION.md`

**Local Validation**:
- `python -m pytest tests/test_api_tare.py tests/test_api_zero.py tests/test_rezero_warning.py`
- Result: `18 passed`
- Lint check on touched files: clean
- Local HDMI preview confirmed the intended one-row larger-button layout only on a clean preview port; stale preview processes were later terminated.

**Post-Restart Verification (approved window only)**:
1. Restart `loadcell-transmitter` once.
2. Confirm HDMI no longer exposes tare controls.
3. Confirm `ZERO`, `CLEAR ZERO`, and `OVERRIDE` fit correctly and remain easy to tap on the real screen.
4. Trigger/observe tare-related events and confirm the log details identify the real source (`web_api` surface versus `opto_input`).
5. Re-check between-jobs re-zero warning behavior with the smaller stable-drift capture update active.

---

## 2026-03-17 - Verified: Live Completed-Job Webhook Runtime on Production

**Verified By**: jthompson (with AI assistance)  
**Sites Observed**: Pi `hoppers.tail840434.ts.net` / Tailscale node `100.114.238.54`  
**Type**: Production runtime verification only (no restart or deploy performed in this session)

**What Was Verified**:
- `job_completion_outbox` row `60` for `PLP6` job `1704584` was created and marked `sent` at `2026-03-17T23:08:27+00:00`.
- The live payload included:
  - `basket_dump_count`
  - `rezero_warning_seen`
  - `rezero_warning_reason`
  - `rezero_warning_weight_lbs`
  - `rezero_warning_threshold_lbs`
  - `post_dump_rezero_applied`
  - `post_dump_rezero_last_apply_utc`
- Pi database confirmed schema version `7` with `job_lifecycle_state`, `job_completion_outbox`, and `counted_events` tables present.

**Backend Verification**:
- Replayed the last 5 real Pi completed-job payloads to the configured backend webhook:
  - 4 payloads stored successfully
  - 1 payload correctly treated as a duplicate
  - all 5 requests returned HTTP `200`

**Operational Conclusion**:
- Completed-job webhook lifecycle/outbox support is live on production.
- Expanded completed-job payload fields are live on production.
- Remaining runtime behavior still needing direct line validation:
  - non-zero `basket_dump_count`
  - floor-threshold / legacy floor signal behavior
  - a true between-jobs re-zero warning case

---

## 2026-03-16 - Staged: Between-Jobs Re-Zero Warning + Webhook Diagnostics (No Restart)

**Prepared By**: jthompson (with AI assistance)  
**Sites Updated**: Pi `hoppers.tail840434.ts.net` (Tailscale node `100.114.238.54`) — runtime files staged to `/opt/loadcell-transmitter`  
**Version**: main branch working tree (re-zero warning rollout)

**Scope Staged**:
- **Between-Jobs Re-Zero Warning**: Added a non-blocking warning that latches after a completed dump/cycle when the scale settles stable and remains outside the configured zero tolerance.
- **Operator UI Warning Surface**: Added persistent warning banners to both `/hdmi` and `/` dashboard so the operator sees `Press ZERO before next job` when the scale is off.
- **Settings Support**: Added `scale.rezero_warning_threshold_lb` with a default of `20.0 lb`.
- **Webhook Diagnostics**: Completed-job payload now includes `rezero_warning_seen`, `rezero_warning_reason`, `rezero_warning_weight_lbs`, `rezero_warning_threshold_lbs`, `post_dump_rezero_applied`, and `post_dump_rezero_last_apply_utc`.

**Production Safety Constraint**:
- Service **not** restarted; Pi is still running the previous in-memory code.
- No reboot, reset, or service bounce performed while the line is in use.
- Files were copied to `/home/pi/rezero-stage` first, then installed into `/opt/loadcell-transmitter` with `sudo install` because runtime files are root-owned.

**Files Staged**:
- `src/services/acquisition.py`
- `src/app/routes.py`
- `src/db/repo.py`
- `src/app/templates/dashboard.html`
- `src/app/templates/hdmi.html`
- `src/app/templates/settings.html`

**Local Validation**:
- `python -m pytest tests/test_rezero_warning.py tests/test_job_completion_webhook.py tests/test_snapshot_job_control.py tests/test_api_zero.py`
- Result: `20 passed`
- Lint check on touched files: clean

**Post-Restart Verification (approved window only)**:
1. Restart `loadcell-transmitter` once.
2. Run a job and let the scale settle empty before the next job.
3. Verify warning appears only when stable zero-relative weight exceeds the configured threshold.
4. Press `ZERO` and verify the warning clears.
5. Confirm the next completed-job webhook includes the new re-zero diagnostic fields.

---

## 2026-03-06 - Staged: Basket Dump Opto + Floor Threshold + Full Sync (No Restart)

**Prepared By**: jthompson (with AI assistance)  
**Sites Updated**: Pi `hoppers.tail840434.ts.net` (Tailscale) — files staged to `/opt/loadcell-transmitter`  
**Version**: main branch (basket dump + floor threshold + schema v7)

**Scope Staged**:
- **Basket Dump Opto Counting**: New opto action `basket_dump` records rising-edge pulses into `counted_events` table. Completed-job webhook payload includes `basket_dump_count`. Schema v7 migration.
- **Configurable Floor Threshold**: `scale.zero_target_lb` and `job_control.legacy_floor_signal_value` for operator-editable floor and legacy PLC signal at/below floor.
- **Full Sync**: All changed runtime files, docs, and tests copied to Pi.

**Production Safety Constraint**:
- Service **not** restarted; Pi still running previous code.
- Restart required to activate basket dump and floor threshold changes.

**Files Staged** (examples):
- `src/db/schema.py`, `src/db/migrate.py`, `src/db/repo.py`
- `src/services/acquisition.py`, `src/app/routes.py`
- `src/app/templates/settings.html`
- `tests/test_counted_events.py`, `tests/test_job_completion_webhook.py`
- All updated docs

**Planned Window Actions**:
1. Restart `loadcell-transmitter` service.
2. Verify schema migration to v7 and `counted_events` table.
3. Verify Settings → Buttons → Basket Dump Count option.
4. Verify completed-job payload includes `basket_dump_count`.

---

## 2026-03-05 09:10 CST - Staged: Completed Job Webhook + Docs (No Pi Deploy Yet)

**Prepared By**: jthompson (with AI assistance)  
**Sites Updated**: Local repository only (no production Pi restart/reboot)  
**Version**: main branch commit `edacaa3`

**Scope Prepared**:
- Completed-job summary generation on normal job transition.
- Durable outbound webhook queue with retry/backoff (`job_completion_outbox`).
- Lifecycle tracking (`job_lifecycle_state`) and set-weight timestamping (`record_time_set_utc`).
- Manual override attribution to active normal job windows.
- Integration docs + payload examples updated.

**Production Safety Constraint**:
- Pi is currently in production.
- No reboot/reset performed.
- Deployment to Pi and service restart deferred to approved maintenance window.

**Planned Window Actions**:
1. Deploy updated Python files to Pi.
2. Restart `loadcell-transmitter` service once.
3. Verify schema migration to v6 and outbound webhook flow.
4. Apply timezone update to `America/Chicago` during same window if approved.

---

## 2026-02-27 11:20 EST - v3.4 Webhook Contract Cutover + HDMI Job Target + Tailscale Funnel

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - full v3.4 webhook/live UI update  
**Version**: v3.4 (local working tree)

**Files Deployed (12 files)**:
- `src/app/routes.py` — New webhook payload contract + expanded auth header support
- `src/services/acquisition.py` — Idempotency dedupe (`idempotencyKey`) and webhook handling updates
- `src/db/repo.py` — Config schema/default alignment for job control
- `src/core/zero_tracking.py`
- `src/core/throughput_cycle.py`
- `src/core/post_dump_rezero.py`
- `src/core/zeroing.py`
- `src/app/templates/dashboard.html`
- `src/app/templates/hdmi.html` — Added Job Target panel (Set Weight + Scale Weight)
- `src/app/templates/settings.html`
- `src/app/templates/scale_settings.html`
- `src/app/templates/calibration.html`

**Operational Changes**:
- Installed and authenticated Tailscale on Pi (`hoppers` node).
- Enabled Tailscale Funnel for public HTTPS ingress:
  - `https://hoppers.tail840434.ts.net`
- Active webhook endpoint exposed externally:
  - `https://hoppers.tail840434.ts.net/api/job/webhook`

**Webhook Contract (live)**:
- Payload fields: `event`, `jobId`, `machineKey`, `loadSize`, `idempotencyKey`, `timestamp`
- Supported auth headers:
  - `X-API-Key` (primary)
  - `Authorization` (`Bearer` / `Basic`)
  - legacy `X-Scale-Token`

**Verification**:
- Pi reboot completed and `loadcell-transmitter` returned `active`.
- Local and public webhook POST smoke tests returned HTTP `200`.
- `/api/job/status` and `/api/snapshot` reflected live `set_weight` updates.
- HDMI page served new Job Target section.
- Safety gate verified: legacy mode still returns `409` for webhook updates by design.

**Known Follow-up**:
- Investigate mode auto-switch back to `target_signal_mode` after manual legacy switch.
- Ensure mode selection persists cleanly across startup/reboot.

---

## 2026-02-25 06:52 EST - v3.4 Target-Aware Auto-Zero + Post-Dump Re-Zero

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - full code update  
**Version**: v3.4 (local working tree)

**Files Deployed (2 files)**:
- `src/services/acquisition.py` — Target-aware AZT, post-dump re-zero logic, unrounded control loop, opto-zero fix
- `src/app/routes.py` — API snapshot updates (added `zero_target_lb`, restored PLC range fields)

**Reason for Deployment**:
- **Auto-Zero Failure**: Auto-zero was fighting the 3.0 lb zero floor (trying to correct to 0.0 lb).
- **Post-Dump Re-Zero**: Needed one-shot correction after dump cycles to catch larger thermal drift.
- **Precision Fix**: Control loop was using rounded weights, causing "stuck" zero tracking near thresholds.
- **Bug Fix**: Fixed `NameError` in opto-button ZERO path.

**New Features**:
1. **Target-Aware Auto-Zero**: Zero tracking now maintains `zero_target_lb` (3.0 lb) instead of 0.0 lb.
2. **Post-Dump Re-Zero**: One-shot correction triggers after confirmed dump cycle (stable + empty).
3. **Unrounded Control Loop**: Stability and zero logic use full-precision filtered weight; rounding is display-only.
4. **Throughput Alignment**: Cycle detection thresholds are now target-relative (works with 3 lb floor).

**Verification**:
- Service restarted successfully via `systemctl restart`
- `systemctl is-active loadcell-transmitter` returned `active`
- Hardware initialized: I/O is LIVE
- File integrity check passed (SHA256 match)
- **Manual ZERO**: Confirmed 3 lb target behavior
- **Auto-Zero**: Confirmed tracking around 3 lb target
- **Post-Dump**: Confirmed re-zero triggers after cycle

**Current System State**:
- **Pi IP**: 172.16.190.25 (Hoppers)
- **Service**: active (running)
- **Zero Floor**: 3 lbs (`zero_target_lb = 3.0`)
- **Zero Tracking**: ENABLED (target-aware)
- **Post-Dump Re-Zero**: ENABLED

---

## 2026-02-24 16:30 EST - System Snapshot & Verification

**Action By**: jthompson (with AI assistance)
**Sites Updated**: Local Documentation Only
**Version**: v3.3.2 (local working tree)

**Files Created**:
- `docs/SNAPSHOT_20260224.md` — Full system state capture (OS, App Config, Calibration, PLC Profile).
- `scripts/dump_db_settings.py` — Utility to dump SQLite settings to JSON.

**Reason**:
- Verify live production settings against documentation.
- Capture baseline for future drift analysis.
- Confirm zero offset and PLC profile integrity.

**Findings**:
- **Zero Offset**: 32.68 lbs (0.29 mV). Significant offset detected.
- **PLC Profile**: 17 points (10-400 lb), linear 0-10V mapping confirmed.
- **Calibration**: 9-point piecewise linear curve active.
- **Zero Tracking**: Active with 0.05 lb range.

---

## 2026-02-24 10:30 EST - v3.3.2 Documentation & Sync Cleanup

**Deployed By**: jthompson (with AI assistance)
**Sites Updated**: Local Repo Sync (No code pushed to Pi)
**Version**: v3.3.2 (local working tree)

**Files Synced**:
- `src/core/post_dump_rezero.py` — Added to local git repo (was active on Pi but untracked)
- `docs/DOCUMENTATION_INDEX.md` — Created new index
- `docs/SYNC_REPORT.md` — Created sync report
- `docs/archive/` — Created archive for old logs

**Reason for Sync**:
- Found critical safety file `post_dump_rezero.py` active on production Pi but missing from version control.
- Documentation cleanup to reduce noise and organize project.

**Verification**:
- `git status` confirms `src/core/post_dump_rezero.py` is now tracked.
- Pi snapshot confirms production state matches local repo.

---

## 2026-02-20 14:30 EST - v3.3 Hardware Upgrade + Negative Dump Fix + Zero Floor

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - full code update + hardware recalibration  
**Version**: v3.3 (local working tree)

**Files Deployed (15 files)**:
- `src/core/throughput_cycle.py` — Negative dump fix (floor empty weight to max(0, empty))
- `src/services/acquisition.py` — Division-by-zero fix, calibration gate for zero tracking, zero floor support
- `src/core/zero_tracking.py` — Type safety fix in `_locked()` method, calibration mode gate
- `src/core/zeroing.py` — New `calibration_signal_at_weight()` function, `compute_zero_offset()` accepts `zero_target_lb`
- `src/app/routes.py` — Zero floor support in ZERO button API
- `src/services/output_writer.py` — (Code review improvements)
- `deploy_to_pi/acquisition.py` — Matching changes to deploy version
- `deploy_to_pi/routes.py` — Matching changes to deploy version
- `deploy_to_pi/throughput_cycle.py` — Added to deploy files (new file)
- `deploy.ps1` — Updated file list to include throughput_cycle.py
- `deploy_with_password.ps1` — Updated file list to include throughput_cycle.py
- `DEPLOY_INSTRUCTIONS.txt` — Updated file list
- `COPY_THESE_FILES.txt` — Updated file list

**Reason for Deployment**:
- **Hardware Change**: Added 4th load cell to summing board (was 3 cells, now 4)
- **Negative Dump Bug**: Empty weight going negative during mechanical hopper push caused inflated dump totals (345-(-60)=405 instead of 345)
- **Code Safety**: Fixed potential division-by-zero in 4 locations (`lbs_per_mv is not None and abs(...)` → `lbs_per_mv is not None and abs(...)`)
- **PLC Dead Zone**: Zero button targeting 0 lb caused PLC output to drop below 0.1V dead zone
- **New PLC Profile**: Old profile topped at 1.663V for 250 lb; new profile sends 2.590V for 250 lb (fixed bad PLC zero offset)

**Hardware Configuration Changes**:
1. **Load Cells**: Upgraded from 3 to 4 S-type load cells on summing board
2. **Full Recalibration Required**: New 4-cell configuration required complete recalibration

**New Calibration (4-cell system)**:
- **Points**: 9 points (3, 25, 50, 100, 150, 200, 250, 300, 335 lbs)
- **Anchor**: 3 lb @ 5.644 mV (zero floor baked into calibration)
- **Slope**: 112 lb/mV (projected from old 3-cell data, verified to hold with 4 cells)
- **Zero Floor**: Empty now reads 3 lb instead of 0 lb (prevents PLC dead zone)

**New PLC Profile (17 points, 10-400 lb)**:
- **Formula**: V = (weight + 9) / 100
- **PLC Config**: Multiplier = 1000, -9 lb offset in PLC hardware
- **Range**: 10 lb (0.190V) to 400 lb (4.090V)
- **Old vs New**: Old profile 1.663V for 250 lb → New profile 2.590V for 250 lb
- **Fix**: Corrected bad PLC zero offset from previous profile

**New Features**:
1. **Negative Dump Fix**: `max(0, empty_lbs)` prevents inflated dump totals when hopper pushes negative
2. **Zero Floor**: New config `scale.zero_target_lb: 3.0` — ZERO button now targets 3 lbs instead of 0 lbs to keep PLC output above dead zone
3. **High-Res Diagnostic Logging**: 20Hz logging to trends_total (weight + output command), delayed start after Monday Feb 23, 2026 06:00 EST

**Code Quality Improvements**:
- Fixed 4 locations with potential division-by-zero: `lbs_per_mv is not None and abs(...)` checks
- Zero tracking now disabled during calibration mode (`calibration_active` gate)
- Type safety improvement in `zero_tracking.py` `_locked()` method

**Verification**:
- Service restarted successfully via `systemctl restart`
- `systemctl is-active loadcell-transmitter` returned `active`
- Hardware initialized: I/O is LIVE (DAQ stack=0, MegaIND stack=2)
- 4 load cells detected on summing board, single channel output
- Calibration verified: 9-point piecewise linear, slope 112 lb/mV
- PLC profile verified: 17 points, armed, 0-10V mode
- Zero floor tested: ZERO button targets 3 lb, PLC output stays above dead zone
- Zero tracking: DISABLED (operator will use manual ZERO with 3 lb floor)

**Current System State**:
- **Pi IP**: 172.16.190.25 (Hoppers)
- **Service**: active (running), PID 2750
- **Hardware**: 4 S-type load cells → summing board → DAQ Channel 1
- **Calibration**: 9-point piecewise, 112 lb/mV slope, 3 lb floor
- **PLC Output**: 0-10V mode, 17-point profile (10-400 lb), armed
- **Zero Floor**: 3 lbs (`zero_target_lb = 3.0`)
- **Zero Tracking**: DISABLED (manual ZERO preferred)

**Notes**:
- Raw negative empty_lbs still recorded in dump logs for diagnostics and auto-zero detection
- High-res logging (20Hz) will activate Monday Feb 23, 2026 06:00 EST to diagnose PLC vs scale discrepancy
- Deploy scripts updated to include `throughput_cycle.py` in future deployments
- Zero floor is baked into calibration anchor point (3 lb @ 5.644 mV)

---

## 2026-02-18 01:54 EST - v3.2 Full System Update + PLC Profile & Filter Fix

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - full code update + live DB tuning  
**Version**: v3.2 (local working tree)

**Files Deployed (13 files)**:
- `src/app/routes.py` — Updated API endpoints, zero offset reset on cal changes, CLEAR ZERO button
- `src/services/acquisition.py` — Smart zero clear, startup auto-zero, improved zero tracking logic
- `src/services/output_writer.py` — Output writer refinements
- `src/db/repo.py` — Config persistence improvements, update_config_section helper
- `src/db/schema.py` — Schema updates
- `src/core/zero_tracking.py` — Dual-path ZeroTracker with startup lockout, max correction guard
- `src/core/zeroing.py` — Zeroing logic improvements
- `src/core/filtering.py` — Filter parameter updates
- `src/app/templates/dashboard.html` — CLEAR ZERO button, UI improvements
- `src/app/templates/settings.html` — Smart zero clear settings, startup auto-zero toggle, filter tuning
- `src/app/templates/scale_settings.html` — Updated zero & scale settings display
- `src/app/templates/calibration.html` — Calibration UI improvements
- `src/app/templates/hdmi.html` — HDMI kiosk template updates

**Reason for Deployment**:
- Scale weight drifting 20+ lbs over the day with no correction (zero tracking was OFF, zero offset was NULL)
- PLC output diverging from scale reading due to corrupted PLC profile (mid-session PLC zero change created 5x slope kink between 36-51 lbs)
- PLC output lagging behind scale during fast fills (Kalman filter Q=7/R=100 too sluggish)
- New features: Smart Zero Clear, Startup Auto-Zero, CLEAR ZERO button, improved zero tracking guards

**Live Database Changes (no restart required)**:
1. **PLC Profile Fixed**: Updated 1 lb (0.100→0.417V) and 10 lb (0.134→0.462V) points to correct PLC zero. Added real-measurement points at 100 lb (0.915V), 200 lb (1.418V), 250 lb (1.663V). Removed stale 101 lb point. Final: 10 clean points on a straight 0.00503 V/lb line from 1-250 lbs.
2. **Kalman Filter Tuned**: Changed Q from 7→25, R from 100→25. Reduces PLC output lag from ~1.7 lbs to ~0.3 lbs at 10 lbs/sec fill rate.

**Verification**:
- Service restarted successfully via `systemctl kill -s SIGKILL` + `start`
- `systemctl is-active loadcell-transmitter` returned `active`
- Hardware initialized: I/O is LIVE (DAQ stack=0, MegaIND stack=2)
- Boards 2/2 online, no faults, 20 Hz loop rate
- PLC profile verified: all 10 points on consistent ~0.005 V/lb slope
- Filter change confirmed live via config refresh

**Pre-Deployment Data Saved**: `docs/pre_retrain_backup_2026-02-18.md`

**Live Tuning (same day, 12:00-18:00 UTC)**:
- PLC profile rebuilt from real nudge data (PLC uses `*1000` multiplier, not `*500`)
- Kalman filter adjusted to Q=10/R=25
- Zero tracking tuned for hopper vibration environment:
  - range=25 lb, hold=0.5s, neg_hold=8s, rate=50 lbs/s, max_correction=50 lb
  - Smart Clear disabled (was fighting with tracking)
  - Stability loosened: stddev=10, slope=25
  - Startup auto-zero enabled, manual gate removed
- Code hotfix: post-dump zero window (10s expanded range after dump detection)
- 4-hour shift monitoring log captured for analysis

**Notes**:
- Calibration still needs retraining (scheduled for Feb 18/19)
- Zero tracking still OFF — enable after calibration retrain
- Smart Zero Clear available but not yet enabled — enable after retrain
- PLC profile formula verified against 3 real nudge measurements: voltage = 0.412 + (weight × 0.00503)
- Old Feb 16 calibration had: duplicate 50 lb point, drift-contaminated 170 lb point (41 min gap), PLC zero changed mid-session

---

## 2026-02-15 10:30 EST - v3.1 Canonical mV Zeroing & Persistence Fix

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - hot-patch deployment  
**Version**: v3.1 (local working tree)

**Files Deployed**:
- `deploy_to_pi/routes.py` — Fixed manual ZERO button (now calculates drift_mv = raw - cal_zero)
- `deploy_to_pi/acquisition.py` — Fixed zero tracking persistence (converts lbs → mV for storage)
- `deploy_to_pi/repo.py` — Config persistence with zero_offset_mv as canonical field

**Reason for Deployment**:
- **CRITICAL BUG**: Zero offset was being stored as Pounds (lbs) in a Millivolt (mV) field
- Symptom: Zeroing operations would fail or produce incorrect weight readings
- Root cause: Unit mismatch causing 100x+ magnitude errors
- Fix: Refactored system to use `zero_offset_mv` as canonical source of truth
- Architecture: Zero applied in signal domain (mV) BEFORE calibration, preserving slope integrity

**Technical Details**:
- `zero_offset_mv` → CANONICAL field (signal domain correction, always in mV)
- `zero_offset_lbs` → DERIVED field (display value = zero_offset_mv * lbs_per_mv)
- Manual ZERO: Calculates signal drift (current_raw_mv - cal_zero_mv), stores as mV
- Zero Tracking: Measures weight error in lbs, converts to mV using calibration slope, stores as mV
- Fixed persistence race conditions with throttled writes and atomic config updates

**Verification**:
- Service restarted successfully via systemctl
- `systemctl is-active loadcell-transmitter` returned `active`
- User tested Manual ZERO button: scale forced to 0.0 lb correctly
- User confirmed zero tracking working on both positive and negative drift
- **User confirmation**: "Working like a champ"
- Dashboard shows correct zero offset values in both mV and derived lbs

**Notes**:
- This was a hot-patch deployment (no version tag)
- Fixes fundamental architectural issue discovered during field testing
- All previous zero offset data will be interpreted correctly under new system
- No database migration required (config JSON auto-upgraded)
- Zero tracking behavior unchanged from user perspective (just fixed internally)

---

## 2026-02-13 14:31 EST - Fast Negative Auto-Zero for Hopper Scales

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - core logic + templates  
**Version**: v3.0 Zero Tracking (local working tree)

**Files Deployed**:
- `src/core/zero_tracking.py` — Dual-path ZeroTracker with fast negative correction
- `src/services/acquisition.py` — New `negative_hold_s` config field + pass-through to ZeroTracker
- `src/app/routes.py` — Save new `negative_hold_s` setting from form
- `src/app/templates/settings.html` — New "Negative Weight Hold Time" control in Zero & Scale section

**Reason for Deployment**:
- Scale was reading -8 lb after hopper dumps. The zero tracking holdoff timer (6 sec) kept resetting because hopper door bounce caused stability to toggle rapidly (`hold_elapsed_s` never exceeded 0.15s). Auto-zero never fired before material started loading again.
- New fast negative path: when weight is negative, relaxes stability (tolerates vibration), uses 1-second holdoff instead of 6, and corrects the entire error in a single shot with no rate limiting.
- Negative weight on a hopper scale is always drift — the scale physically cannot weigh less than the empty hopper.

**Verification**:
- Service restarted successfully via `systemctl kill` + `start`
- `systemctl is-active loadcell-transmitter` returned `active`
- Hardware initialized: I/O is LIVE (DAQ stack=0, MegaIND stack=2)
- Immediate result: weight went from -8 lb → 2 lb within seconds (fast negative auto-zero fired)
- Zero offset updated to -8.36 lb (matching the prior drift)
- API snapshot confirmed `zero_tracking_reason: "holdoff"` (now in normal positive holdoff for the 2 lb residual)

**Notes**:
- New config field `zero_tracking.negative_hold_s` (default 1.0s) — adjustable in Settings UI
- Existing positive-weight zero tracking behavior is unchanged
- deploy_to_pi/ files also updated with matching logic for future deployments

---

## 2026-02-12 14:27 EST - PLC Output Auto-Armed on Power Up

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - core logic update  
**Version**: local working tree (no tag)

**Files Deployed**:
- `src/db/repo.py` - changed default `output.armed` state from `False` to `True`
- `src/app/routes.py` - changed default `megaind_io.armed` state from `False` to `True`
- `deploy_to_pi/repo.py` - changed default `output.armed` and `megaind_io.armed` from `False` to `True`
- `deploy_to_pi/routes.py` - changed default `megaind_io.armed` state from `False` to `True`

**Reason for Deployment**:
- User requirement: 0-10V PLC output must always default to ARMED/ON after every power up
- Previous behavior: outputs defaulted to DISARMED, requiring manual arming after each restart
- New behavior: outputs default to ARMED, automatically writing weight data on startup
- Disarm toggle still available for maintenance (e.g., when removing hardware cards)

**Verification**:
- Service restarted successfully via `sudo systemctl kill -s SIGKILL` + `start`
- `systemctl is-active loadcell-transmitter` returned `active`
- Hardware initialized: I/O is LIVE (DAQ stack=0, MegaIND stack=2)
- Web UI serving on http://172.16.190.25:8080
- No errors in startup logs

**Notes**:
- This change affects **new installations** and **database resets**
- Existing systems retain their current armed state until database is reset or settings are saved
- Manual disarm is still possible via Settings page or Calibration Hub
- Change applies to both main PLC output and MegaIND I/O extra outputs

---

## 2026-02-12 08:14 EST - HDMI Layout + Zero Metadata Update

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - template + service restart  
**Version**: local working tree (no tag)

**Files Deployed**:
- `src/app/templates/hdmi.html` - centered weight card, zero metadata lines, and shift totals placeholder panel

**Reason for Deployment**:
- Improve readability on physical 800x480 HDMI screen.
- Mirror dashboard zero diagnostics directly on HDMI (`Zero Offset`, `Zero Tracking`, `Zero Updated`).
- Reserve space for upcoming database-backed daily/shift totals while keeping existing bottom controls unchanged.

**Verification**:
- `loadcell-transmitter` restarted successfully and reported `active`.
- `kiosk.service` restarted successfully and reported `active`.
- Remote file check confirmed `zero-tracking-info` and `CLEAR SHIFT TOTAL` markup exists in deployed `hdmi.html`.
- Live endpoint check (`curl http://localhost:8080/hdmi`) returned updated HDMI markup.

**Notes**:
- `CLEAR SHIFT TOTAL` is currently UI-only placeholder behavior.
- Back-end shift/day total clear actions will be wired after throughput database integration.

---

## 2026-02-11 11:59 EST - Excitation Monitoring Toggle

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - code + templates  
**Version**: local working tree (no tag)

**Files Deployed**:
- `src/app/routes.py` - persisted new `excitation.enabled` toggle from Settings form
- `src/services/acquisition.py` - excitation fault gating now conditional on `excitation.enabled`
- `src/db/repo.py` - default config includes `excitation.enabled: true`
- `src/app/templates/settings.html` - added "Enable Excitation Monitoring" UI toggle
- `src/app/templates/scale_settings.html` - added `DISABLED` excitation status display

**Reason for Deployment**:
- Field issue: output was being forced safe because excitation monitoring was active while excitation input was not being used.
- Added operator control to enable/disable excitation fault participation without changing calibration math.

**Verification**:
- Service restarted successfully on Pi.
- `systemctl is-active loadcell-transmitter` returned `active`.
- Remote template check confirmed new setting label exists:
  - `Enable Excitation Monitoring`

**Notes**:
- When monitoring is OFF, excitation does not force safe output.
- DAQ/MegaIND offline faults still force safe behavior as before.

---

## 2025-01-30 - AI Development System Setup

**Deployed By**: jthompson (with AI assistance)  
**Sites Updated**: Site A (172.16.190.25) - Configuration only  
**Version**: N/A (infrastructure setup)

**What Was Added**:
- `.cursor/rules/` - 5 rule files for code standards, deployment, documentation
- `.cursor/skills/` - 7 skill folders for common tasks
- `.cursor/agents/` - 8 subagent files for specialized assistance
- `configs/site_templates/` - Template infrastructure
- `docs/FLEET_INVENTORY.md` - Fleet tracking document
- `docs/DEPLOYMENT_LOG.md` - This deployment log

**Files Created**:
```
.cursor/
├── rules/
│   ├── industrial-code-standards.md
│   ├── pi-deployment.md
│   ├── documentation-sync.md
│   ├── fleet-configuration-management.md
│   └── remote-diagnostics.md
├── skills/
│   ├── deploy-to-pi/SKILL.md
│   ├── sync-hardware-docs/SKILL.md
│   ├── calibration-wizard/SKILL.md
│   ├── i2c-diagnostics/SKILL.md
│   ├── fleet-deployment/SKILL.md
│   ├── backup-calibration-data/SKILL.md
│   └── site-commissioning/SKILL.md
└── agents/
    ├── pi-deployment-specialist.md
    ├── hardware-integration-reviewer.md
    ├── calibration-specialist.md
    ├── documentation-updater.md
    ├── plc-integration-specialist.md
    ├── troubleshooting-guide.md
    ├── fleet-monitor.md
    └── auto-documenter.md

configs/
├── site_templates/
│   └── README.md
└── deployed/
    └── (empty - for future site configs)

docs/
├── FLEET_INVENTORY.md
└── DEPLOYMENT_LOG.md
```

**Reason**: Establish AI-assisted development workflow with automatic documentation, deployment safety, and fleet management capabilities.

**Notes**: 
- No code changes to production Pi
- Configuration files only in local repository
- Ready for future multi-site deployment

---

## Template for Future Deployments

```markdown
## YYYY-MM-DD HH:MM - vX.Y.Z

**Deployed By**: [name]
**Sites Updated**: 
- Site A (172.16.190.25) ✅
- Site B (xxx.xxx.xxx.xxx) ✅

**Files Changed**:
- `src/file1.py` - [reason]
- `src/file2.py` - [reason]

**Reason for Deployment**: 
[Why this was needed - bug fix, feature, etc.]

**Pre-Deployment**:
- [ ] Tested locally
- [ ] Backup created
- [ ] User confirmed

**Verification**:
- [ ] Service running
- [ ] Dashboard accessible
- [ ] Feature tested
- [ ] Logs checked

**Rollback Plan**:
[Commands to rollback if needed]

**Notes**:
[Any observations]
```

---

## Deployment Guidelines

### Before Any Deployment
1. Test changes locally
2. Backup calibration data on target Pi
3. Identify ALL files that need deployment
4. Get user confirmation

### After Any Deployment
1. Verify service running
2. Test the changed feature
3. Check logs for errors
4. Update this log
5. Update FLEET_INVENTORY.md with new version

### Rollback Procedure
```powershell
# Restore database if needed
plink -pw depor pi@[IP] "cp /var/lib/loadcell-transmitter/app.sqlite3.backup /var/lib/loadcell-transmitter/app.sqlite3"

# Restore code
plink -pw depor pi@[IP] "cd /opt/loadcell-transmitter && git checkout [commit]"

# Restart
plink -pw depor pi@[IP] "sudo systemctl restart loadcell-transmitter"
```